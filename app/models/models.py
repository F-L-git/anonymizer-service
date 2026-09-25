from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProcessedRequest(Base):
    __tablename__ = "processed_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    original_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 of original
    original_length: Mapped[int] = mapped_column(Integer)
    anonymized_length: Mapped[int] = mapped_column(Integer)
    detections_count: Mapped[int] = mapped_column(Integer, default=0)
    detections: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    stats: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    processing_time_ms: Mapped[float] = mapped_column(default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RuleConfig(Base):
    """Optional DB-backed rules (overrides / extends YAML)."""
    __tablename__ = "rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(64))
    pattern: Mapped[str] = mapped_column(Text)
    mask_strategy: Mapped[str] = mapped_column(String(32), default="full_mask")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UsageStat(Base):
    __tablename__ = "usage_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_detections: Mapped[int] = mapped_column(Integer, default=0)
    detections_by_type: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    avg_processing_ms: Mapped[float] = mapped_column(default=0.0)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0)
