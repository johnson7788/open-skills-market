# API 文档

Skill Market 后端接口说明。Base URL：`http://127.0.0.1:8000`

## 通用说明

- 所有接口返回 `JSON`（`/api/chat` 除外，返回 SSE 流）
- 编码为 `UTF-8`
- 市场类接口无需鉴权；对话类接口需要 `Authorization: Bearer <token>`
- 无 token 访问受保护接口返回 `401`

---

## 1. 健康检查

```http
GET /api/health
```

```json
{ "status": "ok" }
```

---

## 2. 分类列表

```http
GET /api/categories
```

```json
{
  "items": [
    { "id": "document", "name": "文档处理", "icon": "📄", "description": "文档解析与格式转换" },
    { "id": "productivity", "name": "效率工具", "icon": "⚡", "description": "通用效率提升工具" }
  ]
}
```

分类定义在 `backend/app/skills/categories.json`，按 `order` 升序返回。

---

## 3. 技能列表

```http
GET /api/skills?search=&tab=&category=
```

### 查询参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `search` | `""` | 关键词，匹配名称 / slug / 描述 / 标签 / 分类名 |
| `tab` | `all` | `all`（全部）或 `used`（当前用户用过的技能） |
| `category` | `""` | 分类 id，来自 `/api/categories` |

### 响应

```json
{
  "items": [
    {
      "id": 1,
      "slug": "csv-to-markdown",
      "name": "csv-to-markdown",
      "description": "把 CSV 文件转换成 Markdown 表格。",
      "tags": ["CSV", "Markdown"],
      "usage_count": 928,
      "icon": "📊",
      "category_id": "data-science",
      "category_name": "数据科学",
      "is_used": false,
      "examples": ["把 /workspace/data.csv 转成 Markdown 表格"]
    }
  ],
  "total": 3,
  "tabs": { "all": 3, "used": 0 },
  "categories": [{ "id": "document", "name": "文档处理", "icon": "📄", "description": "..." }]
}
```

> `tabs.all` 是所有技能的总数（不受过滤条件影响）；`is_used` 按当前登录用户计算，匿名访问恒为 `false`。
> `usage_count` 是演示用的确定性数值（同一 slug 永远得到同一个值）。

---

## 4. 技能详情

```http
GET /api/skills/{slug}
```

成功返回单个技能对象（字段同上）。`slug` 不存在时：

```json
{ "detail": "Skill 'unknown-slug' not found" }
```

HTTP `404 Not Found`。

---

## 5. 登录

```http
POST /api/auth/login
Content-Type: application/json

{ "username": "alice" }
```

用户名不存在时会自动创建。响应：

```json
{
  "token": "3f2c…",
  "user": { "id": 1, "username": "alice" }
}
```

之后请求带 `Authorization: Bearer <token>`。下载产物等无法带 header 的场景，可用 `?token=` 查询参数兜底。

### 当前用户

```http
GET /api/auth/me
Authorization: Bearer <token>
```

```json
{ "user": { "id": 1, "username": "alice" } }
```

### 退出登录

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

```json
{ "ok": true }
```

---

## 6. 流式对话

```http
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "slug": "text-stats",
  "conversation_id": "可选，不传则服务端生成",
  "messages": [{ "role": "user", "content": "统计 /workspace/report.md" }]
}
```

响应为 `text/event-stream`，事件类型：

| 事件 | data 字段 | 说明 |
|---|---|---|
| `text` | `delta` | 回答正文增量 |
| `reasoning` | `delta` | 推理过程增量（模型支持时） |
| `tool` | `name` + `arguments` | 工具开始调用 |
| `tool` | `name` + `output` | 工具执行结果 |
| `error` | `message` | 出错（例如未配置 `LLM_API_KEY`） |
| `done` | `truncated?` | 本轮结束 |

未配置模型 key 时，会先返回一条 `error` 事件：

```
event: error
data: {"message": "未配置 LLM_API_KEY（或 DASHSCOPE_API_KEY）"}
```

### 停止生成

```http
POST /api/chat/stop?slug=&conversation_id=
Authorization: Bearer <token>
```

```json
{ "stopped": true }
```

---

## 7. 会话与产物

### 历史消息

```http
GET /api/chat/history?slug=&conversation_id=
Authorization: Bearer <token>
```

返回该会话持久化的公开消息：`{ "messages": [{ "role": "user"|"assistant", "content": "...", "reasoning": "..." }] }`。

### 会话列表

```http
GET /api/chat/conversations?slug=
Authorization: Bearer <token>
```

```json
{ "items": [{ "cid": "…", "slug": "text-stats", "title": "统计报告", "updated_at": "2026-01-01 00:00:00" }] }
```

### 产物列表

```http
GET /api/chat/artifacts?slug=&conversation_id=
Authorization: Bearer <token>
```

```json
{ "files": [{ "path": "report.md", "size": 2048, "mtime": 1767225600 }] }
```

### 产物下载

```http
GET /api/chat/artifact?slug=&conversation_id=&path=report.md
Authorization: Bearer <token>   # 也可用 ?token=<token>
```

返回文件内容。路径越界返回 `400`，文件不存在返回 `404`。
