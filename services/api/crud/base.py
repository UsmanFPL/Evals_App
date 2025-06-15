"""
Base CRUD operations for models.
"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize with the SQLAlchemy model class."""
        self.model = model
    
    async def get(self, db: AsyncSession, id: Union[UUID, str, int]) -> Optional[ModelType]:
        """Get a single record by ID."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore
        )
        return result.scalar_one_or_none()
    
    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: ModelType, 
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record."""
        obj_data = jsonable_encoder(db_obj)
        
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def remove(self, db: AsyncSession, *, id: Union[UUID, str, int]) -> Optional[ModelType]:
        """Delete a record by ID."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore
        )
        obj = result.scalar_one_or_none()
        
        if obj is None:
            return None
            
        await db.delete(obj)
        await db.commit()
        return obj
    
    async def get_by_field(
        self, 
        db: AsyncSession, 
        field: str, 
        value: Any,
        case_sensitive: bool = False
    ) -> Optional[ModelType]:
        """Get a record by a specific field."""
        from sqlalchemy import or_
        
        if not hasattr(self.model, field):
            return None
            
        if case_sensitive:
            condition = getattr(self.model, field) == value
        else:
            condition = getattr(self.model, field).ilike(f"%{value}%")
        
        result = await db.execute(
            select(self.model).where(condition)
        )
        return result.scalar_one_or_none()
    
    async def get_multi_by_field(
        self, 
        db: AsyncSession, 
        field: str, 
        value: Any,
        *, 
        skip: int = 0, 
        limit: int = 100,
        case_sensitive: bool = False
    ) -> List[ModelType]:
        """Get multiple records by a specific field."""
        if not hasattr(self.model, field):
            return []
            
        if case_sensitive:
            condition = getattr(self.model, field) == value
        else:
            condition = getattr(self.model, field).ilike(f"%{value}%")
        
        result = await db.execute(
            select(self.model)
            .where(condition)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def count(self, db: AsyncSession) -> int:
        """Count all records."""
        result = await db.execute(select(self.model))
        return len(result.scalars().all())
    
    async def exists(self, db: AsyncSession, id: Union[UUID, str, int]) -> bool:
        """Check if a record exists."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore
        )
        return result.scalar_one_or_none() is not None
