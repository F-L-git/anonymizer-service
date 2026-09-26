import pytest
from app.services.cache import CacheService


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.last_ex = None

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.last_ex = ex

    async def ping(self):
        return True


@pytest.fixture
def cache():
    c = CacheService()
    c._redis = FakeRedis()
    return c


@pytest.mark.asyncio
async def test_set_get_roundtrip(cache):
    payload = {"anonymized_text": "x", "detections_count": 1}
    await cache.set("hello", payload)
    assert await cache.get("hello") == payload


@pytest.mark.asyncio
async def test_different_rules_different_keys(cache):
    await cache.set("hello", {"v": 1}, rules=["email"])
    assert await cache.get("hello", rules=["phone"]) is None
    assert await cache.get("hello", rules=["email"]) == {"v": 1}


def test_text_hash_stable():
    assert CacheService.text_hash("a") == CacheService.text_hash("a")
    assert CacheService.text_hash("a") != CacheService.text_hash("b")


def test_client_raises_if_not_connected():
    with pytest.raises(RuntimeError, match="Redis not connected"):
        _ = CacheService().client


@pytest.mark.asyncio
async def test_get_swallows_errors(mocker):
    c = CacheService()
    broken = mocker.Mock()
    broken.get = mocker.AsyncMock(side_effect=RuntimeError("down"))
    c._redis = broken
    assert await c.get("x") is None


@pytest.mark.asyncio
async def test_set_swallows_errors(mocker):
    c = CacheService()
    broken = mocker.Mock()
    broken.set = mocker.AsyncMock(side_effect=RuntimeError("down"))
    c._redis = broken
    await c.set("x", {"a": 1})  # не должно пробрасывать


@pytest.mark.asyncio
async def test_ping_false_on_error(mocker):
    c = CacheService()
    broken = mocker.Mock()
    broken.ping = mocker.AsyncMock(side_effect=RuntimeError("down"))
    c._redis = broken
    assert await c.ping() is False


@pytest.mark.asyncio
async def test_ping_ok(cache):
    assert await cache.ping() is True