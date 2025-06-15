"""
API endpoints for managing projects.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page, paginate, add_pagination
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid

from ...db.session import get_db
from ...db.models import Project as DBProject
from .schemas.project import (
    Project, ProjectCreate, ProjectUpdate,
    ProjectListResponse, ProjectCreateResponse,
    ProjectUpdateResponse, ProjectDeleteResponse
)

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post(
    "/",
    response_model=ProjectCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project"
)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new project.
    
    - **name**: Name of the project (required)
    - **description**: Optional project description
    """
    # Check if project with this name already exists
    from sqlalchemy import select
    result = await db.execute(
        select(DBProject).where(DBProject.name == project_in.name)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A project with this name already exists"
        )
    
    # Create new project
    db_project = DBProject(
        name=project_in.name,
        description=project_in.description
    )
    
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    
    return ProjectCreateResponse(id=db_project.id)

@router.get(
    "/{project_id}",
    response_model=Project,
    summary="Get a project by ID"
)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a project by its ID.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(DBProject).where(DBProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

@router.get(
    "/",
    response_model=Page[Project],
    summary="List all projects"
)
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all projects with pagination.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(DBProject)
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()
    
    return paginate(projects)

@router.put(
    "/{project_id}",
    response_model=ProjectUpdateResponse,
    summary="Update a project"
)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a project.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(DBProject).where(DBProject.id == project_id)
    )
    db_project = result.scalar_one_or_none()
    
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update project fields
    if project_in.name is not None:
        db_project.name = project_in.name
    if project_in.description is not None:
        db_project.description = project_in.description
    
    db.add(db_project)
    await db.commit()
    
    return ProjectUpdateResponse()

@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
    summary="Delete a project"
)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a project.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(DBProject).where(DBProject.id == project_id)
    )
    db_project = result.scalar_one_or_none()
    
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    await db.delete(db_project)
    await db.commit()
    
    return ProjectDeleteResponse()
