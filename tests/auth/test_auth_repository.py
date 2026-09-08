import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import User
from auth import repository

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_create_and_get_user(db_session):
    # 1. 사용자 생성
    user = repository.create_user(
        db=db_session,
        username="testuser",
        hashed_password="hashed_password_123"
    )
    assert user.id is not None
    assert user.username == "testuser"
    assert user.hashed_password == "hashed_password_123"

    # 2. username으로 사용자 조회
    found_by_name = repository.get_user_by_username(db=db_session, username="testuser")
    assert found_by_name is not None
    assert found_by_name.id == user.id

    # 3. id로 사용자 조회
    found_by_id = repository.get_user_by_id(db=db_session, user_id=user.id)
    assert found_by_id is not None
    assert found_by_id.username == "testuser"

    # 4. 존재하지 않는 사용자 조회
    not_found = repository.get_user_by_username(db=db_session, username="nonexistent")
    assert not_found is None

def test_token_contains_exp_and_iat():
    from jose import jwt
    from auth import security
    from core.config import settings

    access_token = security.create_access_token(data={"sub": "tokentester"})
    payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.algorithm])

    assert payload["sub"] == "tokentester"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
    assert payload["exp"] > payload["iat"]

def test_refresh_token_expiration_longer_than_access():
    from jose import jwt
    from auth import security
    from core.config import settings

    access_token = security.create_access_token(data={"sub": "tokentester"})
    refresh_token = security.create_refresh_token(data={"sub": "tokentester"})

    access_payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.algorithm])
    refresh_payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])

    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]

def test_token_exp_matches_helper_seconds():
    from jose import jwt
    from auth import security
    from core.config import settings

    access_token = security.create_access_token(data={"sub": "tokentester"})
    refresh_token = security.create_refresh_token(data={"sub": "tokentester"})

    access_payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.algorithm])
    refresh_payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])

    # JWT exp - iat 차이가 helper 반환 초(seconds)와 정확히 일치(또는 1초 이내)하는지 검증
    expected_access_seconds = security.get_access_token_expire_seconds()
    expected_refresh_seconds = security.get_refresh_token_expire_seconds()

    assert abs((access_payload["exp"] - access_payload["iat"]) - expected_access_seconds) <= 1
    assert abs((refresh_payload["exp"] - refresh_payload["iat"]) - expected_refresh_seconds) <= 1
