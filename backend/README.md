# Backend

FastAPI 后端：技能市场目录 + 流式 tool-calling 智能体 + 用户名登录。

## 运行

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 填入 LLM_API_KEY 后才有对话能力
uvicorn app.main:app --reload
```

服务监听 `http://127.0.0.1:8000`，接口文档见仓库根目录 [API.md](../API.md)。

## 依赖说明

| 文件 | 用途 |
|---|---|
| `requirements.txt` | 运行时依赖（FastAPI / openai / PyYAML 等） |
| `requirements-dev.txt` | 测试依赖（pytest / httpx） |
| `requirements-extra.txt` | 可选：技能脚本常用的第三方库（文档、图片、数据科学等） |

## 测试

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## 技能仓库

技能放在 `app/skills/<分类>/<技能>/SKILL.md`，分类定义在 `app/skills/categories.json`。
`_remote/` 目录用于存放从 SkillHub 同步的技能（已 gitignore）。
