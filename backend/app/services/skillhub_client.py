"""SkillHub REST API 客户端（零依赖，标准库 urllib）。

对应 SkillHub 官方 Python 示例（examples/python/skillhub_client.py），
这里用标准库重写，避免给 backend 增加新依赖，且可独立于 FastAPI 运行。

Endpoints（详见 SkillHub docs/04-developer/api）：
    GET  /api/v1/skills?keyword=&namespace=&page=&size=
    GET  /api/v1/skills/{namespace}/{slug}
    GET  /api/v1/skills/{namespace}/{slug}/resolve?version=&tag=
    GET  /api/v1/skills/{namespace}/{slug}/download
    GET  /api/v1/skills/{namespace}/{slug}/versions/{version}/download
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class SkillHubError(RuntimeError):
    """SkillHub 返回非零业务码或 HTTP 错误时抛出。"""


class SkillHubClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # -- internals -------------------------------------------------------

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, params: dict | None = None) -> tuple[int, bytes]:
        url = self.base_url + path
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if qs:
                url += "?" + qs
        req = urllib.request.Request(url, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except urllib.error.URLError as e:
            raise SkillHubError(f"无法连接 SkillHub {self.base_url}: {e.reason}") from e

    def _unwrap(self, status: int, body: bytes):
        if status >= 400:
            raise SkillHubError(f"SkillHub HTTP {status}: {body[:200]!r}")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None
        # 统一 envelope：{code, msg, data}；CLI-compat 端点直接返回对象
        if isinstance(payload, dict) and "code" in payload and "data" in payload:
            if payload.get("code") not in (0, None):
                raise SkillHubError(
                    f"SkillHub API error {payload.get('code')}: "
                    f"{payload.get('msg', '')} (requestId={payload.get('requestId')})"
                )
            return payload["data"]
        return payload

    # -- public API ------------------------------------------------------

    def list_skills(self, page: int = 0, limit: int = 100):
        """列出公开技能（cursor 分页，nextCursor = page+1）。"""
        status, body = self._request(
            "GET", "/api/v1/skills",
            params={"page": page, "limit": limit},
        )
        return self._unwrap(status, body)

    def get_skill(self, namespace: str, slug: str):
        status, body = self._request("GET", f"/api/v1/skills/{namespace}/{slug}")
        return self._unwrap(status, body)

    def resolve(self, namespace: str, slug: str, version: str | None = None, tag: str | None = None):
        status, body = self._request(
            "GET", f"/api/v1/skills/{namespace}/{slug}/resolve",
            params={"version": version, "tag": tag},
        )
        return self._unwrap(status, body)

    def get_skill_labels(self, namespace: str, slug: str) -> list[str]:
        """获取技能的标签 slug 列表。"""
        status, body = self._request("GET", f"/api/v1/skills/{namespace}/{slug}/labels")
        data = self._unwrap(status, body)
        if isinstance(data, list):
            return [str(x.get("slug")) for x in data if isinstance(x, dict) and x.get("slug")]
        return []

    def download(self, namespace: str, slug: str, version: str | None = None,
                 max_bytes: int = 64 * 1024 * 1024) -> bytes:
        """下载技能包（zip），返回字节。默认 latest。"""
        if version:
            path = f"/api/v1/skills/{namespace}/{slug}/versions/{version}/download"
        else:
            path = f"/api/v1/skills/{namespace}/{slug}/download"
        status, body = self._request("GET", path)
        if status >= 400:
            raise SkillHubError(f"下载失败 HTTP {status}: {body[:200]!r}")
        if len(body) > max_bytes:
            raise SkillHubError(f"技能包过大（{len(body)} 字节），跳过")
        return body
