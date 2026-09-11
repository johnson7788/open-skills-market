"""skill-market 部署实例的端到端测试。

覆盖：健康检查、前端首页、技能列表/搜索/分类筛选、技能详情、
对话历史/产物（需登录）、产物下载 404，以及智能体对话（SSE 流式，标记 llm）。

默认目标 http://127.0.0.1:8000，可用 SM_BASE_URL 覆盖；
若同一域名下也提供前端静态页，设置 SM_FRONTEND_URL 以启用首页用例。
"""
import pytest


class TestHealth:
    def test_health(self, base_url, client):
        r = client.get(f"{base_url}/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_frontend_index(self, frontend_url, client):
        if not frontend_url:
            pytest.skip("未设置 SM_FRONTEND_URL（后端进程本身不提供前端静态页）")
        r = client.get(f"{frontend_url}/")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()
        assert 'id="root"' in r.text


class TestCatalog:
    def _skills(self, base_url, client, **params):
        r = client.get(f"{base_url}/api/skills", params=params)
        assert r.status_code == 200
        return r.json()

    def test_list_shape(self, base_url, client):
        d = self._skills(base_url, client)
        for key in ("items", "total", "tabs", "categories"):
            assert key in d, f"missing key: {key}"
        assert isinstance(d["items"], list)
        assert d["total"] == len(d["items"]) > 0
        assert set(d["tabs"]) == {"all", "used"}
        assert d["tabs"]["all"] == d["total"]

    def test_item_fields(self, base_url, client):
        item = self._skills(base_url, client)["items"][0]
        for key in ("id", "slug", "name", "description", "tags", "usage_count",
                    "icon", "category_id", "category_name", "is_used"):
            assert key in item, f"item missing key: {key}"
        assert item["slug"] and item["name"]

    def test_categories(self, base_url, client):
        r = client.get(f"{base_url}/api/categories")
        assert r.status_code == 200
        assert r.json()["items"], "分类列表为空"

    def test_category_filter(self, base_url, client):
        cats = self._skills(base_url, client)["categories"]
        assert cats, "分类列表为空"
        cid = cats[0]["id"]
        d = self._skills(base_url, client, category=cid)
        assert all(it["category_id"] == cid for it in d["items"])

    def test_search_filters(self, base_url, client):
        d = self._skills(base_url, client, search="csv")
        assert d["items"], "搜索 csv 无结果"
        for it in d["items"]:
            blob = " ".join([it["slug"], it["name"], it["description"], *it["tags"]]).lower()
            assert "csv" in blob


class TestSkillDetail:
    def test_detail_ok(self, base_url, client):
        slug = client.get(f"{base_url}/api/skills").json()["items"][0]["slug"]
        r = client.get(f"{base_url}/api/skills/{slug}")
        assert r.status_code == 200
        assert r.json()["slug"] == slug

    def test_detail_404(self, base_url, client):
        r = client.get(f"{base_url}/api/skills/__no_such_slug_xyz__")
        assert r.status_code == 404


class TestChatMeta:
    def test_history_requires_auth(self, base_url, client):
        r = client.get(f"{base_url}/api/chat/history", params={"slug": "text-stats"})
        assert r.status_code == 401

    def test_history(self, base_url, client, auth_headers):
        r = client.get(
            f"{base_url}/api/chat/history",
            params={"slug": "text-stats"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "messages" in r.json()

    def test_artifacts(self, base_url, client, auth_headers):
        r = client.get(
            f"{base_url}/api/chat/artifacts",
            params={"slug": "text-stats"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "files" in r.json()

    def test_artifact_404(self, base_url, client, auth_headers):
        r = client.get(
            f"{base_url}/api/chat/artifact",
            params={"slug": "text-stats", "path": "no/such/file.txt"},
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestChatStream:
    """智能体对话：SSE 流式。依赖已配置 LLM_API_KEY。"""

    def _collect_sse(self, resp):
        events = []
        ev = None
        for raw in resp.iter_lines():
            line = raw.strip()
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                events.append((ev, line[5:].strip()))
                if ev in ("done", "error"):
                    break
                ev = None
        return events

    @pytest.mark.llm
    def test_chat_stream(self, base_url, client, auth_headers):
        with client.stream(
            "POST",
            f"{base_url}/api/chat",
            headers=auth_headers,
            json={"slug": None, "messages": [{"role": "user", "content": "只回复两个字：收到"}]},
            timeout=90,
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = self._collect_sse(resp)
            kinds = {e for e, _ in events}
            assert "error" not in kinds, f"对话返回 error 事件: {events}"
            assert "done" in kinds, "未收到 done 事件"
            assert ("text" in kinds) or ("reasoning" in kinds), "无任何内容输出"
