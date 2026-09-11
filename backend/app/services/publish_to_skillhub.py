"""批量发布本地 skill-market 技能到 SkillHub。

零依赖（仅标准库），可在宿主机直接运行：
    python3 backend/app/services/publish_to_skillhub.py [--dry-run] [--namespace global]

流程：CSRF 登录 → 生成 API token（skill:publish 权限）→ 逐个打包本地技能 → POST publish。

打包时自动排除 .DS_Store / __pycache__ / *.pyc 等垃圾文件，以及不在
SkillHub allowlist（SkillPackagePolicy.ALLOWED_EXTENSIONS）内的文件，
确保 publish 不触发 "Pre-publish warnings" 而被拒。

环境变量（可被命令行参数覆盖）：
    SKILLHUB_URL        默认 http://localhost:18080
    SKILLHUB_ADMIN_USERNAME  默认 admin
    SKILLHUB_ADMIN_PASSWORD  必填（本地 SkillHub 默认 change-me-local-demo）
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# 与 SkillHub SkillPackagePolicy.ALLOWED_EXTENSIONS 对齐
ALLOWED_EXT = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".html", ".css", ".csv", ".pdf",
    ".toml", ".xml", ".xsd", ".xsl", ".dtd", ".ini", ".cfg", ".env",
    ".js", ".cjs", ".mjs", ".ts", ".py", ".sh", ".rb", ".go", ".rs", ".java", ".kt",
    ".lua", ".sql", ".r", ".bat", ".ps1", ".zsh", ".bash",
    ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".ico",
    ".doc", ".xls", ".ppt", ".docx", ".xlsx", ".pptx",
}
SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache"}
SKIP_FILES = {".DS_Store", ".gitignore"}

DEFAULT_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class SkillHubPublisher:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.token: str | None = None

    def _csrf(self) -> str:
        return next((c.value for c in self.cookies if c.name == "XSRF-TOKEN"), "")

    def _json(self, method: str, path: str, body=None, csrf: bool = False, bearer: bool = False):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-XSRF-TOKEN"] = self._csrf()
        if bearer and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _unwrap(self, status: int, body: bytes, what: str):
        payload = json.loads(body) if body else {}
        if status >= 400 or payload.get("code") not in (0, None):
            raise RuntimeError(f"{what}失败 [{status}]: {payload}")
        return payload.get("data", {})

    def login(self) -> dict:
        self._json("GET", "/api/v1/auth/providers")  # 建立 CSRF cookie
        status, body = self._json(
            "POST", "/api/v1/auth/local/login",
            {"username": self.username, "password": self.password}, csrf=True,
        )
        return self._unwrap(status, body, "登录")

    def create_token(self) -> str:
        status, body = self._json(
            "POST", "/api/v1/tokens",
            {"name": "skill-market-batch-publish"}, csrf=True,
        )
        data = self._unwrap(status, body, "生成 token")
        self.token = data.get("token")
        if not self.token:
            raise RuntimeError("生成 token 返回缺少 token 字段")
        return self.token

    def skill_exists(self, namespace: str, slug: str) -> bool:
        status, _ = self._json("GET", f"/api/v1/skills/{namespace}/{slug}")
        return status == 200

    def publish(self, namespace: str, zip_bytes: bytes, visibility: str = "PUBLIC"):
        boundary = "----skillhub" + os.urandom(8).hex()
        body = b"".join([
            (f"--{boundary}\r\n"
             f'Content-Disposition: form-data; name="file"; filename="skill.zip"\r\n'
             f"Content-Type: application/zip\r\n\r\n").encode(),
            zip_bytes,
            (f"\r\n--{boundary}\r\n"
             f'Content-Disposition: form-data; name="visibility"\r\n\r\n'
             f"{visibility}\r\n").encode(),
            f"--{boundary}--\r\n".encode(),
        ])
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/cli/v1/skills/{namespace}/publish",
            data=body, method="POST", headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()


# -- 打包 ---------------------------------------------------------------

def iter_skills(root: Path):
    """两层扫描：skills/<category>/<slug>/SKILL.md，与 data.py 市场扫描一致。"""
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_remote"):
        for slug_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            if (slug_dir / "SKILL.md").exists():
                yield slug_dir


def package_skill(skill_dir: Path) -> tuple[bytes, list[str]]:
    """打包 skill 目录为 zip，返回 (字节, 被跳过的文件列表)。"""
    buf = __import__("io").BytesIO()
    skipped: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(skill_dir.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(skill_dir).as_posix()
            if any(part in SKIP_DIRS for part in f.parts):
                skipped.append(rel)
                continue
            if f.name in SKIP_FILES:
                skipped.append(rel)
                continue
            ext = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
            if ext not in ALLOWED_EXT:
                skipped.append(rel)
                continue
            zf.write(f, rel)
    return buf.getvalue(), skipped


# -- 主流程 -------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="批量发布本地 skill 到 SkillHub")
    ap.add_argument("--registry", default=env("SKILLHUB_URL", "http://localhost:18080"))
    ap.add_argument("--username", default=env("SKILLHUB_ADMIN_USERNAME", "admin"))
    ap.add_argument("--password", default=env("SKILLHUB_ADMIN_PASSWORD", "change-me-local-demo"))
    ap.add_argument("--namespace", default="global", help="目标命名空间，默认 global")
    ap.add_argument("--skills-root", default=str(DEFAULT_SKILLS_ROOT))
    ap.add_argument("--dry-run", action="store_true", help="只打包校验，不发布")
    ap.add_argument("--only", help="只发布指定 slug（调试用）")
    ap.add_argument("--force", action="store_true", help="跳过已存在检查，强制重新发布新版本")
    args = ap.parse_args()

    skills = list(iter_skills(Path(args.skills_root)))
    if args.only:
        skills = [s for s in skills if s.name == args.only]

    print(f"发现 {len(skills)} 个本地技能，目标 namespace={args.namespace}")

    if args.dry_run:
        for s in skills:
            _, skipped = package_skill(s)
            note = f"（跳过 {len(skipped)} 个非白名单文件：{', '.join(skipped) if skipped else '-'}）"
            print(f"  [dry-run] {s.parent.name}/{s.name} 可打包 {note}")
        return 0

    pub = SkillHubPublisher(args.registry, args.username, args.password)
    pub.login()
    token = pub.create_token()
    print(f"已登录并生成 API token（前缀 {token[:10]}…）")

    ok = fail = skip_existing = 0
    for s in skills:
        label = f"{s.parent.name}/{s.name}"
        if not args.force and pub.skill_exists(args.namespace, s.name):
            skip_existing += 1
            print(f"  [SKIP] {label} 已存在于 SkillHub")
            continue
        try:
            zip_bytes, skipped = package_skill(s)
            status, body = 0, b""
            # publish 限流 authenticated=10/60s，遇 429 退避重试
            for attempt in range(4):
                status, body = pub.publish(args.namespace, zip_bytes)
                if status != 429:
                    break
                wait = 15 * (attempt + 1)
                print(f"  [限速] {label} 触发限流，{wait}s 后重试({attempt + 1}/3)")
                time.sleep(wait)
            payload = json.loads(body) if body else {}
            if status >= 400 or payload.get("code") not in (0, None):
                raise RuntimeError(f"[{status}] {payload.get('msg', payload)}")
            ok += 1
            skip_note = f"（跳过 {len(skipped)} 文件）" if skipped else ""
            print(f"  [OK] {label} 已发布 {skip_note}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  [FAIL] {label}: {e}")
        time.sleep(7)  # 限速：60s 窗口最多 10 次，7s 间隔留余量

    print(f"\n完成：成功 {ok}，跳过已存在 {skip_existing}，失败 {fail}，共 {len(skills)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
