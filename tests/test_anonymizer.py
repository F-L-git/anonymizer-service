import pytest
from app.core.anonymizer import AnonymizerEngine, AnonymizationRule


@pytest.fixture
def engine():
    e = AnonymizerEngine(rules=[])
    # Load minimal rules for tests
    e.add_rule(AnonymizationRule(
        name="email",
        type="email",
        pattern=r'(?i)\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        mask_strategy="email_mask",
        priority=10,
    ))
    e.add_rule(AnonymizationRule(
        name="phone_ru",
        type="phone",
        pattern=r'(?:\+7|8|7)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
        mask_strategy="phone_mask",
        priority=20,
    ))
    e.add_rule(AnonymizationRule(
        name="snils",
        type="snils",
        pattern=r'\b\d{3}-\d{3}-\d{3}-\d{2}\b',
        mask_strategy="snils_mask",
        priority=40,
    ))
    e.add_rule(AnonymizationRule(
        name="passport_ru",
        type="passport",
        pattern=r'\b\d{4}\s?\d{6}\b',
        mask_strategy="full_mask",
        priority=30,
    ))
    return e


def test_email_masking(engine):
    text = "Contact me at john.doe@example.com please"
    result = engine.anonymize(text)
    assert "john.doe@example.com" not in result.anonymized_text
    assert "@example.com" in result.anonymized_text
    assert result.stats.get("email") == 1
    assert len(result.detections) == 1


def test_phone_masking(engine):
    text = "Call +7 (999) 123-45-67 now"
    result = engine.anonymize(text)
    assert "123-45-67" not in result.anonymized_text or "***" in result.anonymized_text
    assert result.stats.get("phone") == 1


def test_snils_masking(engine):
    text = "SNILS: 123-456-789-00"
    result = engine.anonymize(text)
    assert "123-456-789-00" not in result.anonymized_text
    assert "***-***-***-00" in result.anonymized_text
    assert result.stats.get("snils") == 1


def test_passport_masking(engine):
    text = "Passport 4510 123456"
    result = engine.anonymize(text)
    assert "4510 123456" not in result.anonymized_text
    assert "*" in result.anonymized_text
    assert result.stats.get("passport") == 1


def test_multiple_detections(engine):
    text = "Email: a@b.com, phone: +79991234567, SNILS 111-222-333-44"
    result = engine.anonymize(text)
    assert result.detections_count if hasattr(result, "detections_count") else len(result.detections) >= 2
    assert len(result.detections) >= 2


def test_empty_text(engine):
    result = engine.anonymize("")
    assert result.anonymized_text == ""
    assert result.detections == []


def test_no_matches(engine):
    text = "Just ordinary text without PII"
    result = engine.anonymize(text)
    assert result.anonymized_text == text
    assert result.detections == []


def test_add_custom_rule(engine):
    engine.add_rule(AnonymizationRule(
        name="custom_id",
        type="custom",
        pattern=r"ID-\d{5}",
        mask_strategy="redact",
        priority=5,
    ))
    text = "User ID-12345 is here"
    result = engine.anonymize(text)
    assert "ID-12345" not in result.anonymized_text
    assert "[REDACTED]" in result.anonymized_text
