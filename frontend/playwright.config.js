import { defineConfig } from "@playwright/test";

/**
 * Playwright E2E 配置。
 *
 * 运行前提：前端 dev 服务在 5173（webServer 会复用已运行的实例，若未运行则自动拉起）。
 * 若 5173 已被别的进程占用，用 PW_PORT 换一个端口：PW_PORT=5199 npx playwright test。
 *
 * 用例通过 page.route 模拟后端 API，因此不依赖后端进程或大模型 key，可稳定、可重复执行。
 * 真实链路（真后端 + 真模型）手工验证见仓库根目录的 test/。
 */
const PORT = Number(process.env.PW_PORT || 5173);
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  fullyParallel: true,
  use: {
    baseURL: BASE_URL,
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${PORT}`,
    url: BASE_URL,
    // 指定 PW_PORT 时认为该端口专用于本次测试，避免误复用其它进程
    reuseExistingServer: !process.env.PW_PORT,
    timeout: 60000,
  },
});
