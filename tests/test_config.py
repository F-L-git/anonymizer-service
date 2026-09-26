from app.core.config import Settings, get_settings
from app.core import anonymizer as mod


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.cache_ttl == 3600
    assert s.app_version == "1.0.0"


def test_get_settings_cached():
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()


def test_get_engine_singleton():
    mod._engine = None
    assert mod.get_engine() is mod.get_engine()
    mod._engine = None