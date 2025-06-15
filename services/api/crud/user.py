"""
CRUD operations for users.
"""
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from passlib.context import CryptContext

from ...db.models import User as UserModel, Project, ProjectCollaborator
from .base import CRUDBase
from ..schemas.user import UserCreate, UserUpdate, UserRole
from ...core.security import get_password_hash, verify_password
from ...core.exceptions import NotFoundException, BadRequestException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class CRUDUser(CRUDBase[UserModel, UserCreate, UserUpdate]):
    """CRUD operations for users."""
    
    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[UserModel]:
        """Get a user by email."""
        result = await db.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[UserModel]:
        """Get a user by username."""
        result = await db.execute(
            select(UserModel).where(UserModel.username == username)
        )
        return result.scalar_one_or_none()
    
    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> UserModel:
        """Create a new user with hashed password."""
        # Check if username or email already exists
        existing_user = await self.get_by_username(db, username=obj_in.username)
        if existing_user:
            raise BadRequestException(detail="Username already registered")
            
        existing_email = await self.get_by_email(db, email=obj_in.email)
        if existing_email:
            raise BadRequestException(detail="Email already registered")
        
        # Hash password
        hashed_password = get_password_hash(obj_in.password)
        
        # Create user
        db_obj = UserModel(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            is_active=obj_in.is_active,
            is_superuser=obj_in.is_superuser,
            role=obj_in.role or UserRole.USER.value
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: UserModel, 
        obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> UserModel:
        """Update a user."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
            
        # Handle password update
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
            del update_data["password"]
        
        # Check if username or email already exists
        if "username" in update_data and update_data["username"] != db_obj.username:
            existing_user = await self.get_by_username(db, username=update_data["username"])
            if existing_user:
                raise BadRequestException(detail="Username already registered")
                
        if "email" in update_data and update_data["email"] != db_obj.email:
            existing_email = await self.get_by_email(db, email=update_data["email"])
            if existing_email:
                raise BadRequestException(detail="Email already registered")
        
        return await super().update(db, db_obj=db_obj, obj_in=update_data)
    
    async def authenticate(
        self, db: AsyncSession, *, username: str, password: str
    ) -> Optional[UserModel]:
        """Authenticate a user."""
        user = await self.get_by_username(db, username=username)
        if not user:
            return None
            
        if not verify_password(password, user.hashed_password):
            return None
            
        return user
    
    async def is_active(self, user: UserModel) -> bool:
        """Check if user is active."""
        return user.is_active
    
    async def is_superuser(self, user: UserModel) -> bool:
        """Check if user is a superuser."""
        return user.is_superuser
    
    async def has_role(self, user: UserModel, role: str) -> bool:
        """Check if user has a specific role."""
        return user.role == role
    
    async def get_projects(
        self, 
        db: AsyncSession, 
        *, 
        user_id: UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Project]:
        """Get all projects for a user (owned and collaborated)."""
        # Get owned projects
        owned = await db.execute(
            select(Project)
            .where(Project.owner_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        owned_projects = owned.scalars().all()
        
        # Get collaborated projects
        collaborated = await db.execute(
            select(Project)
            .join(ProjectCollaborator, Project.id == ProjectCollaborator.project_id)
            .where(ProjectCollaborator.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        collaborated_projects = collaborated.scalars().all()
        
        # Combine and deduplicate
        project_ids = {p.id for p in owned_projects}
        all_projects = owned_projects + [
            p for p in collaborated_projects if p.id not in project_ids
        ]
        
        return all_projects
    
    async def get_api_keys(
        self, db: AsyncSession, *, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all API keys for a user."""
        from ...db.models import APIKey
        
        result = await db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
        )
        
        return [
            {
                "id": str(key.id),
                "name": key.name,
                "prefix": key.key_prefix,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at,
                "is_active": key.is_active
            }
            for key in result.scalars().all()
        ]
    
    async def create_api_key(
        self, 
        db: AsyncSession, 
        *, 
        user_id: UUID, 
        name: str, 
        expires_at: Optional[datetime] = None
    ) -> Dict[str, str]:
        """Create a new API key for a user."""
        from ...db.models import APIKey
        import secrets
        import string
        
        # Generate a random key
        alphabet = string.ascii_letters + string.digits
        key_value = ''.join(secrets.choice(alphabet) for _ in range(64))
        key_prefix = key_value[:8]
        
        # Hash the key for storage
        hashed_key = pwd_context.hash(key_value)
        
        # Store the key
        db_obj = APIKey(
            name=name,
            key_hash=hashed_key,
            key_prefix=key_prefix,
            user_id=user_id,
            expires_at=expires_at
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        # Return the full key (only shown once)
        return {
            "id": str(db_obj.id),
            "name": db_obj.name,
            "key": f"evk_{key_prefix}_{key_value}",
            "prefix": key_prefix,
            "created_at": db_obj.created_at,
            "expires_at": db_obj.expires_at.isoformat() if db_obj.expires_at else None
        }
    
    async def revoke_api_key(
        self, db: AsyncSession, *, key_id: UUID, user_id: UUID
    ) -> bool:
        """Revoke an API key."""
        from ...db.models import APIKey
        
        result = await db.execute(
            select(APIKey)
            .where(
                and_(
                    APIKey.id == key_id,
                    APIKey.user_id == user_id
                )
            )
        )
        
        key = result.scalar_one_or_none()
        if not key:
            return False
            
        await db.delete(key)
        await db.commit()
        return True

user = CRUDUser(UserModel)
