"""
Authentication module — JWT token creation, password hashing, user lookup.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt
from pydantic import BaseModel

from config.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str
    company_id: int
    company_name: str


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Decode JWT and return current user data. Raises 401 if invalid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        role: str = payload.get("role")
        company_id: int = payload.get("company_id")
        company_name: str = payload.get("company_name", "")
        if user_id is None or email is None:
            raise credentials_exception
        return TokenData(
            user_id=user_id,
            email=email,
            role=role,
            company_id=company_id,
            company_name=company_name,
        )
    except JWTError:
        raise credentials_exception


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Dependency that requires admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Look up user by email and verify password. Returns user dict or None."""
    from sqlalchemy import text

    from src.tools.sql_tools import get_db_engine

    engine = get_db_engine()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT u.id, u.email, u.password_hash, u.full_name, u.role,
                   u.company_id, c.name as company_name
            FROM users u
            JOIN companies c ON u.company_id = c.id
            WHERE u.email = :email AND u.is_active = 1
        """), {"email": email})
        row = result.fetchone()

    if row is None:
        return None

    user = dict(row._mapping)
    if not verify_password(password, user["password_hash"]):
        return None

    return user
