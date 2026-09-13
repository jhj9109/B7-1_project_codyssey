from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from auth import repository, security
from core import schemas

def create_user(user: schemas.UserCreate, db: Session) -> schemas.UserResponse:
    """
    회원가입 비즈니스 로직:
    아이디 중복을 검사하고, 비밀번호를 해싱한 뒤 DB에 유저를 생성합니다.
    """
    db_user = repository.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already registered")

    # 비밀번호 안전하게 암호화
    hashed_password = security.get_password_hash(user.password)

    new_user = repository.create_user(db, username=user.username, hashed_password=hashed_password)
    return new_user

def authenticate_user(username: str, password: str, db: Session) -> schemas.Token:
    """
    로그인 비즈니스 로직:
    유저 존재 여부와 비밀번호를 검증하고, 성공 시 JWT 토큰을 발급합니다.
    """
    user = repository.get_user_by_username(db, username=username)
    if not user or not security.verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 검증 성공 시 JWT 토큰 생성
    access_token = security.create_access_token(data={"sub": username})
    refresh_token = security.create_refresh_token(data={"sub": username})

    # 2. 둘 다 담아서 반환
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

def reissue_tokens(refresh_token: str, db: Session) -> schemas.Token:
    """
    토큰 재발급 비즈니스 로직:
    Refresh Token을 검증하고 새로운 Access Token (및 Refresh Token)을 반환합니다.
    """
    # 1. Refresh Token 검증 및 username 추출
    username = security.verify_refresh_token(refresh_token)

    # 2. 유저 존재 여부 확인
    user = repository.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # 3. 새로운 토큰 발급 (Token Rotation: 보안을 위해 Refresh Token도 함께 새것으로 교체 권장)
    new_access_token = security.create_access_token(data={"sub": username})
    new_refresh_token = security.create_refresh_token(data={"sub": username})

    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )
