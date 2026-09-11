import { test, expect } from "@playwright/test";
import { mockStore, signIn } from "./helpers.js";

test.beforeEach(async ({ page }) => {
  await signIn(page);
  await mockStore(page);
});

test("首页渲染侧边栏、分类、卡片与「试用」按钮", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator(".sidebar")).toBeVisible();
  await expect(page.locator(".sidebar-brand")).toContainText("Skill Market");
  await expect(page.locator(".skill-store-title")).toHaveText("Skill 商店");
  await expect(page.locator(".skill-store-card")).toHaveCount(2);
  await expect(page.locator(".skill-store-try")).toHaveCount(2);

  // 分类由后端下发，侧边栏与筛选条各渲染一次
  await expect(page.locator(".sidebar-item-emoji")).toHaveCount(2);
  await expect(page.locator(".skill-store-category")).toHaveCount(3); // 全部分类 + 2 个分类
});

test("点击「试用」跳转到对应技能的 /chat/<slug>", async ({ page }) => {
  await page.goto("/");

  await page.locator(".skill-store-try").first().click();
  await expect(page).toHaveURL(/\/chat\/text-stats/);
});

test("点击分类筛选会写入 category 查询参数并带上请求", async ({ page }) => {
  const requested = [];
  await page.route("**/api/skills**", (route) => {
    requested.push(route.request().url());
    return route.fallback();
  });

  await page.goto("/");
  await page.locator(".skill-store-category", { hasText: "文档处理" }).click();

  await expect(page).toHaveURL(/category=document/);
  await expect
    .poll(() => requested.some((u) => u.includes("category=document")))
    .toBe(true);
});
