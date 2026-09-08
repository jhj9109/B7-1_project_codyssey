from typing import Optional, List
from sqlalchemy.orm import Session
from core import models

def get_recent_chats_by_user_id(db: Session, user_id: int, limit: int = 3) -> List[models.ChatLog]:
    """사용자의 최근 대화 기록을 최신순(내림차순)으로 조회합니다."""
    return (
        db.query(models.ChatLog)
        .filter(
            models.ChatLog.user_id == user_id,
            models.ChatLog.error_status.is_(None)  # 👈 에러 난 대화는 AI 기억에서 100% 필터링!
        )
        .order_by(models.ChatLog.id.desc())
        .limit(limit)
        .all()
    )

def create_chat_log(db: Session, user_id: int, user_message: str) -> models.ChatLog:
    """사용자의 질문을 1차로 데이터베이스에 저장합니다."""
    new_chat = models.ChatLog(user_id=user_id, user_message=user_message)
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return new_chat

def update_chat_response(
    db: Session,
    chat_log: models.ChatLog,
    ai_response: Optional[str],
    error_status: Optional[str]
) -> models.ChatLog:
    """AI 응답 및 에러 상태를 기존 채팅 로그에 2차로 업데이트합니다."""
    chat_log.ai_response = ai_response
    chat_log.error_status = error_status
    db.commit()
    db.refresh(chat_log)
    return chat_log

def get_all_chats_by_user_id(db: Session, user_id: int) -> List[models.ChatLog]:
    """사용자의 모든 과거 대화 기록을 시간순(오름차순)으로 조회합니다."""
    return (
        db.query(models.ChatLog)
        .filter(models.ChatLog.user_id == user_id)
        .order_by(models.ChatLog.id.asc())
        .all()
    )
