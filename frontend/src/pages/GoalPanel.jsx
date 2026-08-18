import { useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { Avatar } from "../components/helpers.jsx";
import { CheckIcon, LockIcon, TargetIcon } from "../components/Icons.jsx";

/**
 * Goal rooms: pledges sit in escrow until the target is reached (settles to
 * the host) or the room ends short (everyone is refunded automatically).
 */
export default function GoalPanel({ room, pledges, canPledge, onChange, toast }) {
  const [coins, setCoins] = useState(50);
  const [busy, setBusy] = useState(false);

  const pct = Math.min(100, Math.round((room.pledged_coins / room.goal_coins) * 100));
  const reached = room.goal_reached;
  const remaining = Math.max(0, room.goal_coins - room.pledged_coins);
  const backers = pledges.filter((p) => p.status !== "refunded");

  const pledge = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/api/v1/rooms/${room.id}/pledges/`, {
        method: "POST",
        body: { coins: Number(coins) },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      toast(
        Number(coins) >= remaining
          ? "Goal reached — pledges released to the host!"
          : `${coins} coins pledged and held in escrow.`
      );
      onChange();
    } catch (err) {
      toast(
        err.code === "insufficient_balance"
          ? "Not enough coins — top up your wallet."
          : err.message,
        true
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card goal-card">
      <div className="row" style={{ gap: 8 }}>
        <TargetIcon size={15} />
        <h2>{room.goal_title || "Room goal"}</h2>
        {reached && (
          <span className="badge role speaker">
            <CheckIcon size={11} /> funded
          </span>
        )}
      </div>

      <div className="goal-head">
        <div className="amount">
          {room.pledged_coins}
          <span> / {room.goal_coins} coins</span>
        </div>
        <span className="faint">
          {reached ? "released to host" : `${remaining} to go`}
        </span>
      </div>

      <div className={`meter${reached ? " done" : ""}`}>
        <i style={{ width: `${pct}%` }} />
      </div>

      {backers.length > 0 && (
        <div className="backers">
          {backers.slice(0, 8).map((p) => (
            <Avatar key={p.id} name={p.user.display_name} sm />
          ))}
          <span className="faint">
            {backers.length} backer{backers.length === 1 ? "" : "s"}
          </span>
        </div>
      )}

      {canPledge && !reached && (
        <>
          <form onSubmit={pledge} className="goal-pledge">
            <input
              type="number"
              min="1"
              value={coins}
              onChange={(e) => setCoins(e.target.value)}
            />
            <button disabled={busy}>{busy ? "Pledging…" : "Pledge"}</button>
          </form>
          <div className="escrow-note">
            <LockIcon size={13} />
            All-or-nothing: if the goal isn't reached before the room ends,
            every pledge is refunded automatically.
          </div>
        </>
      )}
    </div>
  );
}
