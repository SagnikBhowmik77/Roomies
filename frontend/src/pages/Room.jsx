import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, idempotencyKey } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Avatar, GIFT_EMOJI, timeAgo, useToast } from "../components/helpers.jsx";
import { useRoomLive } from "../live/useRoomLive.js";

const QUICK_REACTIONS = ["👏", "🔥", "😂", "❤️", "🎉"];

function Seat({ p, isSpeaking, micOn, isHost, canManage, onRole }) {
  return (
    <div className={`seat${isSpeaking ? " speaking" : ""}`}>
      <div style={{ position: "relative" }}>
        <Link to={`/users/${p.user.id}`}>
          <Avatar name={p.user.display_name} lg />
        </Link>
        <span className="mic-tag">{micOn ? "🎙️" : "🔇"}</span>
      </div>
      <span className="name">{p.user.display_name}</span>
      <span className={`badge role ${p.role}`}>
        {p.role === "host" ? "👑 host" : p.role}
      </span>
      {canManage && p.role !== "host" && (
        <div className="host-tools">
          {p.role === "listener" ? (
            <button className="ghost" onClick={() => onRole(p.user.id, "speaker")}>+ Speaker</button>
          ) : (
            <button className="ghost" onClick={() => onRole(p.user.id, "listener")}>Demote</button>
          )}
        </div>
      )}
    </div>
  );
}

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
  const [chatInput, setChatInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toastNode, toast] = useToast();
  const chatEndRef = useRef(null);

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

  const {
    connected,
    messages,
    setMessages,
    sendChat,
    sendReaction,
    reactions,
    speaking,
    micStates,
    micOn,
    toggleMic,
  } = useRoomLive(Number(id), user.id, { onPresence: () => load().catch(() => {}) });

  useEffect(() => {
    load().catch(() => {});
    api("/api/v1/gift-types/").then(setGiftTypes).catch(() => {});
    api(`/api/v1/rooms/${id}/messages/`)
      .then((history) =>
        setMessages(history.map((m) => ({ ...m, event: "chat" })))
      )
      .catch(() => {});
  }, [id, load, setMessages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const topSupporters = useMemo(() => {
    const totals = {};
    gifts.forEach((g) => {
      totals[g.sender.display_name] = (totals[g.sender.display_name] || 0) + g.coins;
    });
    return Object.entries(totals).sort((a, b) => b[1] - a[1]).slice(0, 3);
  }, [gifts]);

  if (!room) return <div className="skeleton" />;

  const me = participants.find((p) => p.user.id === user.id);
  const isHost = room.host.id === user.id;
  const seated = Boolean(me);
  const isLive = room.status === "live";
  const canSpeak = me && (me.role === "host" || me.role === "speaker");

  const act = (fn, okMsg) => async () => {
    setBusy(true);
    try {
      await fn();
      if (okMsg) toast(okMsg);
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const join = act(() => api(`/api/v1/rooms/${id}/join/`, { method: "POST" }));
  const leave = act(() => api(`/api/v1/rooms/${id}/leave/`, { method: "POST" }));
  const end = act(
    () => api(`/api/v1/rooms/${id}/end/`, { method: "POST" }),
    "Room ended."
  );
  const setRole = (userId, role) =>
    act(() =>
      api(`/api/v1/rooms/${id}/participants/${userId}/role/`, {
        method: "POST",
        body: { role },
      })
    )();

  const shareRoom = async () => {
    await navigator.clipboard.writeText(window.location.href);
    toast("Room link copied!");
  };

  const submitChat = (e) => {
    e.preventDefault();
    const text = chatInput.trim();
    if (text) sendChat(text);
    setChatInput("");
  };

  const sendGift = async () => {
    if (!selectedGift || !recipient) return;
    setBusy(true);
    try {
      await api(`/api/v1/rooms/${id}/gifts/`, {
        method: "POST",
        body: { recipient_id: recipient, gift_type_id: selectedGift.id },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      sendReaction(GIFT_EMOJI[selectedGift.name] || "🎁");
      toast(`Sent a ${selectedGift.name}! ${GIFT_EMOJI[selectedGift.name] || "🎁"}`);
      setSelectedGift(null);
      await load();
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

  const micButton = canSpeak && isLive && (
    <button
      className={`mic${micOn ? "" : " off"}`}
      title={micOn ? "Mute microphone" : "Turn on microphone"}
      onClick={() =>
        toggleMic().catch(() =>
          toast("Microphone access was blocked by the browser.", true)
        )
      }
    >
      {micOn ? "🎙️" : "🔇"}
    </button>
  );

  return (
    <div className="stack">
      <div className="card hero row between wrap">
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className={`badge ${room.status}`}>{room.status}</span>
            {room.topic && <span className="badge topic">{room.topic}</span>}
            <span className={`live-pill${connected ? " on" : ""}`}>
              {connected ? "realtime connected" : "connecting…"}
            </span>
          </div>
          <h1>{room.title}</h1>
          <p className="dim">
            Hosted by{" "}
            <Link to={`/users/${room.host.id}`} style={{ color: "#b7a3fa" }}>
              {room.host.display_name}
            </Link>{" "}
            · started {timeAgo(room.started_at)}
          </p>
        </div>
        <div className="row">
          {micButton}
          <button className="ghost" onClick={shareRoom}>Share</button>
          {isLive && !seated && <button onClick={join} disabled={busy}>Join room</button>}
          {isLive && seated && !isHost && (
            <button className="ghost" onClick={leave} disabled={busy}>Leave</button>
          )}
          {isLive && isHost && (
            <button className="danger" onClick={end} disabled={busy}>End room</button>
          )}
          {!isLive && (
            <button className="ghost" onClick={() => navigate("/")}>Back to rooms</button>
          )}
        </div>
      </div>

      <div className="room-layout">
        <div className="stack">
          <div className="card stack">
            <div className="row between">
              <h2>On stage</h2>
              <span className="dim">{participants.length}/{room.max_seats} seats</span>
            </div>
            <div className="stage">
              {participants.map((p) => (
                <Seat
                  key={p.user.id}
                  p={p}
                  isSpeaking={Boolean(speaking[p.user.id])}
                  micOn={Boolean(micStates[p.user.id])}
                  isHost={p.role === "host"}
                  canManage={isHost && isLive}
                  onRole={setRole}
                />
              ))}
            </div>
            {canSpeak && isLive && (
              <p className="faint">
                🎙️ You can speak in this room — audio streams peer-to-peer via WebRTC.
                {micOn ? " You're live." : " Your mic is off."}
              </p>
            )}
            {seated && !canSpeak && isLive && (
              <p className="faint">
                You're listening. Ask the host to promote you to speaker to talk.
              </p>
            )}
          </div>

          {isLive && seated && (
            <div className="card stack">
              <h2>Send a gift 🎁</h2>
              <div className="row wrap">
                {giftTypes.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    className={`gift-option${selectedGift?.id === g.id ? " selected" : ""}`}
                    onClick={() => setSelectedGift(g)}
                  >
                    <span className="emoji">{GIFT_EMOJI[g.name] || "🎁"}</span>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>{g.name}</span>
                    <span className="price">🪙 {g.coins}</span>
                  </button>
                ))}
              </div>
              <div className="row">
                <select
                  value={recipient ?? ""}
                  onChange={(e) => setRecipient(Number(e.target.value))}
                  style={{ maxWidth: 250 }}
                >
                  {participants
                    .filter((p) => p.user.id !== user.id)
                    .map((p) => (
                      <option key={p.user.id} value={p.user.id}>
                        to {p.user.display_name} {p.role === "host" ? "👑" : ""}
                      </option>
                    ))}
                </select>
                <button onClick={sendGift} disabled={busy || !selectedGift}>
                  {selectedGift ? `Send ${selectedGift.name}` : "Pick a gift"}
                </button>
              </div>
            </div>
          )}

          <div className="card stack">
            <div className="row between">
              <h2>Gift history</h2>
              {topSupporters.length > 0 && (
                <span className="dim">
                  Top supporters:{" "}
                  {topSupporters.map(([name, coins], i) => (
                    <span key={name}>
                      {i > 0 && " · "}
                      {["🥇", "🥈", "🥉"][i]} {name} ({coins})
                    </span>
                  ))}
                </span>
              )}
            </div>
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
                      <td className="faint">{timeAgo(g.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="card chat">
          <div className="row between" style={{ marginBottom: 12 }}>
            <h2>Live chat</h2>
            <span className="faint">{messages.length} messages</span>
          </div>
          <div className="msgs">
            {messages.length === 0 && (
              <p className="dim">Say hi — messages appear instantly for everyone here.</p>
            )}
            {messages.map((m, i) => (
              <div className="msg" key={m.id ?? i}>
                <Avatar name={m.user.display_name} sm />
                <div className="bubble">
                  <span className="who">{m.user.display_name}</span>
                  {m.text}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          {seated && isLive && (
            <>
              <form onSubmit={submitChat}>
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Message the room…"
                  maxLength={500}
                />
                <button disabled={!connected}>Send</button>
              </form>
              <div className="quick">
                {QUICK_REACTIONS.map((emoji) => (
                  <button key={emoji} type="button" onClick={() => sendReaction(emoji)}>
                    {emoji}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="float-reactions">
        {reactions.map((r) => (
          <div className="fr" key={r.id}>
            {r.emoji} <small>{r.name}</small>
          </div>
        ))}
      </div>
      {toastNode}
    </div>
  );
}
