import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchCategories, fetchConversations } from "../api";
import { useAuth } from "../AuthContext";

function NavItem({ icon, emoji, label, active = false, onClick, title }) {
  return (
    <button
      type="button"
      className={`sidebar-item${active ? " sidebar-item-active" : ""}`}
      onClick={onClick}
      title={title || label}
    >
      {emoji ? (
        <span className="sidebar-item-emoji" aria-hidden="true">
          {emoji}
        </span>
      ) : (
        <i className={`fa-solid ${icon} sidebar-item-icon`} aria-hidden="true" />
      )}
      <span className="sidebar-item-label">{label}</span>
    </button>
  );
}

const RECENT_MS = 7 * 24 * 60 * 60 * 1000;

function groupByPeriod(items) {
  const now = Date.now();
  const recent = [];
  const older = [];
  for (const it of items) {
    const ts = Date.parse(it.updated_at || "");
    (ts && now - ts <= RECENT_MS ? recent : older).push(it);
  }
  return { recent, older };
}

function historyTitle(item) {
  const t = (item.title || "").trim();
  return t || item.slug || "新对话";
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [conversations, setConversations] = useState([]);
  const [categories, setCategories] = useState([]);

  const isStore = location.pathname === "/";
  const activeCategory = new URLSearchParams(location.search).get("category") || "";

  // 分类由后端提供，新增/调整分类无需改动前端
  useEffect(() => {
    let cancelled = false;
    fetchCategories()
      .then((d) => {
        if (!cancelled) setCategories(d.items || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchConversations()
      .then((d) => {
        if (!cancelled) setConversations(d.items || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search]);

  // 对话完成后（ChatPage 派发事件）刷新历史列表
  useEffect(() => {
    const handler = () =>
      fetchConversations()
        .then((d) => setConversations(d.items || []))
        .catch(() => {});
    window.addEventListener("conversations-changed", handler);
    return () => window.removeEventListener("conversations-changed", handler);
  }, []);

  const { recent, older } = groupByPeriod(conversations);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark" aria-hidden="true">🧩</span>
        <span>Skill Market</span>
      </div>

      <button type="button" className="sidebar-new-chat" onClick={() => navigate("/")}>
        <i className="fa-solid fa-plus" aria-hidden="true" />
        <span>开启新对话</span>
      </button>

      <div className="sidebar-section">
        <div className="sidebar-section-title">技能市场</div>
        <NavItem
          icon="fa-store"
          label="全部技能"
          active={isStore && !activeCategory}
          onClick={() => navigate("/")}
        />
      </div>

      {categories.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">技能分类</div>
          {categories.map((c) => (
            <NavItem
              key={c.id}
              emoji={c.icon}
              label={c.name}
              title={c.description || c.name}
              active={isStore && activeCategory === c.id}
              onClick={() => navigate(`/?category=${encodeURIComponent(c.id)}`)}
            />
          ))}
        </div>
      )}

      <div className="sidebar-section">
        <div className="sidebar-section-title">历史记录</div>
        {conversations.length === 0 ? (
          <div className="sidebar-history-empty">暂无历史记录</div>
        ) : (
          <>
            {recent.length > 0 && (
              <div className="sidebar-history-group">
                <div className="sidebar-history-period">最近7天</div>
                {recent.map((c) => (
                  <div
                    key={c.cid}
                    className="sidebar-history-item"
                    title={historyTitle(c)}
                    onClick={() => navigate(`/chat/${encodeURIComponent(c.slug)}?cid=${encodeURIComponent(c.cid)}`)}
                  >
                    {historyTitle(c)}
                  </div>
                ))}
              </div>
            )}
            {older.length > 0 && (
              <div className="sidebar-history-group">
                <div className="sidebar-history-period">更早</div>
                {older.map((c) => (
                  <div
                    key={c.cid}
                    className="sidebar-history-item"
                    title={historyTitle(c)}
                    onClick={() => navigate(`/chat/${encodeURIComponent(c.slug)}?cid=${encodeURIComponent(c.cid)}`)}
                  >
                    {historyTitle(c)}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <div className="sidebar-user">
        <div className="sidebar-avatar" aria-hidden="true" />
        <span className="sidebar-user-name">{user?.username || "未登录"}</span>
        <button type="button" className="sidebar-logout" onClick={logout} title="退出登录">
          <i className="fa-solid fa-arrow-right-from-bracket" aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}
