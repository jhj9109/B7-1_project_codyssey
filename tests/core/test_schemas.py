from datetime import datetime
from pydantic import ValidationError
import pytest

from core.schemas import ChatRequest, ChatResponse, Token, TokenData, UserCreate, UserResponse


def test_user_create_validation():
    # 1. 유효한 회원가입 데이터 (8자 이상, 영문+숫자 포함)
    user = UserCreate(username="testuser", password="password123")
    assert user.username == "testuser"

    # 2. 아이디가 3자 미만인 경우 (에러)
    with pytest.raises(ValidationError):
        UserCreate(username="ab", password="password123")

    # 3. 비밀번호가 8자 미만인 경우 (에러)
    with pytest.raises(ValidationError):
        UserCreate(username="testuser", password="pass1")

    # 4. 비밀번호에 숫자가 없는 경우 (에러)
    with pytest.raises(ValidationError):
        UserCreate(username="testuser", password="justpassword")

    # 5. 아이디에 허용되지 않은 특수문자가 포함된 경우 (에러)
    with pytest.raises(ValidationError):
        UserCreate(username="user@name", password="password123")


def test_user_response_schema():
    response = UserResponse(id=1, username="testuser", created_at=datetime.now())
    assert response.id == 1


def test_token_schema():
    token = Token(access_token="eyJ...", refresh_token="eyJ...", token_type="bearer")
    assert token.token_type == "bearer"
    assert token.refresh_token == "eyJ..."


def test_token_data_schema():
    token_data = TokenData(username="testuser")
    assert token_data.username == "testuser"


def test_chat_request_validation():
    req = ChatRequest(message="Hello AI")
    assert req.message == "Hello AI"
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_response_schema():
    res = ChatResponse(id=1, user_message="Hello AI", created_at=datetime.now())
    assert res.ai_response is None
    assert res.error_status is None
