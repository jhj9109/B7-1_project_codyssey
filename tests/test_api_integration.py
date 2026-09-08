import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db

# 인메모리 테스트 DB 세팅
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_full_api_flow():
    # 1. 회원가입
    signup_res = client.post(
        "/api/auth/signup",
        json={"username": "flowuser", "password": "password123"}
    )
    assert signup_res.status_code == 201
    user_data = signup_res.json()
    assert user_data["username"] == "flowuser"

    # 2. 로그인
    login_res = client.post(
        "/api/auth/login",
        json={"username": "flowuser", "password": "password123"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # 3. AI 채팅 전송 (Gemini API 키가 없으므로 더미 응답 반환됨)
    chat_res = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"message": "안녕하세요!"}
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["user_message"] == "안녕하세요!"
    assert chat_data["ai_response"] is not None
    assert chat_data["error_status"] is None

    # 4. 내 대화 내역 조회
    history_res = client.get("/api/me/chats", headers=auth_headers)
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) == 1
    assert history_data[0]["user_message"] == "안녕하세요!"

    # 5. 로그아웃
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

def test_unauthenticated_requests():
    # 1. 토큰 없이 채팅 API 요청 시 401 반환 및 '로그인이 필요합니다.' 메시지 확인
    res1 = client.post("/api/chat", json={"message": "인증 없는 질문"})
    assert res1.status_code == 401
    assert res1.json().get("detail") == "로그인이 필요합니다."

    # 2. 토큰 없이 대화 내역 조회 시 401 반환 및 '로그인이 필요합니다.' 메시지 확인
    res2 = client.get("/api/me/chats")
    assert res2.status_code == 401
    assert res2.json().get("detail") == "로그인이 필요합니다."

    # 3. 위조/만료된 토큰으로 요청 시 401 반환 및 '로그인이 필요합니다.' 메시지 확인
    res3 = client.get("/api/me/chats", headers={"Authorization": "Bearer invalid_token_12345"})
    assert res3.status_code == 401
    assert res3.json().get("detail") == "로그인이 필요합니다."

def test_root_redirect():
    # 백엔드 루트 GET / 요청 시 프론트엔드 URL로 리다이렉트 (307 Temporary Redirect)
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (307, 302)
    assert "location" in res.headers

