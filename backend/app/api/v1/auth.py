from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.api.v1.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)

router = APIRouter()


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth/refresh",
    )


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    # Look up tenant, auto-create if it doesn't exist
    result = await db.execute(select(Tenant).where(Tenant.slug == body.tenant_slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name=body.tenant_slug, slug=body.tenant_slug)
        db.add(tenant)
        await db.flush()

    # Check existing email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token in DB
    db_token = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_token)

    _set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(message="Login successful")


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    old_token = request.cookies.get("refresh_token")
    if not old_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_token(old_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Check DB
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == old_token, RefreshToken.is_revoked == False
        )
    )
    db_token = result.scalar_one_or_none()
    if not db_token:
        raise HTTPException(status_code=401, detail="Token revoked or not found")

    # Revoke old
    db_token.is_revoked = True

    # Issue new tokens
    token_data = {"sub": payload["sub"], "tenant_id": payload["tenant_id"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    new_db_token = RefreshToken(
        token=new_refresh,
        user_id=db_token.user_id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_db_token)

    _set_auth_cookies(response, new_access, new_refresh)
    return TokenResponse(message="Token refreshed")


@router.post("/logout", response_model=TokenResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    old_token = request.cookies.get("refresh_token")
    if old_token:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token == old_token)
        )
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.is_revoked = True

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
    return TokenResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
