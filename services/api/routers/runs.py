"""
Run API endpoints.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ...core.security import get_current_active_user
from ...db.session import get_db
from ...schemas.run import (
    RunCreate,
    RunUpdate,
    Run as RunSchema,
    RunStatus as RunStatusEnum,
    RunWithDetails,
    RunStatusResponse,
    RunMetrics,
    RunListResponse,
)
from ...schemas.user import User
from ...crud import run as crud_run
from ...crud import project as crud_project
from ...crud import dataset as crud_dataset
from ...core.exceptions import NotFoundException, BadRequestException
from ...worker.tasks import run_evaluation_task
from ...core.config import settings

router = APIRouter()

@router.post(
    "/", 
    response_model=RunSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new run",
    description="Create a new evaluation run."
)
async def create_run(
    background_tasks: BackgroundTasks,
    run_in: RunCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new evaluation run.
    
    This will start the evaluation process in the background.
    """
    # Check if project exists and user has access
    project = await crud_project.project.get(db, id=run_in.project_id)
    if not project:
        raise NotFoundException(detail="Project not found")
    
    if project.owner_id != current_user.id and not await crud_project.project.is_collaborator(
        db, project_id=run_in.project_id, user_id=current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create runs in this project"
        )
    
    # Check if dataset exists and user has access if provided
    if run_in.dataset_id:
        dataset = await crud_dataset.dataset.get(db, id=run_in.dataset_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")
        
        if dataset.project_id and not await crud_project.project.is_collaborator(
            db, project_id=dataset.project_id, user_id=current_user.id
        ) and dataset.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to use this dataset"
            )
    
    try:
        # Create the run
        run = await crud_run.run.create_with_owner(
            db, obj_in=run_in, owner_id=current_user.id
        )
        
        # Start the evaluation in the background
        background_tasks.add_task(
            run_evaluation_task,
            run_id=str(run.id),
            dataset_id=str(run.dataset_id) if run.dataset_id else None,
            parameters=run.parameters or {}
        )
        
        return run
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating run: {str(e)}"
        )

@router.get(
    "/{run_id}", 
    response_model=RunWithDetails,
    summary="Get run by ID",
    description="Retrieve a run by its ID with details."
)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a run by ID with details."""
    run = await crud_run.run.get_run_with_details(db, run_id=run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Check project access
    project_id = run.get("project_id")
    if project_id:
        if not await crud_project.project.is_collaborator(
            db, project_id=project_id, user_id=current_user.id
        ) and run.get("created_by") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this run"
            )
    
    return run

@router.get(
    "/{run_id}/status",
    response_model=RunStatusResponse,
    summary="Get run status",
    description="Get the status of a run with progress information."
)
async def get_run_status(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the status of a run with progress information."""
    # First verify access by getting the run
    run = await get_run(run_id, current_user, db)
    
    status_info = await crud_run.run.get_run_status(db, run_id=run_id)
    if not status_info:
        raise NotFoundException(detail="Run status not found")
    
    return status_info

@router.get(
    "/{run_id}/metrics",
    response_model=RunMetrics,
    summary="Get run metrics",
    description="Get aggregated metrics for a run."
)
async def get_run_metrics(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated metrics for a run."""
    # First verify access by getting the run
    await get_run(run_id, current_user, db)
    
    metrics = await crud_run.run.get_run_metrics(db, run_id=run_id)
    if not metrics:
        raise NotFoundException(detail="Run metrics not found")
    
    return metrics

@router.post(
    "/{run_id}/cancel",
    response_model=RunStatusResponse,
    summary="Cancel a run",
    description="Cancel a pending or running run."
)
async def cancel_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a pending or running run."""
    # First verify access by getting the run
    run = await get_run(run_id, current_user, db)
    
    # Check if user has permission to cancel
    if run.get("created_by") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to cancel this run"
        )
    
    cancelled_run = await crud_run.run.cancel_run(db, run_id=run_id)
    if not cancelled_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run could not be cancelled. It may have already completed or failed."
        )
    
    return await get_run_status(run_id, current_user, db)

@router.get(
    "/", 
    response_model=RunListResponse,
    summary="List runs",
    description="List all runs with optional filtering and pagination."
)
async def list_runs(
    project_id: Optional[UUID] = None,
    status: Optional[RunStatusEnum] = None,
    dataset_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all runs with optional filtering."""
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
                detail="Not enough permissions to view runs in this project"
            )
    
    # If dataset_id is provided, verify access to the dataset
    if dataset_id:
        dataset = await crud_dataset.dataset.get(db, id=dataset_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")
        
        if dataset.project_id and not await crud_project.project.is_collaborator(
            db, project_id=dataset.project_id, user_id=current_user.id
        ) and dataset.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view runs for this dataset"
            )
    
    # Get runs
    runs = await crud_run.run.get_project_runs(
        db,
        project_id=project_id,
        status=status,
        skip=skip,
        limit=limit
    )
    
    # Get total count for pagination
    total = await crud_run.run.count(db)
    
    return {
        "items": runs,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/{run_id}/compare/{other_run_id}",
    summary="Compare two runs",
    description="Compare results between two runs."
)
async def compare_runs(
    run_id: UUID,
    other_run_id: UUID,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Compare results between two runs."""
    # Verify access to both runs
    run1 = await get_run(run_id, current_user, db)
    run2 = await get_run(other_run_id, current_user, db)
    
    # Check if both runs are from the same project
    if run1.get("project_id") != run2.get("project_id"):
        raise BadRequestException(detail="Cannot compare runs from different projects")
    
    # Compare the runs
    comparison = await crud_run.run.compare_runs(
        db, 
        run_id_1=run_id, 
        run_id_2=other_run_id,
        limit=limit
    )
    
    return comparison

@router.put(
    "/{run_id}",
    response_model=RunSchema,
    summary="Update a run",
    description="Update run metadata."
)
async def update_run(
    run_id: UUID,
    run_in: RunUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a run's metadata."""
    # First verify access by getting the run
    run = await get_run(run_id, current_user, db)
    
    # Check if user has permission to update
    if run.get("created_by") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this run"
        )
    
    # Only allow updating certain fields
    update_data = run_in.dict(exclude_unset=True)
    allowed_fields = {"name", "description", "tags"}
    update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not update_data:
        raise BadRequestException(detail="No valid fields to update")
    
    # Update the run
    updated_run = await crud_run.run.update(
        db, db_obj=run, obj_in=update_data
    )
    
    return updated_run

@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a run",
    description="Delete a run and its associated results."
)
async def delete_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a run and its associated results."""
    # First verify access by getting the run
    run = await get_run(run_id, current_user, db)
    
    # Check if user has permission to delete
    if run.get("created_by") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this run"
        )
    
    # Check if run is in a terminal state
    if run.get("status") not in [
        RunStatusEnum.COMPLETED.value,
        RunStatusEnum.FAILED.value,
        RunStatusEnum.CANCELLED.value
    ]:
        raise BadRequestException(
            detail="Cannot delete a run that is not in a terminal state (completed/failed/cancelled)"
        )
    
    # Delete the run (cascades to results)
    await crud_run.run.remove(db, id=run_id)
    
    return None
