from typing import Optional
from sqlalchemy.orm import Session
from core import models

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """사용자 이름(username)으로 사용자를 조회합니다."""
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """사용자 고유 식별자(id)로 사용자를 조회합니다."""
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, username: str, hashed_password: str) -> models.User:
    """새로운 사용자를 데이터베이스에 저장합니다."""
    new_user = models.User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
