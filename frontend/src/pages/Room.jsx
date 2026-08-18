import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, idempotencyKey } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Avatar, GIFT_EMOJI, timeAgo, useToast } from "../components/helpers.jsx";
import {
  GiftIcon,
  MicIcon,
  MicOffIcon,
  SendIcon,
  ShareIcon,
  UsersIcon,
  WaveIcon,
} from "../components/Icons.jsx";
import { useRoomLive } from "../live/useRoomLive.js";
import GoalPanel from "./GoalPanel.jsx";
import QuestionQueue from "./QuestionQueue.jsx";

const QUICK_REACTIONS = ["👏", "🔥", "😂", "❤️", "🎉"];
const SPLIT = "__split__";

function Seat({ p, isSpeaking, micOn, canManage, onRole }) {
  return (
    <div className={`seat${isSpeaking ? " speaking" : ""}`}>
      <Link to={`/users/${p.user.id}`}>
        <Avatar name={p.user.display_name} lg>
          <span className={`mic-tag${micOn ? " on" : ""}`}>
            {micOn ? <MicIcon size={11} /> : <MicOffIcon size={11} />}
          </span>
        </Avatar>
      </Link>
      <span className="name">{p.user.display_name}</span>
      <span className={`badge role ${p.role}`}>{p.role}</span>
      {canManage && p.role !== "host" && (
        <div className="host-tools">
          {p.role === "listener" ? (
            <button className="ghost" onClick={() => onRole(p.user.id, "speaker")}>
              Invite up
            </button>
          ) : (
            <button className="ghost" onClick={() => onRole(p.user.id, "listener")}>
              Move down
            </button>
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
  const [questions, setQuestions] = useState([]);
  const [pledges, setPledges] = useState([]);
  const [selectedGift, setSelectedGift] = useState(null);
  const [recipient, setRecipient] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toastNode, toast] = useToast();
  const chatEndRef = useRef(null);

  const load = useCallback(async () => {
    const [r, p, g, q] = await Promise.all([
      api(`/api/v1/rooms/${id}/`),
      api(`/api/v1/rooms/${id}/participants/`),
      api(`/api/v1/rooms/${id}/gifts/history/`),
      api(`/api/v1/rooms/${id}/questions/`),
    ]);
    setRoom(r);
    setParticipants(p);
    setGifts(g.results);
    setQuestions(q);
    setRecipient((prev) => prev ?? SPLIT);
    if (r.goal_coins) {
      api(`/api/v1/rooms/${id}/pledges/`).then(setPledges).catch(() => {});
    }
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
    captions,
    captionsOn,
    toggleCaptions,
    recording,
    startRecording,
    stopRecording,
  } = useRoomLive(Number(id), user.id, { onPresence: () => load().catch(() => {}) });

  // countdown for time-boxed rooms
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    load().catch(() => {});
    api("/api/v1/gift-types/").then(setGiftTypes).catch(() => {});
    api(`/api/v1/rooms/${id}/messages/`)
      .then((history) => setMessages(history.map((m) => ({ ...m, event: "chat" }))))
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

  if (!room) return <div className="skeleton" style={{ height: 420 }} />;

  const me = participants.find((p) => p.user.id === user.id);
  const onStage = participants.filter((p) => p.role !== "listener");
  const isHost = room.host.id === user.id;
  const seated = Boolean(me);
  const isLive = room.status === "live";
  const canSpeak = me && (me.role === "host" || me.role === "speaker");

  const secondsLeft = room.ends_at
    ? Math.max(0, Math.floor((new Date(room.ends_at) - now) / 1000))
    : null;
  const countdown =
    secondsLeft === null
      ? null
      : `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;

  const onToggleCaptions = () => {
    try {
      toggleCaptions();
    } catch (err) {
      toast(err.message, true);
    }
  };

  const onToggleRecording = async () => {
    try {
      if (recording) {
        const result = await stopRecording();
        toast(`Recording saved (${result.seconds}s).`);
        await load();
      } else {
        startRecording();
        toast("Recording — every live mic is being mixed in.");
      }
    } catch (err) {
      toast(err.message, true);
    }
  };

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
  const end = act(() => api(`/api/v1/rooms/${id}/end/`, { method: "POST" }), "Room ended.");
  const setRole = (userId, role) =>
    act(() =>
      api(`/api/v1/rooms/${id}/participants/${userId}/role/`, {
        method: "POST",
        body: { role },
      })
    )();

  const shareRoom = async () => {
    await navigator.clipboard.writeText(window.location.href);
    toast("Room link copied.");
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
        body: {
          // omitting recipient_id makes it a room gift, split across the stage
          ...(recipient === SPLIT ? {} : { recipient_id: recipient }),
          gift_type_id: selectedGift.id,
        },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      sendReaction(GIFT_EMOJI[selectedGift.name] || "🎁");
      toast(`${GIFT_EMOJI[selectedGift.name] || "🎁"} ${selectedGift.name} sent`);
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

  return (
    <div className="page">
      <div className="card room-hero">
        <div className="row between wrap" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="row" style={{ marginBottom: 12 }}>
              <span className={`badge ${room.status}`}>
                {isLive ? "On air" : "Ended"}
              </span>
              {room.topic && <span className="badge topic">{room.topic}</span>}
              <span className={`live-pill${connected ? " on" : ""}`}>
                {connected ? "live" : "connecting"}
              </span>
              {recording && (
                <span className="row" style={{ gap: 6 }}>
                  <span className="rec-dot" />
                  <span className="kicker" style={{ color: "var(--live)" }}>rec</span>
                </span>
              )}
            </div>
            <h1 className="display" style={{ fontSize: 34 }}>{room.title}</h1>
            <p className="dim" style={{ marginTop: 8 }}>
              Hosted by{" "}
              <Link to={`/users/${room.host.id}`} style={{ color: "var(--amber)", fontWeight: 600 }}>
                {room.host.display_name}
              </Link>{" "}
              · started {timeAgo(room.started_at)}
            </p>
          </div>
          <div className="row">
            {isLive && countdown && (
              <span className={`countdown${secondsLeft < 120 ? " urgent" : ""}`}>
                {countdown}
                <small>left</small>
              </span>
            )}
            {canSpeak && isLive && (
              <button
                className={`mic${micOn ? "" : " off"}`}
                title={micOn ? "Mute" : "Unmute"}
                onClick={() =>
                  toggleMic().catch(() =>
                    toast("Microphone access was blocked by the browser.", true)
                  )
                }
              >
                {micOn ? <MicIcon size={18} /> : <MicOffIcon size={18} />}
              </button>
            )}
            {isLive && seated && (
              <button
                className={captionsOn ? "" : "ghost"}
                onClick={onToggleCaptions}
                title="Live captions (speech recognition runs in your browser)"
              >
                <WaveIcon size={14} /> CC
              </button>
            )}
            {isLive && isHost && (
              <button
                className={recording ? "danger" : "ghost"}
                onClick={onToggleRecording}
                title="Record the room"
              >
                {recording ? "Stop rec" : "Record"}
              </button>
            )}
            {(room.has_recording || !isLive) && (
              <Link to={`/rooms/${room.id}/replay`}>
                <button className="ghost">Replay</button>
              </Link>
            )}
            <button className="ghost icon-btn" onClick={shareRoom} title="Copy room link">
              <ShareIcon size={15} />
            </button>
            {isLive && !seated && <button onClick={join} disabled={busy}>Join room</button>}
            {isLive && seated && !isHost && (
              <button className="ghost" onClick={leave} disabled={busy}>Leave</button>
            )}
            {isLive && isHost && (
              <button className="danger" onClick={end} disabled={busy}>End room</button>
            )}
            {!isLive && (
              <button className="ghost" onClick={() => navigate("/")}>All rooms</button>
            )}
          </div>
        </div>
      </div>

      <div className="room-layout">
        <div className="stack">
          <div className="card stack">
            <div className="row between">
              <h2>On stage</h2>
              <span className="faint row" style={{ gap: 6 }}>
                <UsersIcon size={13} />
                {participants.length}/{room.max_seats}
              </span>
            </div>
            <div className="stage">
              {participants.map((p) => (
                <Seat
                  key={p.user.id}
                  p={p}
                  isSpeaking={Boolean(speaking[p.user.id])}
                  micOn={Boolean(micStates[p.user.id])}
                  canManage={isHost && isLive}
                  onRole={setRole}
                />
              ))}
            </div>
            {canSpeak && isLive && (
              <p className="faint">
                Audio streams peer-to-peer over WebRTC.{" "}
                {micOn ? "You're live." : "Your mic is off."}
              </p>
            )}
            {seated && !canSpeak && isLive && (
              <p className="faint">
                You're in the audience — the host can invite you up to speak.
              </p>
            )}
          </div>

          {isLive && seated && (
            <div className="card stack">
              <div className="row" style={{ gap: 8 }}>
                <GiftIcon size={15} />
                <h2>Send a gift</h2>
              </div>
              <div className="row wrap">
                {giftTypes.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    className={`gift-option${selectedGift?.id === g.id ? " selected" : ""}`}
                    onClick={() => setSelectedGift(g)}
                  >
                    <span className="emoji">{GIFT_EMOJI[g.name] || "🎁"}</span>
                    <span className="g-name">{g.name}</span>
                    <span className="price">{g.coins}</span>
                  </button>
                ))}
              </div>
              <div className="row">
                <select
                  value={recipient ?? SPLIT}
                  onChange={(e) =>
                    setRecipient(
                      e.target.value === SPLIT ? SPLIT : Number(e.target.value)
                    )
                  }
                  style={{ maxWidth: 260 }}
                >
                  <option value={SPLIT}>
                    Split across the stage ({onStage.length})
                  </option>
                  {participants
                    .filter((p) => p.user.id !== user.id)
                    .map((p) => (
                      <option key={p.user.id} value={p.user.id}>
                        to {p.user.display_name}{p.role === "host" ? " — host" : ""}
                      </option>
                    ))}
                </select>
                <button onClick={sendGift} disabled={busy || !selectedGift}>
                  {selectedGift ? `Send ${selectedGift.name}` : "Pick a gift"}
                </button>
              </div>
              {recipient === SPLIT && (
                <p className="faint">
                  Room gifts are divided between everyone on stage in
                  proportion to their time speaking — co-hosting pays.
                </p>
              )}
            </div>
          )}

          {room.goal_coins ? (
            <GoalPanel
              room={room}
              pledges={pledges}
              canPledge={isLive && seated && !isHost}
              onChange={load}
              toast={toast}
            />
          ) : null}

          <QuestionQueue
            roomId={room.id}
            questions={questions}
            isHost={isHost}
            selfId={user.id}
            canAsk={isLive && seated && !isHost}
            onChange={load}
            toast={toast}
          />

          <div className="card stack">
            <div className="row between wrap">
              <h2>Gift history</h2>
              {topSupporters.length > 0 && (
                <span className="faint">
                  Top:{" "}
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
              <p className="dim">No gifts yet — be the first.</p>
            ) : (
              <table className="ledger">
                <tbody>
                  {gifts.map((g) => (
                    <tr key={g.id}>
                      <td>{GIFT_EMOJI[g.gift_type.name] || "🎁"} {g.gift_type.name}</td>
                      <td className="dim">
                        {g.sender.display_name} →{" "}
                        {/* recipient is null for room gifts: split across the stage */}
                        {g.recipient ? (
                          g.recipient.display_name
                        ) : (
                          <span style={{ color: "var(--amber)" }}>the stage</span>
                        )}
                      </td>
                      <td className="delta-pos">{g.coins}</td>
                      <td className="faint" style={{ textAlign: "right" }}>{timeAgo(g.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="card chat">
          <div className="row between" style={{ marginBottom: 14 }}>
            <h2>Live chat</h2>
            <span className="faint">{messages.length}</span>
          </div>
          <div className="msgs">
            {messages.length === 0 && (
              <p className="dim">Say hi — everyone in the room sees it instantly.</p>
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
                <button disabled={!connected} title="Send">
                  <SendIcon size={15} />
                </button>
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

      {captionsOn && (
        <div className="caption-bar">
          {captions.length === 0 ? (
            <p className="faint" style={{ margin: 0 }}>
              Listening… captions appear here and are shared with the room.
            </p>
          ) : (
            captions.slice(-4).map((c) => (
              <div className="line" key={c.id}>
                <b>{c.who}:</b> {c.text}
              </div>
            ))
          )}
        </div>
      )}

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
