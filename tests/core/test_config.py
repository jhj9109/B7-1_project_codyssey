import os
from core.config import Settings

def test_settings_default_values():
    settings = Settings(
        _env_file=None,
        gemini_api_key="test_key",
        secret_key="test_secret",
        algorithm="HS256",
        access_token_expire_minutes=15
    )
    assert settings.app_name == "Codyssey AI Chatbot"
    assert settings.database_url == "sqlite:///./chatbot.db"
    assert settings.ai_timeout_seconds == 20
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.refresh_token_expire_days == 7
    assert settings.cors_origins == ""
    assert settings.frontend_url == "http://localhost:3000"

def test_settings_extra_ignored():
    # 정의되지 않은 추가 환경변수(extra)가 있어도 에러 없이 무시되는지 검증
    settings = Settings(
        _env_file=None,
        gemini_api_key="test_key",
        secret_key="test_secret",
        algorithm="HS256",
        extra_unknown_field="some_value"
    )
    assert settings.gemini_api_key == "test_key"

