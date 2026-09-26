import pytest
from pydantic import ValidationError
from app.schemas.schemas import AnonymizeRequest, RuleCreate


def test_text_too_long():
    with pytest.raises(ValidationError):
        AnonymizeRequest(text="x" * 1_000_001)


def test_defaults():
    r = AnonymizeRequest(text="ok")
    assert r.store_result is True
    assert r.use_cache is True
    assert r.rules is None


def test_priority_bounds():
    with pytest.raises(ValidationError):
        RuleCreate(name="n", type="t", pattern="a", priority=0)
    with pytest.raises(ValidationError):
        RuleCreate(name="n", type="t", pattern="a", priority=1001)


def test_mask_strategy_allowed():
    RuleCreate(name="n", type="t", pattern="a", mask_strategy="hash")
    with pytest.raises(ValidationError):
        RuleCreate(name="n", type="t", pattern="a", mask_strategy="nope")