from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, OAuth2PasswordBearer, HTTPBearer
from jose import JWTError, jwt
import bcrypt

from auth.dependencies import get_db
from auth import repository
from core import schemas
from core.config import settings

def get_password_hash(password: str) -> str:
    """비밀번호를 bcrypt 알고리즘을 사용해 암호화(단방향 해시)하여 반환합니다."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """사용자가 입력한 비밀번호와 DB에 저장된 암호화된 비밀번호가 일치하는지 검증합니다."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_token(data: dict, type: str, expires_delta: Optional[timedelta] = None) -> str:
    """주어진 데이터(페이로드)를 바탕으로 JWT 토큰을 생성합니다."""
    to_encode = data.copy()
    to_encode.update({"type": type})
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if type == "access":
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        else:
            # Refresh Token은 보통 7일 이상으로 길게 설정
            expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    # 토큰 만료 시간 추가
    to_encode.update({"exp": expire})
    # 시크릿 키와 알고리즘을 사용해 토큰 생성
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """주어진 데이터(페이로드)를 바탕으로 JWT Access Token을 생성합니다."""
    return create_token(data, "access", expires_delta)

# Refresh Token 생성 (신규 추가)
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return create_token(data, "refresh", expires_delta)

# Refresh Token 검증 함수 (신규 추가)
def verify_refresh_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        # 1. 토큰 타입 검증 (Access Token을 가지고 재발급을 시도하는 것 방지)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for refresh",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 2. 사용자 ID(username) 추출
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# FastAPI의 보안 의존성 처리 객체 (토큰이 없어도 403 대신 401 에러를 직접 반환할 수 있도록 auto_error=False 적용)
security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
        auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
        db = Depends(get_db)):
    """
    클라이언트가 보낸 JWT 토큰을 검증하고, 유효한 경우 현재 로그인된 사용자 객체를 반환합니다.
    토큰이 없거나 유효하지 않은 경우 401 상태 코드와 '로그인이 필요합니다.' 메시지를 반환합니다.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if auth is None or not auth.credentials:
        raise credentials_exception

    token = auth.credentials
    try:
        # 토큰 디코딩 및 검증
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        
        # 🔒 [필수 추가] 토큰 타입 검사: Access Token인지 확인
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception

        username = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = repository.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

