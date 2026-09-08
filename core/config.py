import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 애플리케이션 이름
    app_name: str = "Codyssey AI Chatbot"
    # 데이터베이스 연결 URL (SQLite 사용)
    database_url: str = "sqlite:///./chatbot.db"
    # Gemini AI API 키
    gemini_api_key: str = ""
    # JWT 서명에 사용할 시크릿 키
    secret_key: str = ""
    # JWT 암호화 알고리즘
    algorithm: str = ""
    # 토큰 만료 시간 (분)
    access_token_expire_minutes: int = 0
    # AI 응답 대기 시간 (초) - 타임아웃 처리에 사용
    ai_timeout_seconds: int = 10
    # CORS 허용 오리진 (쉼표로 구분하여 추가 오리진 등록 가능, 예: "http://<EC2_IP>:3000")
    cors_origins: str = ""
    # 프론트엔드 URL (루트 엔드포인트 리다이렉트 시 사용)
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env")

# 설정 인스턴스 생성 (앱 전체에서 공유)
# TDD 기반으로 환경 설정 구성 완료
settings = Settings()
