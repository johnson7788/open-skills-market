import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    const name = username.trim();
    if (!name || busy) return;
    setBusy(true);
    setError("");
    try {
      await login(name);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">Skill Market</div>
        <h1 className="login-title">欢迎回来</h1>
        <p className="login-sub">输入用户名即可进入，你的历史记录会按账号分开保存。</p>

        <label className="login-label" htmlFor="username">
          用户名
        </label>
        <input
          id="username"
          className="login-input"
          type="text"
          autoFocus
          autoComplete="username"
          placeholder="请输入用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        {error ? <div className="login-error">{error}</div> : null}

        <button type="submit" className="login-submit" disabled={busy || !username.trim()}>
          {busy ? "进入中…" : "进入"}
        </button>
      </form>
    </div>
  );
}
