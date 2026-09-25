from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.models import ProcessedRequest, UsageStat

logger = logging.getLogger(__name__)


class StatsService:
    async def record_request(
        self,
        session: AsyncSession,
        request_id: str,
        client_id: Optional[str],
        original_hash: str,
        original_length: int,
        anonymized_length: int,
        detections_count: int,
        detections: list,
        stats: Dict[str, int],
        processing_time_ms: float,
        cache_hit: bool,
    ) -> None:
        record = ProcessedRequest(
            request_id=request_id,
            client_id=client_id,
            original_hash=original_hash,
            original_length=original_length,
            anonymized_length=anonymized_length,
            detections_count=detections_count,
            detections=[{"rule": d["rule_name"], "type": d["type"]} for d in detections] if detections else None,
            stats=stats,
            processing_time_ms=processing_time_ms,
            cache_hit=cache_hit,
        )
        session.add(record)

    async def get_summary(
        self,
        session: AsyncSession,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> dict:
        q = select(
            func.count(ProcessedRequest.id).label("total_requests"),
            func.coalesce(func.sum(ProcessedRequest.detections_count), 0).label("total_detections"),
            func.coalesce(func.avg(ProcessedRequest.processing_time_ms), 0.0).label("avg_ms"),
            func.coalesce(func.sum(ProcessedRequest.cache_hit.cast(Integer)), 0).label("cache_hits"),
        )
        if since:
            q = q.where(ProcessedRequest.created_at >= since)
        if until:
            q = q.where(ProcessedRequest.created_at <= until)

        result = await session.execute(q)
        row = result.one()

        total_requests = int(row.total_requests or 0)
        cache_hits = int(row.cache_hits or 0)
        cache_hit_rate = (cache_hits / total_requests) if total_requests else 0.0

        # Aggregate detections by type (simple approach)
        detections_by_type: Dict[str, int] = {}
        q2 = select(ProcessedRequest.stats).where(ProcessedRequest.stats.isnot(None))
        if since:
            q2 = q2.where(ProcessedRequest.created_at >= since)
        if until:
            q2 = q2.where(ProcessedRequest.created_at <= until)
        rows = await session.execute(q2)
        for (stats,) in rows:
            if stats:
                for k, v in stats.items():
                    detections_by_type[k] = detections_by_type.get(k, 0) + int(v)

        return {
            "total_requests": total_requests,
            "total_detections": int(row.total_detections or 0),
            "detections_by_type": detections_by_type,
            "avg_processing_ms": round(float(row.avg_ms or 0.0), 3),
            "cache_hit_rate": round(cache_hit_rate, 4),
            "period_start": since,
            "period_end": until,
        }


stats_service = StatsService()
