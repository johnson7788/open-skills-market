import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import SkillStorePage from "./pages/SkillStorePage";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./AuthContext";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="app-loading">加载中…</div>;
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<SkillStorePage />} />
          <Route path="/skills" element={<Navigate to="/" replace />} />
          <Route path="/chat/:slug" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
