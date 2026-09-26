from app.core.anonymizer import AnonymizerEngine

def test_default_yaml_covers_inn_ip_card_name_date():
    e = AnonymizerEngine()  # config/rules.yaml
    names = {r["name"] for r in e.list_rules()}
    assert {"email", "phone_ru", "snils", "credit_card", "inn", "ip_address", "full_name_ru", "date"} <= names

    text = (
        "Иван Иванов карта 4111111111111111 ИНН 7707083893 "
        "ip 10.0.0.1 дата 12.05.1990"
    )
    r = e.anonymize(text)
    assert r.detections_count if False else len(r.detections) >= 4
    assert "4111111111111111" not in r.anonymized_text
    assert "7707083893" not in r.anonymized_text
    assert "10.0.0.1" not in r.anonymized_text
    assert "12.05.1990" not in r.anonymized_text