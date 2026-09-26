import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.session import get_db


@pytest_asyncio.fixture
async def db_session(mocker):
    session = mocker.AsyncMock()
    result = mocker.Mock()
    result.scalar_one_or_none.return_value = None
    session.execute = mocker.AsyncMock(return_value=result)
    session.add = mocker.Mock()
    session.delete = mocker.AsyncMock()
    yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def fake_db():
        yield db_session

    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


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
async def test_add_rule_invalid_regex(client):
    resp = await client.post(
        "/api/v1/rules",
        json={"name": "bad", "type": "x", "pattern": "[", "mask_strategy": "redact"},
    )
    assert resp.status_code == 400
    assert "Invalid regex" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_add_rule_invalid_strategy(client):
    resp = await client.post(
        "/api/v1/rules",
        json={"name": "bad", "type": "x", "pattern": "A+", "mask_strategy": "wipe_all"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_rule_created(client, db_session, mocker):
    engine = mocker.patch("app.api.routes.get_engine")
    engine.return_value.add_rule = mocker.Mock()

    resp = await client.post(
        "/api/v1/rules",
        json={
            "name": "tmp_token",
            "type": "token",
            "pattern": "TKN-[A-Z0-9]{8}",
            "mask_strategy": "redact",
            "priority": 15,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "tmp_token"
    db_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_delete_rule_404(client, mocker):
    engine = mocker.patch("app.api.routes.get_engine")
    engine.return_value.remove_rule.return_value = False

    resp = await client.delete("/api/v1/rules/missing")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_rule_ok(client, db_session, mocker):
    engine = mocker.patch("app.api.routes.get_engine")
    engine.return_value.remove_rule.return_value = True

    db_rule = mocker.Mock()
    result = mocker.Mock()
    result.scalar_one_or_none.return_value = db_rule
    db_session.execute = mocker.AsyncMock(return_value=result)

    resp = await client.delete("/api/v1/rules/tmp_token")
    assert resp.status_code == 200
    db_session.delete.assert_awaited_with(db_rule)


@pytest.mark.asyncio
async def test_anonymize_uses_service(client, mocker):
    mocker.patch(
        "app.api.routes.anonymize_service.process",
        new=mocker.AsyncMock(
            return_value={
                "request_id": "rid",
                "anonymized_text": "x",
                "detections": [],
                "stats": {},
                "processing_time_ms": 0.1,
                "cache_hit": False,
                "detections_count": 0,
            }
        ),
    )

    resp = await client.post(
        "/api/v1/anonymize",
        json={"text": "hello", "store_result": False, "use_cache": False},
    )
    assert resp.status_code == 200
    assert resp.json()["request_id"] == "rid"


@pytest.mark.asyncio
async def test_anonymize_internal_error_500(client, mocker):
    mocker.patch(
        "app.api.routes.anonymize_service.process",
        new=mocker.AsyncMock(side_effect=RuntimeError("boom")),
    )

    resp = await client.post("/api/v1/anonymize", json={"text": "hello"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal processing error"


@pytest.mark.asyncio
async def test_stats_ok(client, mocker):
    mocker.patch(
        "app.api.routes.stats_service.get_summary",
        new=mocker.AsyncMock(
            return_value={
                "total_requests": 3,
                "total_detections": 7,
                "detections_by_type": {"email": 7},
                "avg_processing_ms": 1.2,
                "cache_hit_rate": 0.1,
                "period_start": None,
                "period_end": None,
            }
        ),
    )

    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    assert resp.json()["total_requests"] == 3


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
