import { Navigate, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Feed from "./pages/Feed.jsx";
import Room from "./pages/Room.jsx";
import Wallet from "./pages/Wallet.jsx";
import Profile from "./pages/Profile.jsx";
import Notifications from "./pages/Notifications.jsx";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <div className="shell dim" style={{ paddingTop: 60 }}>Loading…</div>;

  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }

  return (
    <div className="shell">
      <Navbar />
      <Routes>
        <Route path="/" element={<Feed />} />
        <Route path="/rooms/:id" element={<Room />} />
        <Route path="/wallet" element={<Wallet />} />
        <Route path="/users/:id" element={<Profile />} />
        <Route path="/me" element={<Profile me />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </div>
  );
}
