from app.infrastructure.config.settings import get_settings


def test_settings_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-backend")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://tester:secret@localhost:5432/test_db")
    monkeypatch.setenv("API_V1_PREFIX", "/api/custom/")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "test-backend"
    assert settings.database_url == "postgresql+psycopg://tester:secret@localhost:5432/test_db"
    assert settings.api_v1_prefix == "/api/custom"
