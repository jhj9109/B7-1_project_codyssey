import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from core.config import settings
from core.database import engine, Base
from auth.router import router as auth_router
from ai_chat.router import router as chat_router

# 애플리케이션 시작 시 데이터베이스에 정의된 모든 테이블을 생성합니다.
Base.metadata.create_all(bind=engine)

# 로깅 환경 설정
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("chatbot")

# FastAPI 앱 인스턴스 생성
app = FastAPI(title=settings.app_name)

# Next.js 프론트엔드 연동을 위한 CORS 설정
# 로컬 개발 기본 오리진 및 환경 변수로 추가된 오리진 병합
allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
if settings.cors_origins:
    extra_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    allowed_origins.extend(extra_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(chat_router)

@app.get("/")
def read_root():
    """백엔드 루트 접속 시 Next.js 프론트엔드 서버로 리다이렉트합니다."""
    return RedirectResponse(url=settings.frontend_url)