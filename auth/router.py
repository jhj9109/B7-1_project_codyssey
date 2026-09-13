from typing import Optional

from fastapi import APIRouter, Depends, status, Response, Cookie, HTTPException
from auth import service, validators, security
from auth.dependencies import get_db
from core import schemas

# 라우터 초기 설정
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db = Depends(get_db)):
    """
    회원가입 API: 
    사용자의 아이디와 비밀번호를 받아 새 계정을 생성합니다.
    """
    # 비즈니스 로직은 service 계층에 위임
    return service.create_user(user=user, db=db)

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    user_data: schemas.UserLogin, 
    response: Response,  # FastAPI가 Response 객체를 주입해줌
    db = Depends(get_db)
):
    """
    로그인 API:
    - Access Token은 JSON 응답 바디로 반환
    - Refresh Token은 HttpOnly 쿠키로 세팅
    """
    tokens = service.authenticate_user(
        username=user_data.username, 
        password=user_data.password, 
        db=db
    )
    
    # 🍪 Refresh Token을 HttpOnly 쿠키로 굽기 (JWT exp와 100% 동일한 TTL 공유)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,        # XSS 공격 방지 (JS 접근 불가)
        secure=False,         # 로컬(http) 개발 시 False, 배포(https) 시 True
        samesite="lax",       # CSRF 보호 설정
        max_age=security.get_refresh_token_expire_seconds(),
    )
    
    return tokens

@router.post("/refresh", response_model=schemas.Token)
def refresh_access_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),  # 🍪 쿠키에서 'refresh_token' 파싱
    db = Depends(get_db)
):
    """
    토큰 재발급 API:
    - 클라이언트 쿠키에 있는 refresh_token을 읽어서 검증 후 재발급
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing from cookies",
        )
    
    # 새로운 토큰 생성 (Refresh Token Rotation)
    new_tokens = service.reissue_tokens(refresh_token=refresh_token, db=db)
    
    # 🍪 새로 발급된 Refresh Token으로 쿠키 갱신 (JWT exp와 100% 동일한 TTL 공유)
    response.set_cookie(
        key="refresh_token",
        value=new_tokens.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=security.get_refresh_token_expire_seconds(),
    )
    
    return new_tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response):
    """
    로그아웃 API:
    - 브라우저에 저장된 refresh_token 쿠키를 삭제
    """
    response.delete_cookie(key="refresh_token")
    return {"message": "Successfully logged out"}