import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, timeAgo, useToast } from "../components/helpers.jsx";

function RoomCard({ room }) {
  return (
    <Link to={`/rooms/${room.id}`}>
      <div className="card room-card">
        <div className="row between">
          <span className={`badge ${room.status}`}>{room.status.toUpperCase()}</span>
          {room.topic && <span className="badge topic">{room.topic}</span>}
        </div>
        <h2>{room.title}</h2>
        <div className="row">
          <Avatar name={room.host.display_name} sm />
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{room.host.display_name}</div>
            <div className="dim">
              {room.active_participants}/{room.max_seats} seats · {timeAgo(room.started_at)}
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function Feed() {
  const [rooms, setRooms] = useState(null);
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [newTopic, setNewTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [toastNode, toast] = useToast();

  const load = useCallback(async () => {
    const params = new URLSearchParams({ status: "live" });
    if (topic) params.set("topic", topic);
    const data = await api(`/api/v1/rooms/?${params}`);
    setRooms(data.results);
  }, [topic]);

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
      toast("You're live! Followers have been notified.");
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="stack">
      <div className="row between">
        <div>
          <h1>Live now</h1>
          <p className="dim">Rooms refresh every 10 seconds.</p>
        </div>
        <select value={topic} onChange={(e) => setTopic(e.target.value)} style={{ width: 160 }}>
          <option value="">All topics</option>
          {["music", "tech", "gaming", "comedy", "bollywood", "cricket"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <form onSubmit={createRoom} className="card row" style={{ gap: 10 }}>
        <input
          placeholder="Start your own room — give it a title…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          style={{ flex: 2 }}
        />
        <input
          placeholder="topic (optional)"
          value={newTopic}
          onChange={(e) => setNewTopic(e.target.value)}
          style={{ flex: 1 }}
        />
        <button disabled={creating}>{creating ? "Starting…" : "Go live"}</button>
      </form>

      {rooms === null ? (
        <p className="dim">Loading rooms…</p>
      ) : rooms.length === 0 ? (
        <p className="dim">No live rooms right now — start one!</p>
      ) : (
        <div className="grid">
          {rooms.map((r) => (
            <RoomCard key={r.id} room={r} />
          ))}
        </div>
      )}
      {toastNode}
    </div>
  );
}
