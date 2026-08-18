import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, timeAgo, useToast } from "../components/helpers.jsx";
import {
  CoinIcon,
  Equalizer,
  TargetIcon,
  UsersIcon,
  WaveIcon,
} from "../components/Icons.jsx";

function RoomCard({ room }) {
  const live = room.status === "live";
  return (
    <Link to={`/rooms/${room.id}`}>
      <div className="card room-card">
        <div className="row between">
          <div className="row" style={{ gap: 8 }}>
            {live ? <Equalizer active /> : null}
            <span className={`badge ${room.status}`}>
              {live ? "On air" : "Ended"}
            </span>
          </div>
          {room.topic && <span className="badge topic">{room.topic}</span>}
        </div>
        <div className="title">{room.title}</div>
        {room.goal_coins ? (
          <div className="stack" style={{ gap: 6 }}>
            <div className="row between">
              <span className="faint row" style={{ gap: 5 }}>
                <TargetIcon size={12} />
                {room.goal_title || "Room goal"}
              </span>
              <span className="faint">
                {room.pledged_coins}/{room.goal_coins}
              </span>
            </div>
            <div className={`meter${room.goal_reached ? " done" : ""}`} style={{ height: 6 }}>
              <i
                style={{
                  width: `${Math.min(100, (room.pledged_coins / room.goal_coins) * 100)}%`,
                }}
              />
            </div>
          </div>
        ) : null}
        <div className="row between">
          <div className="row" style={{ gap: 9 }}>
            <Avatar name={room.host.display_name} sm />
            <span className="dim" style={{ fontWeight: 600 }}>
              {room.host.display_name}
            </span>
          </div>
          <span className="meta">
            <UsersIcon size={13} />
            {room.active_participants}/{room.max_seats} · {timeAgo(room.started_at)}
          </span>
        </div>
      </div>
    </Link>
  );
}

function WhoToFollow({ toast }) {
  const [rows, setRows] = useState([]);
  const load = useCallback(
    () => api("/api/v1/users/suggested/").then(setRows).catch(() => {}),
    []
  );
  useEffect(() => {
    load();
  }, [load]);

  const follow = async (id) => {
    try {
      await api(`/api/v1/users/${id}/follow/`, { method: "POST" });
      toast("Following — you'll be notified when they go on air.");
      await load();
    } catch (err) {
      toast(err.message, true);
    }
  };

  if (rows.length === 0) return null;
  return (
    <div className="card stack" style={{ gap: 13 }}>
      <h3>Who to follow</h3>
      {rows.map((u) => (
        <div className="rail-row" key={u.id}>
          <Link to={`/users/${u.id}`} className="info">
            <Avatar name={u.display_name} sm />
            <div>
              <div className="nm">{u.display_name}</div>
              <div className="sub">{u.follower_count} followers</div>
            </div>
          </Link>
          <button className="ghost" onClick={() => follow(u.id)}>Follow</button>
        </div>
      ))}
    </div>
  );
}

function TopHosts() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api("/api/v1/leaderboard/").then(setRows).catch(() => {});
  }, []);
  if (rows.length === 0) return null;
  return (
    <div className="card stack" style={{ gap: 13 }}>
      <div className="row between">
        <h3>Top hosts</h3>
        <span className="faint">by gifts</span>
      </div>
      {rows.map((u, i) => (
        <div className="rail-row" key={u.id}>
          <Link to={`/users/${u.id}`} className="info">
            <span className="rail-rank">{i + 1}</span>
            <Avatar name={u.display_name} sm />
            <div>
              <div className="nm">{u.display_name}</div>
              <div className="sub">{u.gift_count} gifts received</div>
            </div>
          </Link>
          <span className="row" style={{ gap: 5, color: "var(--amber)", fontWeight: 700, fontSize: 12.5 }}>
            <CoinIcon size={13} />
            {u.coins_received}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Feed() {
  const [rooms, setRooms] = useState(null);
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState("live");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [newTopic, setNewTopic] = useState("");
  const [goalCoins, setGoalCoins] = useState("");
  const [goalTitle, setGoalTitle] = useState("");
  const [showGoal, setShowGoal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [toastNode, toast] = useToast();

  // debounce search -> query
  useEffect(() => {
    const t = setTimeout(() => setQuery(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ status });
    if (topic) params.set("topic", topic);
    if (query) params.set("search", query);
    const data = await api(`/api/v1/rooms/?${params}`);
    setRooms(data.results);
  }, [topic, status, query]);

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, [load]);

  const topicCounts = useMemo(() => {
    const counts = {};
    (rooms || []).forEach((r) => {
      if (r.topic) counts[r.topic] = (counts[r.topic] || 0) + 1;
    });
    return counts;
  }, [rooms]);

  const createRoom = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api("/api/v1/rooms/", {
        method: "POST",
        body: {
          title,
          topic: newTopic,
          ...(showGoal && goalCoins
            ? { goal_coins: Number(goalCoins), goal_title: goalTitle }
            : {}),
        },
      });
      setTitle("");
      setNewTopic("");
      setGoalCoins("");
      setGoalTitle("");
      setShowGoal(false);
      toast("You're on air — followers have been notified.");
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="page">
      <div className="feed-head">
        <div>
          <div className="kicker" style={{ marginBottom: 8 }}>
            {status === "live" ? `${rooms?.length ?? "—"} rooms on air` : "the archive"}
          </div>
          <h1 className="display">
            {status === "live" ? (
              <>Happening <em>now.</em></>
            ) : (
              <>Past <em>rooms.</em></>
            )}
          </h1>
        </div>
        <div className="row">
          <div className="searchbox">
            <WaveIcon size={14} />
            <input
              placeholder="Search rooms…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button
            className="ghost"
            onClick={() => setStatus(status === "live" ? "ended" : "live")}
          >
            {status === "live" ? "History" : "Back to live"}
          </button>
        </div>
      </div>

      <div className="feed-grid">
        <div className="stack">
          <form onSubmit={createRoom} className="card stack" style={{ gap: 12 }}>
            <div className="go-live" style={{ padding: 0 }}>
              <input
                placeholder="Start a room — what do you want to talk about?"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
              <input
                placeholder="Topic (optional)"
                value={newTopic}
                onChange={(e) => setNewTopic(e.target.value)}
              />
              <button disabled={creating}>{creating ? "Starting…" : "Go on air"}</button>
            </div>
            <div className="row wrap" style={{ gap: 10 }}>
              <button
                type="button"
                className={showGoal ? "" : "ghost"}
                style={{ padding: "7px 14px", fontSize: 12.5 }}
                onClick={() => setShowGoal(!showGoal)}
              >
                <TargetIcon size={13} /> {showGoal ? "Goal on" : "Add a goal"}
              </button>
              {showGoal && (
                <>
                  <input
                    placeholder="What unlocks at the goal?"
                    value={goalTitle}
                    onChange={(e) => setGoalTitle(e.target.value)}
                    style={{ flex: 2, minWidth: 180 }}
                  />
                  <input
                    type="number"
                    min="1"
                    placeholder="coins"
                    value={goalCoins}
                    onChange={(e) => setGoalCoins(e.target.value)}
                    style={{ width: 110 }}
                  />
                  <span className="faint">all-or-nothing · refunded if missed</span>
                </>
              )}
            </div>
          </form>

          <div className="chips">
            <button className={topic === "" ? "on" : ""} onClick={() => setTopic("")}>
              All
            </button>
            {["music", "tech", "gaming", "comedy", "bollywood", "cricket"].map((t) => (
              <button
                key={t}
                className={topic === t ? "on" : ""}
                onClick={() => setTopic(topic === t ? "" : t)}
              >
                {t}
                {topicCounts[t] ? <span className="cnt">{topicCounts[t]}</span> : null}
              </button>
            ))}
          </div>

          {rooms === null ? (
            <div className="grid">
              {[...Array(4)].map((_, i) => <div className="skeleton" key={i} />)}
            </div>
          ) : rooms.length === 0 ? (
            <div className="card empty">
              <div className="display">
                {query ? <>No rooms match <em>"{query}".</em></> : status === "live" ? (
                  <>It's quiet <em>in here.</em></>
                ) : (
                  <>Nothing yet.</>
                )}
              </div>
              {status === "live" && !query && "Be the first — start a room above."}
            </div>
          ) : (
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(255px, 1fr))" }}>
              {rooms.map((r) => (
                <RoomCard key={r.id} room={r} />
              ))}
            </div>
          )}
        </div>

        <div className="rail">
          <WhoToFollow toast={toast} />
          <TopHosts />
          <div className="card" style={{ padding: 18 }}>
            <div className="kicker" style={{ marginBottom: 8 }}>How it works</div>
            <p className="dim" style={{ margin: 0, fontSize: 12.5 }}>
              Join a room to listen. Hosts can invite you on stage — audio is
              peer-to-peer. Send coins as gifts; every coin is tracked on a
              double-entry ledger.
            </p>
          </div>
        </div>
      </div>
      {toastNode}
    </div>
  );
}
