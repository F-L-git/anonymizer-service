import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_list_rules(client):
    resp = await client.get("/api/v1/rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert isinstance(rules, list)
    assert len(rules) > 0


@pytest.mark.asyncio
async def test_anonymize_basic(client):
    payload = {
        "text": "My email is test.user@example.com and phone +7 999 111-22-33",
        "store_result": False,
        "use_cache": False,
    }
    resp = await client.post("/api/v1/anonymize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "anonymized_text" in data
    assert "test.user@example.com" not in data["anonymized_text"]
    assert data["detections_count"] >= 1
    assert "request_id" in data


@pytest.mark.asyncio
async def test_anonymize_empty_rejected(client):
    payload = {"text": ""}
    resp = await client.post("/api/v1/anonymize", json=payload)
    assert resp.status_code == 422
