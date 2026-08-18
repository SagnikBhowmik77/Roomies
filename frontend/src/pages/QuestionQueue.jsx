import { useState } from "react";
import { Link } from "react-router-dom";
import { api, idempotencyKey } from "../api.js";
import { Avatar, timeAgo } from "./../components/helpers.jsx";
import { CoinIcon, LockIcon, QuestionIcon } from "../components/Icons.jsx";

/**
 * The paid question queue. Stakes are escrowed the moment a question is
 * asked, so the UI can promise refunds honestly.
 */
export default function QuestionQueue({
  roomId,
  questions,
  isHost,
  selfId,
  canAsk,
  onChange,
  toast,
}) {
  const [text, setText] = useState("");
  const [coins, setCoins] = useState(50);
  const [busy, setBusy] = useState(false);

  const pending = questions.filter((q) => q.status === "pending");
  const resolved = questions.filter((q) => q.status !== "pending");

  const ask = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api(`/api/v1/rooms/${roomId}/questions/`, {
        method: "POST",
        body: { text: text.trim(), coins: Number(coins) },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      setText("");
      toast(`${coins} coins held in escrow until it's answered.`);
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

  const resolve = async (question, action) => {
    setBusy(true);
    try {
      await api(`/api/v1/rooms/${roomId}/questions/${question.id}/${action}/`, {
        method: "POST",
      });
      toast(
        action === "answer"
          ? `${question.coins} coins released to the host.`
          : `${question.coins} coins refunded to ${question.asker.display_name}.`
      );
      onChange();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const Row = ({ q, rank }) => (
    <div
      className={`q-item${rank === 0 && q.status === "pending" ? " top" : ""}${
        q.status !== "pending" ? " resolved" : ""
      }`}
    >
      <div className="stake">
        <b>{q.coins}</b>
        <small>{q.status === "pending" ? "held" : q.status === "answered" ? "paid" : "back"}</small>
      </div>
      <div className="body">
        <div className="qtext">{q.text}</div>
        <div className="qmeta">
          <Link to={`/users/${q.asker.id}`} className="row" style={{ gap: 6 }}>
            <Avatar name={q.asker.display_name} sm />
            <span className="faint">{q.asker.display_name}</span>
          </Link>
          <span className="faint">· {timeAgo(q.created_at)}</span>
          {q.status !== "pending" && (
            <span className="badge role">{q.status}</span>
          )}
        </div>
      </div>
      {q.status === "pending" && (isHost || q.asker.id === selfId) && (
        <div className="actions">
          {isHost && (
            <button disabled={busy} onClick={() => resolve(q, "answer")}>
              Answer
            </button>
          )}
          <button className="ghost" disabled={busy} onClick={() => resolve(q, "decline")}>
            {isHost ? "Decline" : "Withdraw"}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="card stack">
      <div className="row between">
        <div className="row" style={{ gap: 8 }}>
          <QuestionIcon size={15} />
          <h2>Question queue</h2>
        </div>
        <span className="faint">
          {pending.length} waiting ·{" "}
          {pending.reduce((sum, q) => sum + q.coins, 0)} coins escrowed
        </span>
      </div>

      {canAsk && (
        <form onSubmit={ask} className="ask-form">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask the host something…"
            maxLength={280}
          />
          <input
            type="number"
            min="1"
            value={coins}
            onChange={(e) => setCoins(e.target.value)}
            title="Coins to stake"
          />
          <button disabled={busy || !text.trim()}>Stake</button>
        </form>
      )}

      {canAsk && (
        <div className="escrow-note">
          <LockIcon size={13} />
          Your coins are held in escrow — released only when the host answers,
          refunded automatically if they decline or the room ends.
        </div>
      )}

      {pending.length === 0 && resolved.length === 0 ? (
        <p className="dim">
          No questions yet. A bigger stake moves you up the queue.
        </p>
      ) : (
        <div className="stack" style={{ gap: 9 }}>
          {pending.map((q, i) => (
            <Row key={q.id} q={q} rank={i} />
          ))}
          {resolved.slice(0, 4).map((q) => (
            <Row key={q.id} q={q} rank={-1} />
          ))}
        </div>
      )}

      {isHost && pending.length > 0 && (
        <p className="faint row" style={{ gap: 6 }}>
          <CoinIcon size={12} />
          Answering the top question pays you {pending[0].coins} coins.
        </p>
      )}
    </div>
  );
}
