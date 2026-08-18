import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, idempotencyKey } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Avatar, GIFT_EMOJI, timeAgo, useToast } from "../components/helpers.jsx";

export default function Room() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [room, setRoom] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [giftTypes, setGiftTypes] = useState([]);
  const [gifts, setGifts] = useState([]);
  const [selectedGift, setSelectedGift] = useState(null);
  const [recipient, setRecipient] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toastNode, toast] = useToast();

  const load = useCallback(async () => {
    const [r, p, g] = await Promise.all([
      api(`/api/v1/rooms/${id}/`),
      api(`/api/v1/rooms/${id}/participants/`),
      api(`/api/v1/rooms/${id}/gifts/history/`),
    ]);
    setRoom(r);
    setParticipants(p);
    setGifts(g.results);
    setRecipient((prev) => prev ?? r.host.id);
  }, [id]);

  useEffect(() => {
    load().catch(() => {});
    api("/api/v1/gift-types/").then(setGiftTypes).catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 8000);
    return () => clearInterval(t);
  }, [load]);

  if (!room) return <p className="dim">Loading room…</p>;

  const isHost = room.host.id === user.id;
  const seated = participants.some((p) => p.user.id === user.id);
  const isLive = room.status === "live";

  const act = (fn) => async () => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const join = act(() => api(`/api/v1/rooms/${id}/join/`, { method: "POST" }));
  const leave = act(() => api(`/api/v1/rooms/${id}/leave/`, { method: "POST" }));
  const end = act(async () => {
    await api(`/api/v1/rooms/${id}/end/`, { method: "POST" });
    toast("Room ended.");
  });

  const sendGift = async () => {
    if (!selectedGift || !recipient) return;
    setBusy(true);
    try {
      // fresh key per send; retries of the SAME send would reuse the key
      await api(`/api/v1/rooms/${id}/gifts/`, {
        method: "POST",
        body: { recipient_id: recipient, gift_type_id: selectedGift.id },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      toast(`Sent a ${selectedGift.name}! ${GIFT_EMOJI[selectedGift.name] || "🎁"}`);
      setSelectedGift(null);
      await load();
    } catch (err) {
      toast(err.code === "insufficient_balance" ? "Not enough coins — top up your wallet." : err.message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="row between">
        <div>
          <div className="row" style={{ marginBottom: 6 }}>
            <span className={`badge ${room.status}`}>{room.status.toUpperCase()}</span>
            {room.topic && <span className="badge topic">{room.topic}</span>}
          </div>
          <h1>{room.title}</h1>
          <p className="dim">
            Hosted by{" "}
            <Link to={`/users/${room.host.id}`} style={{ color: "var(--accent)" }}>
              {room.host.display_name}
            </Link>{" "}
            · started {timeAgo(room.started_at)}
          </p>
        </div>
        <div className="row">
          {isLive && !seated && (
            <button onClick={join} disabled={busy}>Join room</button>
          )}
          {isLive && seated && !isHost && (
            <button className="ghost" onClick={leave} disabled={busy}>Leave</button>
          )}
          {isLive && isHost && (
            <button className="danger" onClick={end} disabled={busy}>End room</button>
          )}
          {!isLive && <button className="ghost" onClick={() => navigate("/")}>Back to rooms</button>}
        </div>
      </div>

      <div className="card stack">
        <div className="row between">
          <h2>In the room</h2>
          <span className="dim">{participants.length}/{room.max_seats} seats</span>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" }}>
          {participants.map((p) => (
            <Link key={p.user.id} to={`/users/${p.user.id}`}>
              <div className="row">
                <Avatar name={p.user.display_name} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{p.user.display_name}</div>
                  <div className="dim">{p.role}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {isLive && seated && (
        <div className="card stack">
          <h2>Send a gift 🎁</h2>
          <div className="row" style={{ flexWrap: "wrap" }}>
            {giftTypes.map((g) => (
              <button
                key={g.id}
                type="button"
                className={`gift-option${selectedGift?.id === g.id ? " selected" : ""}`}
                onClick={() => setSelectedGift(g)}
              >
                <span className="emoji">{GIFT_EMOJI[g.name] || "🎁"}</span>
                <span>{g.name}</span>
                <span className="price">🪙 {g.coins}</span>
              </button>
            ))}
          </div>
          <div className="row">
            <select value={recipient ?? ""} onChange={(e) => setRecipient(Number(e.target.value))} style={{ maxWidth: 260 }}>
              {participants
                .filter((p) => p.user.id !== user.id)
                .map((p) => (
                  <option key={p.user.id} value={p.user.id}>
                    to {p.user.display_name} {p.role === "host" ? "(host)" : ""}
                  </option>
                ))}
            </select>
            <button onClick={sendGift} disabled={busy || !selectedGift}>
              {busy ? "Sending…" : selectedGift ? `Send ${selectedGift.name}` : "Pick a gift"}
            </button>
          </div>
        </div>
      )}

      <div className="card stack">
        <h2>Gift history</h2>
        {gifts.length === 0 ? (
          <p className="dim">No gifts yet. Be the first!</p>
        ) : (
          <table className="ledger">
            <tbody>
              {gifts.map((g) => (
                <tr key={g.id}>
                  <td>{GIFT_EMOJI[g.gift_type.name] || "🎁"} {g.gift_type.name}</td>
                  <td>{g.sender.display_name} → {g.recipient.display_name}</td>
                  <td className="delta-pos">🪙 {g.coins}</td>
                  <td className="dim">{timeAgo(g.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {toastNode}
    </div>
  );
}
