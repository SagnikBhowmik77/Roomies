import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { timeAgo } from "../components/helpers.jsx";
import { GiftIcon, QuestionIcon, SendIcon, WaveIcon } from "../components/Icons.jsx";

const KIND_META = {
  chat: { icon: SendIcon, label: "chat" },
  caption: { icon: WaveIcon, label: "said" },
  gift: { icon: GiftIcon, label: "gift" },
  question: { icon: QuestionIcon, label: "question" },
};

const clock = (seconds) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export default function Replay() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [at, setAt] = useState(0); // playhead, in seconds
  const audioRef = useRef(null);

  useEffect(() => {
    api(`/api/v1/rooms/${id}/replay/`).then(setData).catch(() => {});
  }, [id]);

  const rows = useMemo(() => {
    if (!data) return [];
    return filter === "all"
      ? data.timeline
      : data.timeline.filter((r) => r.kind === filter);
  }, [data, filter]);

  if (!data) return <div className="skeleton" />;

  const { room, audio_url: audioUrl, timeline } = data;
  const counts = timeline.reduce((acc, r) => {
    acc[r.kind] = (acc[r.kind] || 0) + 1;
    return acc;
  }, {});

  const seek = (seconds) => {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds;
      audioRef.current.play().catch(() => {});
    }
    setAt(seconds);
  };

  return (
    <div className="page stack" style={{ gap: 14 }}>
      <div>
        <div className="kicker" style={{ marginBottom: 8 }}>Replay</div>
        <h1 className="display">{room.title}</h1>
        <p className="dim" style={{ marginTop: 8 }}>
          Hosted by{" "}
          <Link to={`/users/${room.host.id}`} style={{ color: "var(--amber)", fontWeight: 600 }}>
            {room.host.display_name}
          </Link>{" "}
          · {timeAgo(room.started_at)} ·{" "}
          <Link to={`/rooms/${room.id}`} style={{ textDecoration: "underline" }}>
            back to the room
          </Link>
        </p>
      </div>

      {audioUrl ? (
        <div className="card stack" style={{ gap: 12 }}>
          <div className="row between">
            <h2>Room audio</h2>
            <span className="faint">{clock(data.duration_seconds)}</span>
          </div>
          <audio
            ref={audioRef}
            src={audioUrl}
            controls
            style={{ width: "100%" }}
            onTimeUpdate={(e) => setAt(e.target.currentTime)}
          />
          <p className="faint">
            Mixed in the host's browser from every live stream and uploaded
            once — the server never sat in the audio path.
          </p>
        </div>
      ) : (
        <div className="card" style={{ padding: 18 }}>
          <p className="dim" style={{ margin: 0 }}>
            No audio was captured for this room — the transcript and timeline
            below are still complete.
          </p>
        </div>
      )}

      <div className="chips">
        <button className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>
          Everything <span className="cnt">{timeline.length}</span>
        </button>
        {Object.keys(KIND_META).map((kind) =>
          counts[kind] ? (
            <button
              key={kind}
              className={filter === kind ? "on" : ""}
              onClick={() => setFilter(kind)}
            >
              {KIND_META[kind].label} <span className="cnt">{counts[kind]}</span>
            </button>
          ) : null
        )}
      </div>

      <div className="card stack" style={{ gap: 0 }}>
        {rows.length === 0 ? (
          <p className="dim">Nothing recorded for this filter.</p>
        ) : (
          rows.map((row, i) => {
            const Icon = KIND_META[row.kind]?.icon || SendIcon;
            const active = audioUrl && at >= row.at && at < (rows[i + 1]?.at ?? 1e9);
            return (
              <button
                key={`${row.kind}-${i}`}
                className={`tl-row${active ? " now" : ""}`}
                onClick={() => seek(row.at)}
                title={audioUrl ? "Jump to this moment" : undefined}
              >
                <span className="tl-at">{clock(row.at)}</span>
                <span className={`tl-icon k-${row.kind}`}>
                  <Icon size={13} />
                </span>
                <span className="tl-body">
                  <b>{row.who}</b> {row.text}
                </span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
