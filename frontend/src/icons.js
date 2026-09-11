// 技能图标：确定性「唯一」图标系统
//
// 目标：让每个 skill 都有自己专属的图标，且无需为不断增长的技能列表逐个手工维护映射表。
//
// 原理（三步，全部由 slug 决定，天然稳定、可重复）：
//   1. 把 slug 用 FNV-1a 哈希成 32 位整数；
//   2. 用该整数从「手工语义表 → 通用 emoji 池」确定性选出一个 glyph；
//   3. 用同一整数生成唯一色相，作为图标砖的底色。
// 于是：同一 slug 永远得到同一图标 + 同一底色；不同 slug 底色几乎必然不同 ——
// 即使两个 skill 偶然撞了同一个 glyph，底色也不同，视觉上绝不重复。

// ── 稳定哈希（FNV-1a，32 位）────────────────────────────────────
function hash32(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// ── 手工精选：常见技能的语义 emoji（key = slug）───────────────────
const SLUG_EMOJI = {
  "hello-skill": "👋",
  "text-stats": "🧮",
  "csv-to-markdown": "📊",
  "pdf": "📕",
  "pdf-processing": "📄",
  "docx": "📘",
  "pptx": "📙",
  "arxiv-search": "📚",
  "searxng": "🔎",
  "find-skills": "🔍",
  "skill-creator": "🛠️",
  "image-recognize": "👁️",
  "frontend-design": "🎨",
  "weather": "🌤️",
  "diagram-maker": "📐",
  "data-viz-plots": "📉",
  "statistical-analysis": "📈",
  "automation-workflows": "⚙️",
  "de-ai-writing-cn": "🖊️",
};

// ── 通用 emoji 池（未收录的技能从这里确定性取值）─────────────────
const EMOJI_POOL = [
  "🧩", "🛠️", "⚙️", "🔧", "🔩", "📦", "🧰", "📎", "📌", "📍",
  "📄", "📃", "📑", "🗂️", "🗃️", "🗄️", "📕", "📘", "📙", "📚",
  "📖", "📝", "📋", "🧾", "🗒️", "🖊️", "✍️", "🖥️", "💻", "⌨️",
  "🤖", "🧠", "💡", "🔍", "🔎", "🔭", "🧮", "📐", "📊", "📈",
  "📉", "🎯", "🎓", "🏆", "🥼", "🧪", "🧫", "🔬", "🧬", "🌱",
  "🌿", "🍃", "🌐", "🗺️", "☁️", "🌤️", "⚡", "🚀", "🛰️", "📡",
  "🔗", "🧷", "🔖", "⭐", "🌟", "✨", "🎨", "🖼️", "🎬", "🎵",
  "📤", "📥", "🔄", "♻️", "🧭", "⏱️", "⏳", "🔐", "🛡️", "🧱",
];

// 色相：slug → 0..359（FNV 分布足够散）
export function hueForSlug(slug) {
  return hash32(slug || "") % 360;
}

// 底色：柔和的同色系渐变（不同 slug 底色不同）
export function tileBackground(slug) {
  const h = hueForSlug(slug);
  return `linear-gradient(180deg, hsl(${h} 70% 95%), hsl(${h} 65% 86%))`;
}

// 强调色（hover 描边 / 选中高亮）
export function accentForSlug(slug) {
  const h = hueForSlug(slug);
  return `hsl(${h} 62% 50%)`;
}

/**
 * 解析技能图标。
 * @returns {{ kind: "emoji", glyph: string, hue: number, background: string, accent: string }}
 */
export function getSkillIcon(skill) {
  const slug = skill?.slug || "";
  const glyph = SLUG_EMOJI[slug] || EMOJI_POOL[hash32(slug) % EMOJI_POOL.length];
  return {
    kind: "emoji",
    glyph,
    hue: hueForSlug(slug),
    background: tileBackground(slug),
    accent: accentForSlug(slug),
  };
}
