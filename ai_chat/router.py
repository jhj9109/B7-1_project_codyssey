from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core import models, schemas
from core.database import get_db 
from auth.security import get_current_user
from ai_chat import service

# 라우터 초기화
# prefix: api 주소의 접두사, tags: swagger 문서에서 그룹명
router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=schemas.ChatResponse)
async def chat(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    사용자의 질문을 수신하여 AI 응답을 생성하고 저장한 뒤 반환합니다.
    (실제 처리 로직 및 DB 트랜잭션은 service/repository 계층에 위임)
    """
    return await service.process_chat(
        db=db,
        user_id=current_user.id,
        message=request.message
    )

@router.get("/me/chats", response_model=List[schemas.ChatResponse])
def get_my_chats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    현재 로그인된 사용자의 모든 과거 채팅 로그를 시간순(오름차순)으로 반환합니다.
    """
    return service.get_chat_history(db=db, user_id=current_user.id)

