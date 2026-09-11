# Skill Market · 后端镜像（FastAPI + Uvicorn）
# 需要技能脚本的额外系统依赖（pandoc / libreoffice / tesseract 等）时，
# 可按 backend/requirements-extra.txt 的思路在本镜像里追加安装。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用（含 app/skills 静态技能仓库）
COPY app ./app

# 运行时数据目录（对话 SQLite 与智能体工作区产物）
RUN mkdir -p /app/data /app/.workspaces

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]