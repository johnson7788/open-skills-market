"""端到端测试公共 fixture：针对已部署的 skill-market 实例。

默认打本地开发入口 http://127.0.0.1:8000，可用环境变量 SM_BASE_URL 覆盖
（例如指向 docker compose 的 http://127.0.0.1:8001 或任意部署地址）。
若部署在同一域名下同时提供前端静态页，可再设置 SM_FRONTEND_URL 以启用首页用例。
依赖 httpx（见 backend/requirements-dev.txt）。

运行：
    pytest test/ -m "not llm"        # 跳过需要大模型的用例
    pytest test/                     # 全量（需要配置 LLM_API_KEY）
"""
import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("SM_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FRONTEND_URL = os.environ.get("SM_FRONTEND_URL", "").rstrip("/")


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: 需要调用大模型的测试（用 -m 'not llm' 可跳过）")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def frontend_url() -> str:
    """前端入口；未配置时相关用例会跳过（纯后端进程不提供静态页）。"""
    return FRONTEND_URL


@pytest.fixture(scope="session")
def client():
    return httpx.Client(headers={"User-Agent": "skill-market-e2e-test"}, timeout=30)


@pytest.fixture(scope="session")
def auth_headers(base_url, client):
    """注册/登录一个一次性用户，返回带 Bearer token 的请求头。"""
    username = f"e2e-{uuid.uuid4().hex[:8]}"
    r = client.post(f"{base_url}/api/auth/login", json={"username": username})
    assert r.status_code == 200, f"登录失败：{r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}"}
