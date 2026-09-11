#!/usr/bin/env bash
#
# 一键部署：SkillHub（注册中心）+ Skill Market（市场/运行时）
#
# 用法（在 skill-market 根目录执行）：
#   ./deploy.sh                # 构建 + 启动全部，并做连通性/同步验证
#   ./deploy.sh --down         # 停止并删除容器（保留数据卷）
#   ./deploy.sh --down -v      # 停止并删除容器 + 数据卷
#   ./deploy.sh --logs         # 跟踪查看日志
#   ./deploy.sh --no-build     # 不重新构建 skill-market 镜像
#   ./deploy.sh --publish [--namespace N] [--only slug] [--dry-run]
#                               # 批量发布本地技能到 SkillHub
#
# 环境变量（可选）：
#   SKILLHUB_VERSION    SkillHub 镜像 tag，默认 latest
#   SKILLHUB_TOKEN      SkillHub API token（公开技能不需要）
#   SKILLHUB_SYNC_NAMESPACES  只同步指定命名空间（逗号分隔）
#   LLM_API_KEY         智能体对话密钥（也可写在 backend/.env）
set -euo pipefail

cd "$(dirname "$0")"   # 切到脚本所在目录（skill-market 根目录）
COMPOSE="docker compose -f deploy/docker-compose.all.yml"

ACTION="up"
VOLUMES=0
BUILD=1
FOLLOW=0
PUBLISH_ARGS=()

# ── 参数解析 ─────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --down) ACTION="down" ;;
    -v|--volumes) VOLUMES=1 ;;
    --logs) ACTION="logs"; FOLLOW=1 ;;
    --no-build) BUILD=0 ;;
    --publish) ACTION="publish"; shift; PUBLISH_ARGS=("$@"); break ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1（--help 查看用法）" >&2; exit 2 ;;
  esac
  shift
done

# ── publish 动作：不依赖 docker，只依赖 python3 + SkillHub 可达 ──
if [[ "$ACTION" == "publish" ]]; then
  echo "==> 批量发布本地技能到 SkillHub"
  if ! curl -sf http://localhost:18080/actuator/health >/dev/null 2>&1; then
    echo "[!] 未检测到本地 SkillHub（localhost:18080）" >&2
    echo "    请先 ./deploy.sh 启动，或加 --registry 指向远程实例" >&2
  fi
  exec python3 backend/app/services/publish_to_skillhub.py "${PUBLISH_ARGS[@]}"
fi

# ── 前置检查 ─────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "[✗] 未找到 docker，请先安装 Docker Desktop / docker engine" >&2; exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[✗] 未找到 docker compose（需要 Docker Compose v2）" >&2; exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[✗] Docker 未运行，请先启动 Docker Desktop" >&2; exit 1
fi

# ── 动作分发 ─────────────────────────────────────────────
case "$ACTION" in
  down)
    if [[ $VOLUMES -eq 1 ]]; then
      $COMPOSE down -v
    else
      $COMPOSE down
    fi
    echo "[✓] 已停止并删除容器"
    exit 0
    ;;
  logs)
    $COMPOSE logs -f --tail=100
    exit 0
    ;;
esac

# ── 启动流程 ─────────────────────────────────────────────
echo "==> 拉取 SkillHub 官方镜像（ghcr.io/iflytek/skillhub-*:${SKILLHUB_VERSION:-latest}）"
for img in skillhub-server skillhub-web skillhub-scanner; do
  docker pull "ghcr.io/iflytek/${img}:${SKILLHUB_VERSION:-latest}" || {
    echo "[!] 拉取 ${img} 失败；若私有仓库请先 docker login ghcr.io" >&2
  }
done

if [[ $BUILD -eq 1 ]]; then
  echo "==> 构建 Skill Market 镜像（backend + frontend）"
  $COMPOSE build skillmarket-backend skillmarket-frontend
else
  echo "==> 跳过构建（--no-build）"
fi

echo "==> 启动全部服务"
$COMPOSE up -d

echo "==> 等待 SkillHub server 健康（最长约 120s）"
for i in $(seq 1 40); do
  if curl -sf http://localhost:18080/actuator/health >/dev/null 2>&1; then
    echo "[✓] SkillHub server 已就绪"
    break
  fi
  if [[ $i -eq 40 ]]; then
    echo "[!] SkillHub server 未在预期时间内就绪，查看日志：$COMPOSE logs skillhub-server" >&2
  fi
  sleep 3
done

echo "==> 等待 Skill Market backend 健康"
for i in $(seq 1 40); do
  if curl -sf http://localhost:8001/api/health >/dev/null 2>&1; then
    echo "[✓] Skill Market backend 已就绪"
    break
  fi
  sleep 3
done

# backend 容器启动时已同步一次；这里再手动触发一次，确保内置技能初始化完成后拉到数据
echo "==> 触发一次 SkillHub → Skill Market 技能同步"
$COMPOSE exec -T skillmarket-backend python -m app.services.skillhub_sync || true

# ── 验证结果 ─────────────────────────────────────────────
echo ""
echo "============== 验证结果 =============="
echo -n "SkillHub API      : "; curl -s http://localhost:18080/actuator/health | head -c 120; echo
echo -n "Skill Market API  : "; curl -s http://localhost:8001/api/health; echo

REMOTE_COUNT=$($COMPOSE exec -T skillmarket-backend \
  sh -c "find app/skills/_remote -name SKILL.md 2>/dev/null | wc -l" 2>/dev/null || echo 0)
echo "同步到的远程技能数: ${REMOTE_COUNT}"

SKILLS_TOTAL=$(curl -s "http://localhost:8001/api/skills" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total','?'))" 2>/dev/null || echo "?")
echo "Skill Market 技能总数: ${SKILLS_TOTAL}"

echo ""
echo "============== 访问地址 =============="
echo "SkillHub  Web UI   : http://localhost:18081   (admin / change-me-local-demo)"
echo "SkillHub  API      : http://localhost:18080"
echo "Skill Market 前端  : http://localhost:5174"
echo "Skill Market API   : http://localhost:8001"
echo ""
echo "查看日志：$COMPOSE logs -f"
echo "停止服务：./deploy.sh --down"
