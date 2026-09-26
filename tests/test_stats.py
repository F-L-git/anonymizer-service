import pytest
from app.services.stats import StatsService
from app.models.models import ProcessedRequest


@pytest.mark.asyncio
async def test_record_request_adds_row(mocker):
    session = mocker.Mock()
    session.add = mocker.Mock()

    await StatsService().record_request(
        session=session,
        request_id="r1",
        client_id="c1",
        original_hash="abc",
        original_length=10,
        anonymized_length=8,
        detections_count=1,
        detections=[{"rule_name": "email", "type": "email"}],
        stats={"email": 1},
        processing_time_ms=1.5,
        cache_hit=False,
    )

    session.add.assert_called_once()
    rec = session.add.call_args[0][0]
    assert isinstance(rec, ProcessedRequest)
    assert rec.request_id == "r1"
    assert rec.detections == [{"rule": "email", "type": "email"}]


@pytest.mark.asyncio
async def test_get_summary_empty(mocker):
    row = mocker.Mock(total_requests=0, total_detections=0, avg_ms=0, cache_hits=0)

    agg = mocker.Mock()
    agg.one.return_value = row

    stats_rows = mocker.Mock()
    stats_rows.__iter__ = lambda self: iter([])

    session = mocker.Mock()
    session.execute = mocker.AsyncMock(side_effect=[agg, stats_rows])

    summary = await StatsService().get_summary(session)
    assert summary["total_requests"] == 0
    assert summary["cache_hit_rate"] == 0.0
    assert summary["detections_by_type"] == {}
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_summary_aggregates_types_and_hit_rate(mocker):
    row = mocker.Mock(total_requests=4, total_detections=5, avg_ms=2.5, cache_hits=2)

    agg = mocker.Mock()
    agg.one.return_value = row

    stats_rows = [({"email": 2},), ({"phone": 1, "email": 1},)]

    session = mocker.Mock()
    session.execute = mocker.AsyncMock(side_effect=[agg, stats_rows])

    summary = await StatsService().get_summary(session)
    assert summary["total_requests"] == 4
    assert summary["total_detections"] == 5
    assert summary["cache_hit_rate"] == 0.5
    assert summary["detections_by_type"] == {"email": 3, "phone": 1}
    assert summary["avg_processing_ms"] == 2.5