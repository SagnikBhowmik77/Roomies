import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, timeAgo, useToast } from "../components/helpers.jsx";
import { Equalizer, UsersIcon } from "../components/Icons.jsx";

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

export default function Feed() {
  const [rooms, setRooms] = useState(null);
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState("live");
  const [title, setTitle] = useState("");
  const [newTopic, setNewTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [toastNode, toast] = useToast();

  const load = useCallback(async () => {
    const params = new URLSearchParams({ status });
    if (topic) params.set("topic", topic);
    const data = await api(`/api/v1/rooms/?${params}`);
    setRooms(data.results);
  }, [topic, status]);

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, [load]);

  const createRoom = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api("/api/v1/rooms/", {
        method: "POST",
        body: { title, topic: newTopic },
      });
      setTitle("");
      setNewTopic("");
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
            {status === "live"
              ? `${rooms?.length ?? "—"} rooms on air`
              : "the archive"}
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
          <button
            className="ghost"
            onClick={() => setStatus(status === "live" ? "ended" : "live")}
          >
            {status === "live" ? "History" : "Back to live"}
          </button>
          <select
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={{ width: 140 }}
          >
            <option value="">All topics</option>
            {["music", "tech", "gaming", "comedy", "bollywood", "cricket"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="stack">
        <form onSubmit={createRoom} className="card go-live">
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
        </form>

        {rooms === null ? (
          <div className="grid">
            {[...Array(6)].map((_, i) => <div className="skeleton" key={i} />)}
          </div>
        ) : rooms.length === 0 ? (
          <div className="card empty">
            <div className="display">
              {status === "live" ? <>It's quiet <em>in here.</em></> : <>Nothing yet.</>}
            </div>
            {status === "live" && "Be the first — start a room above."}
          </div>
        ) : (
          <div className="grid">
            {rooms.map((r) => (
              <RoomCard key={r.id} room={r} />
            ))}
          </div>
        )}
      </div>
      {toastNode}
    </div>
  );
}
