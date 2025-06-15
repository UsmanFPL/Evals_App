"""
CRUD operations for projects.
"""
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ...db.models import Project as ProjectModel
from .base import CRUDBase
from ..schemas.project import ProjectCreate, ProjectUpdate

class CRUDProject(CRUDBase[ProjectModel, ProjectCreate, ProjectUpdate]):
    """CRUD operations for projects."""
    
    async def get_by_name(
        self, db: AsyncSession, *, name: str, owner_id: Optional[UUID] = None
    ) -> Optional[ProjectModel]:
        """Get a project by name and optionally by owner."""
        query = select(ProjectModel).where(ProjectModel.name == name)
        if owner_id:
            query = query.where(ProjectModel.owner_id == owner_id)
            
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multi_by_owner(
        self, db: AsyncSession, *, owner_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProjectModel]:
        """Get multiple projects by owner ID."""
        result = await db.execute(
            select(ProjectModel)
            .where(ProjectModel.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_with_owner(
        self, db: AsyncSession, *, obj_in: ProjectCreate, owner_id: UUID
    ) -> ProjectModel:
        """Create a new project with an owner."""
        db_obj = ProjectModel(
            **obj_in.dict(),
            owner_id=owner_id,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_multi_by_collaborator(
        self, db: AsyncSession, *, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProjectModel]:
        """Get all projects where user is a collaborator."""
        from ...db.models import ProjectCollaborator
        
        result = await db.execute(
            select(ProjectModel)
            .join(ProjectCollaborator, ProjectModel.id == ProjectCollaborator.project_id)
            .where(ProjectCollaborator.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def is_collaborator(
        self, db: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> bool:
        """Check if a user is a collaborator on a project."""
        from ...db.models import ProjectCollaborator
        
        result = await db.execute(
            select(ProjectCollaborator)
            .where(
                and_(
                    ProjectCollaborator.project_id == project_id,
                    ProjectCollaborator.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def add_collaborator(
        self, db: AsyncSession, *, project_id: UUID, user_id: UUID, role: str = "viewer"
    ) -> bool:
        """Add a collaborator to a project."""
        from ...db.models import ProjectCollaborator
        
        # Check if user is already a collaborator
        if await self.is_collaborator(db, project_id=project_id, user_id=user_id):
            return False
            
        db_obj = ProjectCollaborator(
            project_id=project_id,
            user_id=user_id,
            role=role
        )
        db.add(db_obj)
        await db.commit()
        return True
    
    async def remove_collaborator(
        self, db: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> bool:
        """Remove a collaborator from a project."""
        from ...db.models import ProjectCollaborator
        from sqlalchemy import delete
        
        result = await db.execute(
            delete(ProjectCollaborator)
            .where(
                and_(
                    ProjectCollaborator.project_id == project_id,
                    ProjectCollaborator.user_id == user_id
                )
            )
            .returning(ProjectCollaborator)
        )
        await db.commit()
        return result.scalar_one_or_none() is not None

project = CRUDProject(ProjectModel)
