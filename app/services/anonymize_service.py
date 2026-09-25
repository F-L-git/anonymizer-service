import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.anonymizer import get_engine, AnonymizationResult
from app.services.cache import cache_service
from app.services.stats import stats_service

logger = logging.getLogger(__name__)


class AnonymizeService:
    def __init__(self):
        self.engine = get_engine()

    async def process(
        self,
        text: str,
        rules: Optional[List[str]] = None,
        client_id: Optional[str] = None,
        store_result: bool = True,
        use_cache: bool = True,
        session: Optional[AsyncSession] = None,
    ) -> dict:
        request_id = str(uuid.uuid4())
        text_hash = cache_service.text_hash(text)

        # Cache lookup
        if use_cache:
            cached = await cache_service.get(text, rules)
            if cached:
                cached["request_id"] = request_id
                cached["cache_hit"] = True
                logger.info("cache_hit request_id=%s hash=%s", request_id, text_hash[:12])
                if store_result and session:
                    await stats_service.record_request(
                        session=session,
                        request_id=request_id,
                        client_id=client_id,
                        original_hash=text_hash,
                        original_length=len(text),
                        anonymized_length=len(cached["anonymized_text"]),
                        detections_count=cached.get("detections_count", 0),
                        detections=cached.get("detections", []),
                        stats=cached.get("stats", {}),
                        processing_time_ms=cached.get("processing_time_ms", 0.0),
                        cache_hit=True,
                    )
                return cached

        # Real processing
        result: AnonymizationResult = self.engine.anonymize(text, rule_names=rules)

        response = {
            "request_id": request_id,
            "anonymized_text": result.anonymized_text,
            "detections": [
                {
                    "rule_name": d.rule_name,
                    "type": d.type,
                    "original": d.original,
                    "masked": d.masked,
                    "start": d.start,
                    "end": d.end,
                }
                for d in result.detections
            ],
            "stats": result.stats,
            "processing_time_ms": result.processing_time_ms,
            "cache_hit": False,
            "detections_count": len(result.detections),
        }

        # Store in cache
        if use_cache:
            await cache_service.set(text, response, rules)

        # Persist
        if store_result and session:
            await stats_service.record_request(
                session=session,
                request_id=request_id,
                client_id=client_id,
                original_hash=text_hash,
                original_length=len(text),
                anonymized_length=len(result.anonymized_text),
                detections_count=len(result.detections),
                detections=response["detections"],
                stats=result.stats,
                processing_time_ms=result.processing_time_ms,
                cache_hit=False,
            )

        logger.info("anonymized request_id=%s detections=%s time_ms=%s", request_id, len(result.detections), result.processing_time_ms)
        return response


anonymize_service = AnonymizeService()
