from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AnonymizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000, description="Text to anonymize")
    rules: Optional[List[str]] = Field(
        None, description="Optional list of rule names to apply. If omitted, all enabled rules are used."
    )
    client_id: Optional[str] = Field(None, max_length=128, description="Optional client identifier for stats")
    store_result: bool = Field(True, description="Whether to store the result in DB")
    use_cache: bool = Field(True, description="Whether to use cache for identical texts")


class DetectionOut(BaseModel):
    rule_name: str
    type: str
    original: str
    masked: str
    start: int
    end: int


class AnonymizeResponse(BaseModel):
    request_id: str
    anonymized_text: str
    detections: List[DetectionOut]
    stats: Dict[str, int]
    processing_time_ms: float
    cache_hit: bool = False
    detections_count: int = 0


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    type: str = Field(..., min_length=1, max_length=64)
    pattern: str = Field(..., min_length=1)
    mask_strategy: str = Field("full_mask")
    priority: int = Field(100, ge=1, le=1000)
    enabled: bool = True
    description: Optional[str] = None
    example: Optional[str] = None

    @field_validator("mask_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        allowed = {
            "full_mask", "email_mask", "phone_mask", "snils_mask",
            "card_mask", "ip_mask", "name_mask", "date_mask",
            "partial", "hash", "redact"
        }
        if v not in allowed:
            raise ValueError(f"mask_strategy must be one of {allowed}")
        return v


class RuleOut(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    priority: int
    enabled: bool
    example: Optional[str] = None
    mask_strategy: str


class StatsSummary(BaseModel):
    total_requests: int
    total_detections: int
    detections_by_type: Dict[str, int]
    avg_processing_ms: float
    cache_hit_rate: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str


class MessageResponse(BaseModel):
    message: str
    details: Optional[Any] = None
