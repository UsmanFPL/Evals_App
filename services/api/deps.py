"""
Dependency injection for FastAPI routes.
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import get_settings
from .core.security import verify_password
from .db.session import get_db, AsyncSessionLocal
from .models import User

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Get the current user from the JWT token."""
    from .core.exceptions import UnauthorizedException
    
    credentials_exception = UnauthorizedException(
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception
    
    # Get user from database
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user."""
    from .core.exceptions import ForbiddenException
    
    if not current_user.is_active:
        raise ForbiddenException(detail="Inactive user")
    return current_user

async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active superuser."""
    from .core.exceptions import ForbiddenException
    
    if not current_user.is_superuser:
        raise ForbiddenException(
            detail="The user doesn't have enough privileges"
        )
    return current_user

def get_db() -> Generator[AsyncSession, None, None]:
    """Get database session."""
    try:
        db = AsyncSessionLocal()
        yield db
    finally:
        await db.close()

# Dependencies for specific permissions or roles
class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            from .core.exceptions import ForbiddenException
            raise ForbiddenException(
                detail=f"Operation not permitted for role: {user.role}"
            )
        return user

# Common role checkers
is_admin = RoleChecker(["admin"])
is_editor = RoleChecker(["admin", "editor"])
is_user = RoleChecker(["admin", "editor", "user"])

# Dependency for API key authentication
async def get_api_key(api_key: str) -> str:
    """Validate API key."""
    from .core.exceptions import UnauthorizedException
    from .crud import user as user_crud
    
    db = AsyncSessionLocal()
    try:
        user = await user_crud.get_by_api_key(db, api_key=api_key)
        if not user:
            raise UnauthorizedException(detail="Invalid API key")
        return user
    finally:
        await db.close()
