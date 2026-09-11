import { useNavigate } from "react-router-dom";
import { getSkillIcon } from "../icons";

export default function SkillCard({ skill, selected = false, onClick }) {
  const icon = getSkillIcon(skill);
  const navigate = useNavigate();

  return (
    <article
      className={`skill-store-card${selected ? " skill-store-card-selected" : ""}`}
      style={{ "--skill-accent": icon.accent }}
      onClick={onClick}
    >
      <div className="skill-store-card-top">
        <div className="skill-store-icon" style={{ background: icon.background }}>
          <span aria-hidden="true">{icon.glyph}</span>
        </div>
        <div className="skill-store-card-content">
          <div className="skill-store-card-header">
            <span className="skill-store-name">{skill.name}</span>
            <span className="skill-store-slug">{skill.slug}</span>
          </div>
          <p className="skill-store-description">{skill.description}</p>
        </div>
      </div>
      <div className="skill-store-footer">
        <div className="skill-store-tags">
          {skill.tags.map((tag) => (
            <span key={tag} className="skill-store-tag">
              {tag}
            </span>
          ))}
        </div>
        <div className="skill-store-footer-actions">
          <span className="skill-store-usage">
            {skill.usage_count.toLocaleString()} 次使用
          </span>
          <button
            type="button"
            className="skill-store-try"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/chat/${skill.slug}`);
            }}
          >
            <i className="fa-solid fa-wand-magic-sparkles" aria-hidden="true" />
            <span>试用</span>
          </button>
        </div>
      </div>
    </article>
  );
}