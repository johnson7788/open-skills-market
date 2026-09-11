"""从 SkillHub 拉取技能到本地 `skills/_remote/<namespace>/<slug>/` 目录。

设计要点：
- 零依赖，可用 `python -m app.services.skillhub_sync` 独立运行（uvicorn 启动前执行）。
- 幂等：`_meta.json` 里记录版本号，版本一致则跳过下载。
- 拉下来的技能会被 data.py（市场列表）与 agent/skill_index.py（智能体）扫描到，
  因此「市场展示」与「智能体执行」天然复用同一套 SkillHub 技能源。

环境变量：
    SKILLHUB_URL             SkillHub 服务地址（必填，如 http://skillhub-server:8080）
    SKILLHUB_TOKEN           API token（可选；公开技能不需要）
    SKILLHUB_SYNC_NAMESPACES 只同步指定命名空间，逗号分隔（可选；默认全部公开技能）
    SKILLHUB_SYNC_LIMIT      最多拉取 N 个（可选；0 = 不限制）
    SKILLHUB_SYNC_FORCE      true/1 强制重新下载
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

from .skillhub_client import SkillHubClient

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
REMOTE_DIR = SKILLS_ROOT / "_remote"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# -- 分页与字段解析（防御性，兼容 SkillHub 多种返回结构） --------------------

def _extract_items(data) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "list", "content", "records", "data"):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        # 单对象兜底
        return [data] if data else []
    return []


def _extract_total(data) -> int | None:
    if isinstance(data, dict):
        for key in ("total", "totalElements", "count"):
            v = data.get(key)
            if isinstance(v, int):
                return v
    return None


def _pick(item: dict, *keys: str, default: str = ""):
    for k in keys:
        v = item.get(k)
        if v not in (None, ""):
            return v
    return default


def _skill_meta(item: dict) -> dict:
    slug = str(_pick(item, "slug", "skillSlug", "name", "id", default=""))
    namespace = str(_pick(item, "namespace", "namespaceSlug", "namespace_slug", default="global"))
    name = str(_pick(item, "displayName", "display_name", "name", "title", default=slug))
    description = str(_pick(item, "summary", "description", "tagline", default=""))
    # version 优先取嵌套 latestVersion.version，兼容顶层 version
    version = str(_pick(item, "version", default=""))
    lv = item.get("latestVersion") or item.get("latest_version")
    if isinstance(lv, dict):
        version = str(_pick(lv, "version", default="")) or version
    elif lv:
        version = str(lv)
    return {
        "namespace": namespace,
        "slug": slug,
        "name": name,
        "description": description,
        "version": version,
    }


def _iter_all_skills(client: SkillHubClient, namespace: str | None):
    page = 0
    while True:
        data = client.list_skills(page=page, limit=100)
        items = _extract_items(data)
        if not items:
            break
        for it in items:
            yield it
        nxt = data.get("nextCursor") if isinstance(data, dict) else None
        if not nxt:
            break
        page = int(nxt)  # nextCursor = page + 1


# -- 解压与落地 ---------------------------------------------------------

def _flatten(target: Path) -> None:
    """若 zip 解压后内容被包在单一顶层目录里，则上移一层，使 SKILL.md 与 _meta.json 同层。"""
    if (target / "SKILL.md").exists():
        return
    children = [p for p in target.iterdir() if p.name != "_meta.json"]
    if len(children) == 1 and children[0].is_dir():
        sub = children[0]
        for p in list(sub.iterdir()):
            p.rename(target / p.name)
        sub.rmdir()


def _safe_extract(zip_bytes: bytes, target: Path) -> None:
    """解压 zip 到 target，带 zip-slip 防护。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        base = target.resolve()
        for member in zf.infolist():
            dest = (target / member.filename).resolve()
            if not str(dest).startswith(str(base) + os.sep) and dest != base:
                raise ValueError(f"非法压缩路径：{member.filename}")
        zf.extractall(target)
    _flatten(target)


def sync_skill(client: SkillHubClient, meta: dict, force: bool = False) -> bool:
    """下载单个技能到 _remote/<ns>/<slug>，返回是否发生了更新。"""
    ns, slug = meta["namespace"], meta["slug"]
    if not slug:
        return False
    target = REMOTE_DIR / ns / slug
    meta_path = target / "_meta.json"

    # 幂等：已存在且版本一致则跳过
    if meta_path.exists() and not force:
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta["version"] and existing.get("version") == meta["version"]:
                return False
        except (json.JSONDecodeError, OSError):
            pass

    zip_bytes = client.download(ns, slug)
    target.mkdir(parents=True, exist_ok=True)
    _safe_extract(zip_bytes, target)

    # 保留技能包自带的 _meta.json（examples / changelog / max_steps 等），
    # 只在上面叠加同步信息，避免覆盖丢失推荐问题等字段
    original_meta: dict = {}
    try:
        if meta_path.exists():
            original_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(original_meta, dict):
                original_meta = {}
    except (json.JSONDecodeError, OSError):
        original_meta = {}

    # 远程技能统一归入「远程技能」分类；技能包自带 _meta.json.category_id 可覆盖
    category_id = "remote"
    labels: list[str] = []
    try:
        labels = client.get_skill_labels(ns, slug)
    except Exception:  # noqa: BLE001 —— 标签拉取失败不影响同步主流程
        pass

    out_meta = {
        **original_meta,
        **meta,
        "source": "skillhub",
        "category_id": category_id,
    }
    if labels:
        out_meta["labels"] = labels
    meta_path.write_text(json.dumps(out_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


# -- 主流程 -------------------------------------------------------------

def sync_from_skillhub() -> dict:
    """执行一次完整同步，返回统计信息。"""
    url = env("SKILLHUB_URL")
    if not url:
        return {"enabled": False, "reason": "未配置 SKILLHUB_URL"}

    token = env("SKILLHUB_TOKEN") or None
    namespaces = [n for n in env("SKILLHUB_SYNC_NAMESPACES").split(",") if n]
    limit = int(env("SKILLHUB_SYNC_LIMIT", "0") or "0")
    force = env("SKILLHUB_SYNC_FORCE", "false").lower() in ("1", "true", "yes")

    client = SkillHubClient(url, token)
    updated = skipped = failed = 0
    ns_list = namespaces or [None]

    for ns in ns_list:
        for item in _iter_all_skills(client, ns):
            meta = _skill_meta(item)
            label = f"{meta['namespace']}/{meta['slug']}"
            if not meta["slug"]:
                continue
            try:
                if sync_skill(client, meta, force):
                    updated += 1
                    print(f"[skillhub-sync] 拉取 {label} v{meta['version']}")
                else:
                    skipped += 1
            except Exception as e:  # noqa: BLE001 —— 单个技能失败不中断整批
                failed += 1
                print(f"[skillhub-sync] 失败 {label}: {e}")
            if limit and updated >= limit:
                break
        if limit and updated >= limit:
            break

    return {"enabled": True, "updated": updated, "skipped": skipped, "failed": failed}


def main() -> int:
    result = sync_from_skillhub()
    if not result["enabled"]:
        print("[skillhub-sync] 跳过：", result.get("reason"))
        return 0
    print(
        "[skillhub-sync] 完成："
        f"更新 {result['updated']}，跳过 {result['skipped']}，失败 {result['failed']}"
    )
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
