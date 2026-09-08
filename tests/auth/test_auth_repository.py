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
