import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """同步 TestClient，覆盖所有非流式 API 与无 key 的 chat 错误分支。"""
    return TestClient(app)