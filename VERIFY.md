# Verifying Roomies is fully operational

Two modes. Mode A needs nothing installed beyond Python. Mode B is the full
production-shaped stack (Postgres + Redis + Celery worker) and additionally
runs the two concurrency tests that prove the ledger under real row locks.

---

## Mode A — local, no Docker (works right now)

From the project root (`roomies-backend`):

**1. The test suite is the primary proof.** Expect `58 passed, 2 skipped`
(the 2 skipped are Postgres-only concurrency tests — see Mode B):

```
.venv\Scripts\python -m pytest --cov
```

**2. Boot the API:**

```
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py runserver
```

**3. Open the interactive docs:** http://localhost:8000/api/v1/docs/
You should see ~26 endpoints grouped by tag (auth, rooms, wallet, ...).

**4. Walk the core loop in Swagger UI:**

1. `POST /api/v1/auth/request-otp/` with body `{"phone": "+919876500000"}`
   → 200, response echoes `debug_code: "123456"`.
2. `POST /api/v1/auth/verify-otp/` with `{"phone": "+919876500000", "code": "123456"}`
   → 200 with `access` and `refresh` tokens.
3. Click **Authorize** (top right), paste the `access` token.
4. `GET /api/v1/rooms/?status=live` → 6 seeded live rooms.
5. `GET /api/v1/wallet/` → your seeded balance and ledger entries.
6. `POST /api/v1/rooms/{id}/gifts/` — pick a room you don't host, set header
   `Idempotency-Key: test-1`, body `{"recipient_id": <host id>, "gift_type_id": 1}`
   → **201**. Check `GET /wallet/` — balance dropped by the gift price.
7. **Send the exact same request again** (same `Idempotency-Key: test-1`)
   → **200** with the *same* gift id, and the wallet is *not* charged again.
   This is the idempotency guarantee.
8. `POST` a third time with a *new* key → 201, charged again (as it should be).

**5. Check the moderation + social loop:** follow a user
(`POST /users/2/follow/`), file a report (`POST /reports/`), list
notifications (`GET /notifications/`).

---

## Mode B — full stack with Docker (after Docker Desktop is installed)

**1. Start everything** (Postgres 16, Redis 7, Django, Celery worker):

```
docker compose up --build
```

First build takes a few minutes. Healthy when the web service logs
`Starting development server at http://0.0.0.0:8000/`.

**2. Seed and verify** (new terminal):

```
docker compose exec web python manage.py seed_demo
```

Then repeat the Swagger walk-through above — same URL,
http://localhost:8000/api/v1/docs/, but now backed by Postgres and Redis.

**3. Run the FULL test suite including the concurrency tests** — this is the
one thing Mode A cannot do. Against Postgres, expect **60 passed, 0 skipped**:

```
docker compose exec web pytest
```

The two extra tests fire 10 simultaneous gift transactions from a wallet
funded for only 3 and race 5 identical idempotency keys from parallel
threads — proving no overspend and no double-charge under real
`SELECT ... FOR UPDATE` row locking.

**4. Prove the Celery fan-out is really async now:** watch the worker logs

```
docker compose logs -f worker
```

then create a room via the API — you'll see
`notify_followers_of_live_room` received and executed by the worker process,
not the web process.

**5. Prove the Redis cache:** hit `GET /api/v1/rooms/?status=live` twice and

```
docker compose exec redis redis-cli KEYS "*rooms:list*"
```

shows the cached feed key; end a room and the version key bumps
(old entries are simply abandoned to expire).

---

## CI (after pushing to GitHub)

Push to GitHub and the Actions workflow (`.github/workflows/ci.yml`) runs the
entire suite against real Postgres + Redis service containers on every push —
the green check is the public, reproducible version of Mode B step 3.
