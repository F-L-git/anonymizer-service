from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.anonymizer import AnonymizationRule, get_engine
from app.db.session import get_db
from app.models.models import RuleConfig
from app.schemas.schemas import (
    AnonymizeRequest,
    AnonymizeResponse,
    DetectionOut,
    HealthResponse,
    MessageResponse,
    RuleCreate,
    RuleOut,
    StatsSummary,
)
from app.services.anonymize_service import anonymize_service
from app.services.cache import cache_service
from app.services.stats import stats_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    db_status = "ok"
    redis_status = "ok"
    try:
        # lightweight checks
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception:
        db_status = "unavailable"
    try:
        if not await cache_service.ping():
            redis_status = "unavailable"
    except Exception:
        redis_status = "unavailable"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
    )


@router.post(
    "/anonymize",
    response_model=AnonymizeResponse,
    tags=["Anonymization"],
    summary="Anonymize text synchronously",
)
async def anonymize(
    body: AnonymizeRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await anonymize_service.process(
            text=body.text,
            rules=body.rules,
            client_id=body.client_id,
            store_result=body.store_result,
            use_cache=body.use_cache,
            session=db,
        )
        return AnonymizeResponse(
            request_id=result["request_id"],
            anonymized_text=result["anonymized_text"],
            detections=[DetectionOut(**d) for d in result["detections"]],
            stats=result["stats"],
            processing_time_ms=result["processing_time_ms"],
            cache_hit=result["cache_hit"],
            detections_count=result["detections_count"],
        )
    except Exception as e:
        logger.exception("anonymize_error: %s", e)
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.get("/rules", response_model=List[RuleOut], tags=["Rules"])
async def list_rules():
    engine = get_engine()
    return [RuleOut(**r) for r in engine.list_rules()]


@router.post(
    "/rules",
    response_model=RuleOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Rules"],
    summary="Add or update an anonymization rule",
)
async def add_rule(body: RuleCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Validate regex
        import re
        re.compile(body.pattern)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")

    rule = AnonymizationRule(
        name=body.name,
        type=body.type,
        pattern=body.pattern,
        mask_strategy=body.mask_strategy,
        priority=body.priority,
        enabled=body.enabled,
        description=body.description or "",
        example=body.example or "",
    )
    engine = get_engine()
    engine.add_rule(rule)

    # Persist to DB
    existing = await db.execute(select(RuleConfig).where(RuleConfig.name == body.name))
    db_rule = existing.scalar_one_or_none()
    if db_rule:
        db_rule.type = body.type
        db_rule.pattern = body.pattern
        db_rule.mask_strategy = body.mask_strategy
        db_rule.priority = body.priority
        db_rule.enabled = body.enabled
        db_rule.description = body.description
        db_rule.example = body.example
    else:
        db_rule = RuleConfig(
            name=body.name,
            type=body.type,
            pattern=body.pattern,
            mask_strategy=body.mask_strategy,
            priority=body.priority,
            enabled=body.enabled,
            description=body.description,
            example=body.example,
        )
        db.add(db_rule)

    return RuleOut(
        name=rule.name,
        type=rule.type,
        description=rule.description,
        priority=rule.priority,
        enabled=rule.enabled,
        example=rule.example,
        mask_strategy=rule.mask_strategy,
    )


@router.delete("/rules/{name}", response_model=MessageResponse, tags=["Rules"])
async def delete_rule(name: str, db: AsyncSession = Depends(get_db)):
    engine = get_engine()
    removed = engine.remove_rule(name)
    if not removed:
        raise HTTPException(status_code=404, detail="Rule not found")

    existing = await db.execute(select(RuleConfig).where(RuleConfig.name == name))
    db_rule = existing.scalar_one_or_none()
    if db_rule:
        await db.delete(db_rule)

    return MessageResponse(message=f"Rule '{name}' removed")


@router.get("/stats", response_model=StatsSummary, tags=["Statistics"])
async def get_stats(
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    summary = await stats_service.get_summary(db, since=since, until=until)
    return StatsSummary(**summary)
