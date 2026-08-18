import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, timeAgo } from "../components/helpers.jsx";

const VERB_TEXT = {
  went_live: "went live",
  new_follower: "started following you",
};

export default function Notifications() {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    api("/api/v1/notifications/")
      .then((d) => {
        setRows(d.results);
        // clears the navbar dot
        if (d.results[0]) localStorage.setItem("notif_seen", d.results[0].created_at);
      })
      .catch(() => {});
  }, []);

  if (rows === null) return <p className="dim">Loading notifications…</p>;

  return (
    <div className="stack">
      <div>
        <h1>Notifications</h1>
        <p className="dim">
          Created asynchronously by the Celery worker when hosts you follow go live.
        </p>
      </div>
      {rows.length === 0 ? (
        <div className="card dim">
          Nothing yet — follow some hosts, and you'll be notified here when they go live.
        </div>
      ) : (
        <div className="card stack">
          {rows.map((n) => (
            <div key={n.id} className="row between">
              <div className="row">
                <Avatar name={n.actor.display_name} sm />
                <span style={{ fontSize: 14.5 }}>
                  <b>{n.actor.display_name}</b> {VERB_TEXT[n.verb] || n.verb}
                </span>
              </div>
              <div className="row">
                {n.room && n.verb === "went_live" && (
                  <Link to={`/rooms/${n.room}`}>
                    <button className="ghost" style={{ padding: "5px 12px", fontSize: 13 }}>
                      Join room
                    </button>
                  </Link>
                )}
                <span className="dim">{timeAgo(n.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
