import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Avatar, useToast } from "../components/helpers.jsx";

function UserList({ title, rows }) {
  return (
    <div className="card stack" style={{ flex: 1, gap: 12 }}>
      <div className="row between">
        <h3>{title}</h3>
        <span className="faint">{rows.length}</span>
      </div>
      {rows.length === 0 && <p className="faint">Nobody yet.</p>}
      {rows.map(({ user: u }) => (
        <Link key={u.id} to={`/users/${u.id}`}>
          <div className="row" style={{ gap: 10 }}>
            <Avatar name={u.display_name} sm />
            <span style={{ fontSize: 13.5, fontWeight: 600 }}>{u.display_name}</span>
          </div>
        </Link>
      ))}
    </div>
  );
}

export default function Profile({ me = false }) {
  const params = useParams();
  const { user: self, reloadUser } = useAuth();
  const userId = me ? self.id : Number(params.id);
  const isSelf = userId === self.id;

  const [profile, setProfile] = useState(null);
  const [followers, setFollowers] = useState([]);
  const [following, setFollowing] = useState([]);
  const [isFollowing, setIsFollowing] = useState(false);
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [busy, setBusy] = useState(false);
  const [toastNode, toast] = useToast();

  const load = useCallback(async () => {
    const [p, fw, fg] = await Promise.all([
      api(isSelf ? "/api/v1/me/" : `/api/v1/users/${userId}/`),
      api(`/api/v1/users/${userId}/followers/`),
      api(`/api/v1/users/${userId}/following/`),
    ]);
    setProfile(p);
    setFollowers(fw.results);
    setFollowing(fg.results);
    setIsFollowing(fw.results.some((r) => r.user.id === self.id));
    setName(p.display_name || "");
    setCountry(p.country || "");
  }, [userId, isSelf, self.id]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  if (!profile) return <div className="skeleton" />;

  const toggleFollow = async () => {
    setBusy(true);
    try {
      await api(`/api/v1/users/${userId}/follow/`, {
        method: isFollowing ? "DELETE" : "POST",
      });
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/api/v1/me/", {
        method: "PATCH",
        body: { display_name: name, country: country.toUpperCase() },
      });
      toast("Profile saved.");
      await Promise.all([load(), reloadUser()]);
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page stack" style={{ gap: 14 }}>
      <div className="card row between wrap" style={{ padding: 28 }}>
        <div className="row" style={{ gap: 18 }}>
          <Avatar name={profile.display_name} lg />
          <div>
            <h1 className="display" style={{ fontSize: 32 }}>
              {profile.display_name || "Unnamed"}
            </h1>
            <p className="faint" style={{ marginTop: 4 }}>
              {profile.country && `${profile.country} · `}
              joined {new Date(profile.created_at).toLocaleDateString()}
              {" · "}{followers.length} followers · {following.length} following
            </p>
          </div>
        </div>
        {!isSelf && (
          <button className={isFollowing ? "ghost" : ""} onClick={toggleFollow} disabled={busy}>
            {isFollowing ? "Following ✓" : "Follow"}
          </button>
        )}
      </div>

      {isSelf && (
        <form onSubmit={saveProfile} className="card row wrap" style={{ gap: 10 }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Display name"
            style={{ flex: 2, minWidth: 160 }}
          />
          <input
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Country (IN)"
            maxLength={2}
            style={{ flex: 1, minWidth: 90 }}
          />
          <button disabled={busy}>Save</button>
        </form>
      )}

      <div className="row wrap" style={{ alignItems: "stretch" }}>
        <UserList title="Followers" rows={followers} />
        <UserList title="Following" rows={following} />
      </div>
      {toastNode}
    </div>
  );
}
