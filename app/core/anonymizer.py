"""
Core anonymization engine.

Supports configurable regex rules with different masking strategies.
Rules can be loaded from YAML or added dynamically at runtime.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
import logging

logger = logging.getLogger(__name__)


class MaskStrategy(str, Enum):
    FULL_MASK = "full_mask"
    EMAIL_MASK = "email_mask"
    PHONE_MASK = "phone_mask"
    SNILS_MASK = "snils_mask"
    CARD_MASK = "card_mask"
    IP_MASK = "ip_mask"
    NAME_MASK = "name_mask"
    DATE_MASK = "date_mask"
    PARTIAL = "partial"
    HASH = "hash"
    REDACT = "redact"


@dataclass
class AnonymizationRule:
    name: str
    type: str
    pattern: str
    mask_strategy: str
    priority: int = 100
    enabled: bool = True
    description: str = ""
    example: str = ""
    compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.compiled is None:
            flags = re.IGNORECASE | re.UNICODE
            self.compiled = re.compile(self.pattern, flags)


@dataclass
class Detection:
    rule_name: str
    type: str
    original: str
    masked: str
    start: int
    end: int


@dataclass
class AnonymizationResult:
    original_text: str
    anonymized_text: str
    detections: List[Detection]
    stats: Dict[str, int]
    processing_time_ms: float = 0.0
    cache_hit: bool = False


# ---------------------------------------------------------------------------
# Masking functions
# ---------------------------------------------------------------------------

def _mask_email(match: str) -> str:
    if "@" not in match:
        return "***"
    local, domain = match.rsplit("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def _mask_phone(match: str) -> str:
    digits = re.sub(r"\D", "", match)
    if len(digits) < 10:
        return re.sub(r"\d", "*", match)
    # Keep country code / first 3 and last 2
    # Simple heuristic for RU numbers
    if match.startswith("+7") or match.startswith("8") or match.startswith("7"):
        # +7 (999) ***-**-67 style
        return re.sub(
            r"(\+?[78]?\s*\(?\d{3}\)?\s*)\d{3}(\s*\-?\s*)\d{2}(\s*\-?\s*)\d{2}",
            r"\1***\2**\3" + digits[-2:],
            match,
            count=1,
        )
    # Generic: mask middle
    return match[:4] + "*" * (len(match) - 6) + match[-2:] if len(match) > 6 else "*" * len(match)


def _mask_snils(match: str) -> str:
    # 123-456-789-00 → ***-***-***-00
    parts = match.split("-")
    if len(parts) == 4:
        return f"***-***-***-{parts[3]}"
    return "***-***-***-**"


def _mask_card(match: str) -> str:
    digits = re.sub(r"\D", "", match)
    if len(digits) < 13:
        return "*" * len(match)
    last4 = digits[-4:]
    # Preserve separators roughly
    return re.sub(r"\d", "*", match[:-4]) + last4 if len(match) > 4 else f"**** **** **** {last4}"


def _mask_ip(match: str) -> str:
    parts = match.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.***.***.***"
    return "*.*.*.*"


def _mask_name(match: str) -> str:
    parts = match.split()
    if not parts:
        return "***"
    initials = [p[0] + "." for p in parts if p]
    return " ".join(initials)


def _mask_date(match: str) -> str:
    return re.sub(r"\d", "*", match)


def _full_mask(match: str) -> str:
    return "*" * len(match)


def _hash_mask(match: str) -> str:
    h = hashlib.sha256(match.encode("utf-8")).hexdigest()[:12]
    return f"[hash:{h}]"


def _redact(match: str) -> str:
    return "[REDACTED]"


MASK_FUNCTIONS: Dict[str, Callable[[str], str]] = {
    MaskStrategy.FULL_MASK: _full_mask,
    MaskStrategy.EMAIL_MASK: _mask_email,
    MaskStrategy.PHONE_MASK: _mask_phone,
    MaskStrategy.SNILS_MASK: _mask_snils,
    MaskStrategy.CARD_MASK: _mask_card,
    MaskStrategy.IP_MASK: _mask_ip,
    MaskStrategy.NAME_MASK: _mask_name,
    MaskStrategy.DATE_MASK: _mask_date,
    MaskStrategy.PARTIAL: lambda m: m[0] + "*" * (len(m) - 2) + m[-1] if len(m) > 2 else "**",
    MaskStrategy.HASH: _hash_mask,
    MaskStrategy.REDACT: _redact,
}


class AnonymizerEngine:
    """Main anonymization engine with pluggable rules."""

    def __init__(self, rules: Optional[List[AnonymizationRule]] = None):
        self.rules: List[AnonymizationRule] = []
        if rules:
            for r in rules:
                self.add_rule(r)
        else:
            self._load_default_rules()

    def _load_default_rules(self) -> None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "rules.yaml"
        if config_path.exists():
            self.load_from_yaml(str(config_path))
        else:
            logger.warning("rules.yaml not found, using empty rule set")

    def load_from_yaml(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules_data = data.get("rules", [])
        for item in rules_data:
            rule = AnonymizationRule(
                name=item["name"],
                type=item.get("type", item["name"]),
                pattern=item["pattern"],
                mask_strategy=item.get("mask_strategy", "full_mask"),
                priority=item.get("priority", 100),
                enabled=item.get("enabled", True),
                description=item.get("description", ""),
                example=item.get("example", ""),
            )
            self.add_rule(rule)
        logger.info("loaded_rules count=%s path=%s", len(self.rules), path)

    def add_rule(self, rule: AnonymizationRule) -> None:
        # Replace existing rule with same name
        self.rules = [r for r in self.rules if r.name != rule.name]
        if rule.enabled:
            self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def remove_rule(self, name: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.name != name]
        return len(self.rules) < before

    def list_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": r.name,
                "type": r.type,
                "description": r.description,
                "priority": r.priority,
                "enabled": r.enabled,
                "example": r.example,
                "mask_strategy": r.mask_strategy,
            }
            for r in sorted(self.rules, key=lambda x: x.priority)
        ]

    def anonymize(self, text: str, rule_names: Optional[List[str]] = None) -> AnonymizationResult:
        import time
        start = time.perf_counter()

        if not text:
            return AnonymizationResult(
                original_text=text,
                anonymized_text=text,
                detections=[],
                stats={},
                processing_time_ms=0.0,
            )

        active_rules = self.rules
        if rule_names:
            name_set = set(rule_names)
            active_rules = [r for r in self.rules if r.name in name_set]

        # Collect all matches with positions (non-overlapping, higher priority first)
        candidates: List[Tuple[int, int, AnonymizationRule, str]] = []
        for rule in active_rules:
            for m in rule.compiled.finditer(text):
                candidates.append((m.start(), m.end(), rule, m.group(0)))

        # Sort by start, then by priority (lower number = higher priority), then longer match
        candidates.sort(key=lambda x: (x[0], x[2].priority, -(x[1] - x[0])))

        # Greedy non-overlapping selection
        selected: List[Tuple[int, int, AnonymizationRule, str]] = []
        last_end = -1
        for start_pos, end_pos, rule, original in candidates:
            if start_pos >= last_end:
                selected.append((start_pos, end_pos, rule, original))
                last_end = end_pos

        # Apply masks from the end so positions stay valid
        result_chars = list(text)
        detections: List[Detection] = []
        stats: Dict[str, int] = {}

        for start_pos, end_pos, rule, original in sorted(selected, key=lambda x: -x[0]):
            mask_fn = MASK_FUNCTIONS.get(rule.mask_strategy, _full_mask)
            masked = mask_fn(original)
            result_chars[start_pos:end_pos] = list(masked)
            detections.append(
                Detection(
                    rule_name=rule.name,
                    type=rule.type,
                    original=original,
                    masked=masked,
                    start=start_pos,
                    end=end_pos,
                )
            )
            stats[rule.type] = stats.get(rule.type, 0) + 1

        # Reverse detections to keep original order
        detections.reverse()

        elapsed = (time.perf_counter() - start) * 1000
        anonymized = "".join(result_chars)

        return AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized,
            detections=detections,
            stats=stats,
            processing_time_ms=round(elapsed, 3),
        )


# Singleton for convenience
_engine: Optional[AnonymizerEngine] = None


def get_engine() -> AnonymizerEngine:
    global _engine
    if _engine is None:
        _engine = AnonymizerEngine()
    return _engine
