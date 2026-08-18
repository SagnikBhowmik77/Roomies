import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Avatar, timeAgo } from "../components/helpers.jsx";
import { ArrowIcon } from "../components/Icons.jsx";

const VERB_TEXT = {
  went_live: "went on air",
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

  if (rows === null) return <div className="skeleton" />;

  return (
    <div className="page stack" style={{ gap: 14 }}>
      <div>
        <div className="kicker" style={{ marginBottom: 8 }}>Alerts</div>
        <h1 className="display">While you were <em>away.</em></h1>
        <p className="dim" style={{ marginTop: 10 }}>
          Fan-out happens asynchronously on a Celery worker the moment a host
          you follow goes on air.
        </p>
      </div>
      {rows.length === 0 ? (
        <div className="card empty">
          <div className="display">All <em>quiet.</em></div>
          Follow some hosts and you'll hear about it here when they go live.
        </div>
      ) : (
        <div className="card stack" style={{ gap: 16 }}>
          {rows.map((n) => (
            <div key={n.id} className="row between">
              <div className="row" style={{ gap: 11 }}>
                <Avatar name={n.actor.display_name} sm />
                <span style={{ fontSize: 13.5 }}>
                  <b>{n.actor.display_name}</b>{" "}
                  <span className="dim">{VERB_TEXT[n.verb] || n.verb}</span>
                </span>
              </div>
              <div className="row">
                {n.room && n.verb === "went_live" && (
                  <Link to={`/rooms/${n.room}`}>
                    <button className="ghost" style={{ padding: "6px 13px", fontSize: 12 }}>
                      Join <ArrowIcon size={12} />
                    </button>
                  </Link>
                )}
                <span className="faint">{timeAgo(n.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
