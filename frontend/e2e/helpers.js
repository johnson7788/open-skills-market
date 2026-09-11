// E2E 公共工具：绕过登录页 + 拦截后端接口。
//
// 前端登录态存 localStorage 的 "skill-market:token"；这里预置一个假 token，
// 并把 /api/auth/me 打桩成已登录用户，这样用例不依赖真实后端。

export const E2E_TOKEN = "e2e-token";

export const E2E_USER = { id: 1, username: "e2e" };

export const CATEGORIES = [
  { id: "document", name: "文档处理", icon: "📄", description: "文档解析与转换" },
  { id: "productivity", name: "效率工具", icon: "⚡", description: "通用效率工具" },
];

export const SKILLS = [
  {
    slug: "text-stats",
    name: "text-stats",
    description: "统计文本文件的行数、字符数、词数与高频词。",
    tags: ["文本", "统计"],
    usage_count: 2280,
    icon: "📄",
    category_id: "document",
    category_name: "文档处理",
    is_used: false,
    examples: ["统计 /workspace/report.md 的行数"],
  },
  {
    slug: "hello-skill",
    name: "hello-skill",
    description: "最小可用示例技能，演示 SKILL.md 目录结构。",
    tags: ["示例", "入门"],
    usage_count: 2003,
    icon: "⚡",
    category_id: "productivity",
    category_name: "效率工具",
    is_used: false,
    examples: ["用 hello-skill 打个招呼"],
  },
];

export const SKILL = SKILLS[0];

/** 预置登录态并打桩鉴权 / 会话列表接口。 */
export async function signIn(page) {
  await page.addInitScript((token) => {
    localStorage.setItem("skill-market:token", token);
  }, E2E_TOKEN);

  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ json: { user: E2E_USER } })
  );
  await page.route("**/api/chat/conversations*", (route) =>
    route.fulfill({ json: { items: [] } })
  );
}

/** 打桩技能市场接口（/api/skills、/api/categories、/api/skills/{slug}）。 */
export async function mockStore(page, { items = SKILLS } = {}) {
  await page.route("**/api/categories", (route) =>
    route.fulfill({ json: { items: CATEGORIES } })
  );
  await page.route("**/api/skills**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/skills") {
      const slug = decodeURIComponent(url.pathname.replace("/api/skills/", ""));
      const found = items.find((s) => s.slug === slug);
      return found
        ? route.fulfill({ json: found })
        : route.fulfill({ status: 404, json: { detail: "not found" } });
    }
    return route.fulfill({
      json: {
        total: items.length,
        tabs: { all: items.length, used: 0 },
        categories: CATEGORIES,
        items,
      },
    });
  });
}
