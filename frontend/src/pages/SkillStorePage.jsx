import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchSkills } from "../api";
import SkillCard from "../components/SkillCard";

const TABS = [
  { key: "all", label: "全部技能" },
  { key: "used", label: "我的使用项目" },
];

export default function SkillStorePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const category = searchParams.get("category") || "";

  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("all");
  const [selectedSlug, setSelectedSlug] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    fetchSkills({ search, tab, category })
      .then((payload) => {
        setData(payload);
        if (!selectedSlug && payload.items.length > 0) {
          setSelectedSlug(payload.items[0].slug);
        }
      })
      .catch(() => setError("技能列表加载失败"));
  }, [search, tab, category]);

  function selectCategory(id) {
    const next = new URLSearchParams(searchParams);
    if (id) next.set("category", id);
    else next.delete("category");
    setSearchParams(next, { replace: true });
  }

  const categories = data?.categories || [];

  return (
    <div className="skill-store-page">
      {/* ── Header ── */}
      <div className="skill-store-header">
        <h1 className="skill-store-title">Skill 商店</h1>
        <p className="skill-store-subtitle">
          浏览、搜索并试用可被智能体直接执行的 SKILL.md 技能
        </p>
        <div className="skill-store-controls">
          <div className="skill-store-tabs">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                className={`skill-store-tab${tab === key ? " skill-store-tab-active" : ""}`}
                onClick={() => setTab(key)}
              >
                {label}
                {data ? (
                  <span className="skill-store-tab-count">（{data.tabs[key] ?? 0}）</span>
                ) : null}
              </button>
            ))}
          </div>
          <div className="skill-store-search-wrap">
            <i className="skill-store-search-icon fa-solid fa-magnifying-glass" aria-hidden="true" />
            <input
              className="skill-store-search"
              type="text"
              placeholder="搜索 Skill 名称或描述..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {categories.length > 0 && (
          <div className="skill-store-categories">
            <button
              type="button"
              className={`skill-store-category${category ? "" : " skill-store-category-active"}`}
              onClick={() => selectCategory("")}
            >
              全部分类
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                title={c.description || c.name}
                className={`skill-store-category${
                  category === c.id ? " skill-store-category-active" : ""
                }`}
                onClick={() => selectCategory(c.id)}
              >
                <span aria-hidden="true">{c.icon}</span>
                <span>{c.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {error ? <div className="feedback-card">{error}</div> : null}
      {!data && !error ? <div className="feedback-card">正在加载技能列表...</div> : null}

      {data ? (
        <div className="skill-store-main">
          {data.total === 0 ? (
            <div className="feedback-card">
              没有找到匹配的技能。把技能目录放到 <code>backend/app/skills/</code> 下，
              或配置 <code>SKILLHUB_URL</code> 从 SkillHub 同步。
            </div>
          ) : (
            <div className="skill-store-grid">
              {data.items.map((skill) => (
                <SkillCard
                  key={skill.slug}
                  skill={skill}
                  selected={selectedSlug === skill.slug}
                  onClick={() => setSelectedSlug(skill.slug)}
                />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
