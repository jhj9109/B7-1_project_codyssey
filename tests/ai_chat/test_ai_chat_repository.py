import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import User, ChatLog
from ai_chat import repository

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # 외래 키를 만족시키기 위한 테스트 유저 생성
    test_user = User(username="chatuser", hashed_password="hashed_pw")
    session.add(test_user)
    session.commit()
    session.refresh(test_user)
    
    try:
        yield session, test_user
    finally:
        session.close()

def test_chat_repository_lifecycle(db_session):
    session, user = db_session

    # 1. create_chat_log (1차 저장)
    log1 = repository.create_chat_log(db=session, user_id=user.id, user_message="첫 번째 질문")
    assert log1.id is not None
    assert log1.user_message == "첫 번째 질문"
    assert log1.ai_response is None

    # 2. update_chat_response (2차 저장)
    updated_log1 = repository.update_chat_response(
        db=session,
        chat_log=log1,
        ai_response="첫 번째 답변",
        error_status=None
    )
    assert updated_log1.ai_response == "첫 번째 답변"
    assert updated_log1.error_status is None

    # 3. 추가 로그 생성
    log2 = repository.create_chat_log(db=session, user_id=user.id, user_message="두 번째 질문")
    repository.update_chat_response(db=session, chat_log=log2, ai_response="두 번째 답변", error_status=None)

    log3 = repository.create_chat_log(db=session, user_id=user.id, user_message="세 번째 질문")
    repository.update_chat_response(db=session, chat_log=log3, ai_response="세 번째 답변", error_status=None)

    log4 = repository.create_chat_log(db=session, user_id=user.id, user_message="네 번째 질문")
    repository.update_chat_response(db=session, chat_log=log4, ai_response="오류 발생", error_status="AI_TIMEOUT")

    # 4. get_recent_chats_by_user_id (최신순 limit=3)
    recent_chats = repository.get_recent_chats_by_user_id(db=session, user_id=user.id, limit=3)
    assert len(recent_chats) == 3
    assert recent_chats[0].id == log4.id
    assert recent_chats[1].id == log3.id
    assert recent_chats[2].id == log2.id

    # 5. get_all_chats_by_user_id (전체 시간순)
    all_chats = repository.get_all_chats_by_user_id(db=session, user_id=user.id)
    assert len(all_chats) == 4
    assert all_chats[0].id == log1.id
    assert all_chats[-1].id == log4.id
