# Frontend

Skill Market 前端：技能商店（分类 / 搜索 / 试用）+ 智能体对话页。React 18 + Vite 5。

## 运行

```bash
cd frontend
npm install
npm run dev          # http://127.0.0.1:5173
```

开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`（见 `vite.config.js`）。
后端不在默认地址时，用环境变量指定：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev
```

## 构建

```bash
npm run build        # 产物在 dist/
npm run preview      # 本地预览构建产物
```

## E2E 测试

用例通过 `page.route` 打桩后端接口，不依赖后端进程或模型 key：

```bash
npx playwright install chromium
npm run test:e2e
```

## 结构

```text
src/
├── api.js                 # 接口封装（含 SSE 流式对话）
├── AuthContext.jsx        # 登录态
├── icons.js               # 技能图标（slug → 确定性 emoji + 底色）
├── components/            # Sidebar · SkillCard
├── pages/                 # LoginPage · SkillStorePage · ChatPage
└── styles.css             # 全部样式与设计 tokens
```
