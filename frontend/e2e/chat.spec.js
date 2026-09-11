import { test, expect } from "@playwright/test";
import { SKILL, signIn } from "./helpers.js";

/** 模拟后端 /api 接口（跨源到 127.0.0.1:8000 的请求也会被拦截）。 */
async function mockChatApi(
  page,
  { history = [], artifacts = [], chatBody = "", conversations = [] } = {}
) {
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const method = req.method();

    if (method === "POST" && path === "/api/chat") {
      return route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: chatBody,
      });
    }
    if (method === "GET" && path === "/api/chat/history") {
      return route.fulfill({ json: { messages: history } });
    }
    if (method === "GET" && path === "/api/chat/artifacts") {
      return route.fulfill({ json: { files: artifacts } });
    }
    if (method === "GET" && path === "/api/chat/conversations") {
      return route.fulfill({ json: { items: conversations } });
    }
    if (method === "GET" && path === "/api/auth/me") {
      return route.fulfill({ json: { user: { id: 1, username: "e2e" } } });
    }
    if (method === "GET" && /^\/api\/skills\/[^/]+$/.test(path)) {
      return route.fulfill({ json: SKILL });
    }
    if (method === "GET" && path === "/api/skills") {
      return route.fulfill({
        json: { total: 1, tabs: { all: 1, used: 0 }, categories: [], items: [SKILL] },
      });
    }
    return route.continue();
  });
}

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("流式回答逐步渲染", async ({ page }) => {
  const chatBody = [
    'event: text\ndata: {"delta":"你好"}',
    'event: text\ndata: {"delta":"，我是测试回答。"}',
    "event: done\ndata: {}",
  ].join("\n\n") + "\n\n";

  await mockChatApi(page, { chatBody });
  await page.goto("/chat/text-stats");
  await page.fill(".chat-input textarea", "介绍一下");
  await page.click(".chat-send");

  await expect(page.locator(".chat-msg-assistant .chat-markdown")).toContainText("你好，我是测试回答。");
  // 流结束后 loading 结束（发送按钮不再显示 spinner）
  await expect(page.locator(".chat-send .fa-spinner")).toHaveCount(0);
  // 重新输入后按钮可再次发送
  await page.fill(".chat-input textarea", "再问一次");
  await expect(page.locator(".chat-send")).toBeEnabled();
});

test("工具调用分组收起并展示命令与输出", async ({ page }) => {
  const chatBody = [
    'event: tool\ndata: {"name":"run_command","arguments":"{\\"command\\":\\"echo hi\\"}"}',
    'event: tool\ndata: {"name":"run_command","output":"hi"}',
    'event: text\ndata: {"delta":"执行完成"}',
    "event: done\ndata: {}",
  ].join("\n\n") + "\n\n";

  await mockChatApi(page, { chatBody });
  await page.goto("/chat/text-stats");
  await page.fill(".chat-input textarea", "跑一下");
  await page.click(".chat-send");

  // 完成后工具组收起为摘要：显示工具名与状态
  await expect(page.locator(".tool-group")).toHaveCount(1);
  await expect(page.locator(".tool-group-title")).toContainText("执行命令");
  await expect(page.locator(".tool-group-status")).toContainText("已完成");

  // 手动展开工具组 + 单个工具后可查看输出
  await page.click(".tool-group-summary");
  await page.click(".tool-item-header");
  await expect(page.locator(".tool-item-section-title", { hasText: "结果" })).toHaveCount(1);
  await expect(page.locator(".tool-item-body")).toContainText("hi");
});

test("思考过程折叠为「推理过程」并支持展开", async ({ page }) => {
  const chatBody = [
    'event: reasoning\ndata: {"delta":"先看看工作区里有什么文件。"}',
    'event: tool\ndata: {"name":"list_files","arguments":"{\\"path\\":\\"/workspace\\"}"}',
    'event: tool\ndata: {"name":"list_files","output":"/workspace/report.md"}',
    'event: text\ndata: {"delta":"处理完成。"}',
    "event: done\ndata: {}",
  ].join("\n\n") + "\n\n";

  await mockChatApi(page, { chatBody });
  await page.goto("/chat/text-stats");
  await page.fill(".chat-input textarea", "帮我看看");
  await page.click(".chat-send");

  // 思考过程以折叠块存在，默认收起
  await expect(page.locator(".reasoning-summary")).toContainText("推理过程");
  await expect(page.locator(".reasoning-content")).toHaveCount(0);

  // 点击展开后显示思考内容
  await page.click(".reasoning-summary");
  await expect(page.locator(".reasoning-content")).toContainText("先看看工作区里有什么文件。");
});

test("产物列表展示下载项", async ({ page }) => {
  const artifacts = [{ path: "report.md", size: 2048 }];
  // 需要一个已存在的会话，页面才会去拉取该会话的产物
  const conversations = [
    { cid: "e2e-conv", slug: "text-stats", title: "产物示例", updated_at: new Date().toISOString() },
  ];
  await mockChatApi(page, { artifacts, conversations });
  await page.goto("/chat/text-stats");

  await expect(page.locator(".chat-artifact")).toHaveCount(1);
  await expect(page.locator(".chat-artifact")).toContainText("report.md");
});

test("出错时显示错误信息与重试按钮", async ({ page }) => {
  const chatBody = 'event: error\ndata: {"message":"模型调用失败"}\n\n';
  await mockChatApi(page, { chatBody });
  await page.goto("/chat/text-stats");
  await page.fill(".chat-input textarea", "触发错误");
  await page.click(".chat-send");

  await expect(page.locator(".chat-error-text")).toContainText("模型调用失败");
  await expect(page.locator(".chat-retry")).toBeVisible();
});
