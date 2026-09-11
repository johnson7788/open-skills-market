"""API 端点测试（TestClient，不触发真实大模型）。"""
from app.agent import config


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_categories(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list) and items
    assert {"id", "name", "icon"} <= set(items[0].keys())
    # 排序稳定：order 升序
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids))


def test_skills_list_shape(client):
    r = client.get("/api/skills")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert isinstance(data["items"], list) and data["items"]
    assert set(data["tabs"].keys()) == {"all", "used"}
    assert data["tabs"]["all"] == data["total"]
    assert isinstance(data["categories"], list) and data["categories"]


def test_skills_search(client):
    data = client.get("/api/skills", params={"search": "csv"}).json()
    assert data["items"], "搜索 csv 应有结果"
    for it in data["items"]:
        blob = " ".join([it["slug"], it["name"], it["description"], *it["tags"]]).lower()
        assert "csv" in blob


def test_skills_category_filter(client):
    data = client.get("/api/skills", params={"category": "document"}).json()
    assert data["items"], "document 分类应有技能"
    assert all(it["category_id"] == "document" for it in data["items"])


def test_skills_used_tab_empty_for_new_user(client):
    data = client.get("/api/skills", params={"tab": "used"}).json()
    assert data["items"] == []
    assert data["tabs"]["used"] == 0


def test_skill_detail_found(client):
    slug = client.get("/api/skills").json()["items"][0]["slug"]
    r = client.get(f"/api/skills/{slug}")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == slug
    assert body["name"]


def test_skill_detail_404(client):
    r = client.get("/api/skills/no-such-skill")
    assert r.status_code == 404


def test_chat_history_requires_auth(client):
    r = client.get("/api/chat/history", params={"slug": "text-stats"})
    assert r.status_code == 401


def test_chat_history_empty(client):
    token = client.post("/api/auth/login", json={"username": "pytest-user"}).json()["token"]
    r = client.get(
        "/api/chat/history",
        params={"slug": "text-stats"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"messages": []}


def test_chat_artifacts_empty(client):
    token = client.post("/api/auth/login", json={"username": "pytest-user"}).json()["token"]
    r = client.get(
        "/api/chat/artifacts",
        params={"slug": "text-stats", "conversation_id": "empty-conv"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"files": []}


def test_chat_without_key_returns_error(client, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    token = client.post("/api/auth/login", json={"username": "pytest-user"}).json()["token"]
    r = client.post(
        "/api/chat",
        json={"slug": "text-stats", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "event: error" in r.text
    assert "LLM_API_KEY" in r.text
