"""
Dataset API endpoints.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os

from ...core.security import get_current_active_user
from ...db.session import get_db
from ...schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    Dataset as DatasetSchema,
    DatasetPreviewResponse,
    DatasetUploadResponse,
    DatasetListResponse
)
from ...schemas.user import User
from ...crud import dataset as crud_dataset
from ...crud import project as crud_project
from ...core.exceptions import NotFoundException, BadRequestException
from ...core.config import settings

router = APIRouter()

@router.post(
    "/", 
    response_model=DatasetSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dataset",
    description="Upload and create a new dataset for a project."
)
async def create_dataset(
    file: UploadFile = File(...),
    name: str = None,
    description: str = None,
    project_id: UUID = None,
    metadata: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new dataset by uploading a file.
    
    Supported file formats: CSV, JSON, JSONL, TXT
    """
    # Validate file type
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in settings.ALLOWED_DATASET_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(settings.ALLOWED_DATASET_EXTENSIONS)}"
        )
    
    # Parse metadata if provided
    metadata_dict = {}
    if metadata:
        try:
            import json
            metadata_dict = json.loads(metadata)
            if not isinstance(metadata_dict, dict):
                raise ValueError("Metadata must be a valid JSON object")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid metadata format. Must be a valid JSON object."
            )
    
    # Use filename as name if not provided
    if not name:
        name = os.path.splitext(file.filename)[0]
    
    # Create dataset
    dataset_in = DatasetCreate(
        name=name,
        description=description,
        project_id=project_id,
        metadata=metadata_dict,
        file=file
    )
    
    # Check project access
    if project_id:
        project = await crud_project.project.get(db, id=project_id)
        if not project:
            raise NotFoundException(detail="Project not found")
        
        # Check if user has access to the project
        if project.owner_id != current_user.id and not await crud_project.project.is_collaborator(
            db, project_id=project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to add dataset to this project"
            )
    
    try:
        dataset = await crud_dataset.dataset.create_with_owner(
            db, obj_in=dataset_in, owner_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating dataset: {str(e)}"
        )
    
    return dataset

@router.get(
    "/{dataset_id}", 
    response_model=DatasetSchema,
    summary="Get dataset by ID",
    description="Retrieve a dataset by its ID."
)
async def get_dataset(
    dataset_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a dataset by ID."""
    dataset = await crud_dataset.dataset.get(db, id=dataset_id)
    if not dataset:
        raise NotFoundException(detail="Dataset not found")
    
    # Check project access if dataset is in a project
    if dataset.project_id:
        if not await crud_project.project.is_collaborator(
            db, project_id=dataset.project_id, user_id=current_user.id
        ) and dataset.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this dataset"
            )
    
    return dataset

@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreviewResponse,
    summary="Preview dataset",
    description="Preview the first few rows of a dataset."
)
async def preview_dataset(
    dataset_id: UUID,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Preview a dataset."""
    # First verify access
    await get_dataset(dataset_id, current_user, db)
    
    preview = await crud_dataset.dataset.get_preview(db, dataset_id=dataset_id, limit=limit)
    if not preview:
        raise NotFoundException(detail="Dataset preview not available")
    
    return preview

@router.get(
    "/{dataset_id}/download",
    response_class=FileResponse,
    summary="Download dataset",
    description="Download the dataset file."
)
async def download_dataset(
    dataset_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Download a dataset file."""
    dataset = await get_dataset(dataset_id, current_user, db)
    
    if not os.path.exists(dataset.file_path):
        raise NotFoundException(detail="Dataset file not found")
    
    return FileResponse(
        dataset.file_path,
        filename=dataset.file_name,
        media_type="application/octet-stream"
    )

@router.get(
    "/{dataset_id}/validate",
    summary="Validate dataset",
    description="Validate the structure and content of a dataset."
)
async def validate_dataset(
    dataset_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate a dataset."""
    # First verify access
    await get_dataset(dataset_id, current_user, db)
    
    validation = await crud_dataset.dataset.validate_dataset(db, dataset_id=dataset_id)
    return validation

@router.get(
    "/", 
    response_model=DatasetListResponse,
    summary="List datasets",
    description="List all datasets accessible to the current user with pagination."
)
async def list_datasets(
    project_id: Optional[UUID] = None,
    name: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all datasets with optional filtering."""
    # If project_id is provided, verify access to the project
    if project_id:
        project = await crud_project.project.get(db, id=project_id)
        if not project:
            raise NotFoundException(detail="Project not found")
            
        if project.owner_id != current_user.id and not await crud_project.project.is_collaborator(
            db, project_id=project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view datasets in this project"
            )
    
    # Build query
    query = select(crud_dataset.dataset.model)
    
    # Apply filters
    if project_id:
        query = query.where(crud_dataset.dataset.model.project_id == project_id)
    else:
        # If no project_id, only show datasets in projects the user has access to
        # or datasets not in any project that the user owns
        from sqlalchemy import or_
        
        # Get project IDs the user has access to
        projects = await crud_project.project.get_multi_by_owner(
            db, owner_id=current_user.id
        )
        project_ids = [p.id for p in projects]
        
        # Get collaborated projects
        collaborated = await crud_project.project.get_multi_by_collaborator(
            db, user_id=current_user.id
        )
        project_ids.extend([p.id for p in collaborated if p.id not in project_ids])
        
        if project_ids:
            query = query.where(
                or_(
                    crud_dataset.dataset.model.project_id.in_(project_ids),
                    and_(
                        crud_dataset.dataset.model.project_id.is_(None),
                        crud_dataset.dataset.model.created_by == current_user.id
                    )
                )
            )
        else:
            query = query.where(
                and_(
                    crud_dataset.dataset.model.project_id.is_(None),
                    crud_dataset.dataset.model.created_by == current_user.id
                )
            )
    
    if name:
        query = query.where(crud_dataset.dataset.model.name.ilike(f"%{name}%"))
    
    # Get total count
    total = await db.execute(select(func.count()).select_from(query.subquery()))
    total_count = total.scalar()
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    datasets = result.scalars().all()
    
    return {
        "items": datasets,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }

@router.put(
    "/{dataset_id}",
    response_model=DatasetSchema,
    summary="Update a dataset",
    description="Update dataset metadata."
)
async def update_dataset(
    dataset_id: UUID,
    dataset_in: DatasetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a dataset."""
    # First verify access
    dataset = await get_dataset(dataset_id, current_user, db)
    
    # Check if user is the owner
    if dataset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this dataset"
        )
    
    # Check if project is being changed and user has access to the new project
    if dataset_in.project_id and dataset_in.project_id != dataset.project_id:
        project = await crud_project.project.get(db, id=dataset_in.project_id)
        if not project:
            raise NotFoundException(detail="Project not found")
            
        if project.owner_id != current_user.id and not await crud_project.project.is_collaborator(
            db, project_id=dataset_in.project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to move dataset to this project"
            )
    
    # Update dataset
    updated_dataset = await crud_dataset.dataset.update(
        db, db_obj=dataset, obj_in=dataset_in
    )
    
    return updated_dataset

@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dataset",
    description="Delete a dataset and its associated file."
)
async def delete_dataset(
    dataset_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a dataset."""
    # First verify access
    dataset = await get_dataset(dataset_id, current_user, db)
    
    # Check if user is the owner
    if dataset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this dataset"
        )
    
    # Delete the file
    try:
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)
    except Exception as e:
        # Log the error but continue with DB deletion
        print(f"Error deleting dataset file: {str(e)}")
    
    # Delete the dataset record
    await crud_dataset.dataset.remove(db, id=dataset_id)
    
    return None
