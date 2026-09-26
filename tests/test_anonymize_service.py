import pytest
from app.core.anonymizer import (
    AnonymizerEngine,
    AnonymizationRule,
    AnonymizationResult,
    Detection,
)
from app.services.anonymize_service import AnonymizeService


def _result():
    return AnonymizationResult(
        original_text="a@b.c",
        anonymized_text="*@b.c",
        detections=[Detection("email", "email", "a@b.c", "*@b.c", 0, 5)],
        stats={"email": 1},
        processing_time_ms=1.0,
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_engine(mocker):
    svc = AnonymizeService()
    cached = {
        "anonymized_text": "cached",
        "detections": [],
        "stats": {},
        "processing_time_ms": 0.1,
        "detections_count": 0,
    }

    cache = mocker.patch("app.services.anonymize_service.cache_service")
    cache.text_hash.return_value = "h" * 64
    cache.get = mocker.AsyncMock(return_value=dict(cached))
    cache.set = mocker.AsyncMock()

    engine = mocker.patch.object(svc, "engine")

    out = await svc.process("a@b.c", use_cache=True, store_result=False)

    assert out["cache_hit"] is True
    assert out["anonymized_text"] == "cached"
    assert "request_id" in out
    engine.anonymize.assert_not_called()
    cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_miss_processes_and_sets_cache(mocker):
    svc = AnonymizeService()
    cache = mocker.patch("app.services.anonymize_service.cache_service")
    cache.text_hash.return_value = "h" * 64
    cache.get = mocker.AsyncMock(return_value=None)
    cache.set = mocker.AsyncMock()

    svc.engine = AnonymizerEngine(rules=[])
    svc.engine.add_rule(
        AnonymizationRule("email", "email", r"\S+@\S+", "redact", priority=1)
    )

    out = await svc.process("a@b.c", use_cache=True, store_result=False)

    assert out["cache_hit"] is False
    assert out["detections_count"] == 1
    cache.set.assert_awaited()


@pytest.mark.asyncio
async def test_store_result_records_stats(mocker):
    svc = AnonymizeService()
    session = mocker.Mock()

    cache = mocker.patch("app.services.anonymize_service.cache_service")
    cache.text_hash.return_value = "h" * 64
    cache.get = mocker.AsyncMock(return_value=None)
    cache.set = mocker.AsyncMock()

    stats = mocker.patch("app.services.anonymize_service.stats_service")
    stats.record_request = mocker.AsyncMock()

    mocker.patch.object(svc, "engine")
    svc.engine.anonymize.return_value = _result()

    await svc.process(
        "a@b.c",
        store_result=True,
        use_cache=False,
        session=session,
        client_id="demo",
    )

    stats.record_request.assert_awaited()
    kwargs = stats.record_request.await_args.kwargs
    assert kwargs["session"] is session
    assert kwargs["cache_hit"] is False
    assert kwargs["client_id"] == "demo"
    cache.get.assert_not_called()
    cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_also_stores_stats(mocker):
    svc = AnonymizeService()
    session = mocker.Mock()

    cache = mocker.patch("app.services.anonymize_service.cache_service")
    cache.text_hash.return_value = "h" * 64
    cache.get = mocker.AsyncMock(
        return_value={
            "anonymized_text": "x",
            "detections": [],
            "stats": {},
            "processing_time_ms": 0.2,
            "detections_count": 0,
        }
    )

    stats = mocker.patch("app.services.anonymize_service.stats_service")
    stats.record_request = mocker.AsyncMock()

    await svc.process("a@b.c", use_cache=True, store_result=True, session=session)

    kwargs = stats.record_request.await_args.kwargs
    assert kwargs["cache_hit"] is True