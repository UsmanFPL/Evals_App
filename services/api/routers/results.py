"""
Result API endpoints.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import csv
import io

from ...core.security import get_current_active_user
from ...db.session import get_db
from ...schemas.result import (
    Result as ResultSchema,
    ResultCreate,
    ResultUpdate,
    ResultListResponse,
    ResultComparison,
    ResultExportFormat,
    ResultExportResponse
)
from ...schemas.user import User
from ...crud import result as crud_result
from ...crud import run as crud_run
from ...core.exceptions import NotFoundException, BadRequestException

router = APIRouter()

@router.post(
    "/", 
    response_model=List[ResultSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Create results",
    description="Create multiple results in a batch."
)
async def create_results(
    results: List[ResultCreate],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create multiple results in a batch."""
    if not results:
        raise BadRequestException(detail="No results provided")
    
    # Verify all runs exist and user has access
    run_ids = {str(r.run_id) for r in results}
    
    for run_id in run_ids:
        run = await crud_run.run.get(db, id=run_id)
        if not run:
            raise NotFoundException(detail=f"Run not found: {run_id}")
        
        # Check if user has access to the run's project
        if run.project_id:
            from ...crud import project as crud_project
            if not await crud_project.project.is_collaborator(
                db, project_id=run.project_id, user_id=current_user.id
            ) and run.created_by != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not enough permissions to add results to run: {run_id}"
                )
    
    # Create results
    created_results = await crud_result.result.create_batch(db, results=results)
    return created_results

@router.get(
    "/{result_id}", 
    response_model=ResultSchema,
    summary="Get result by ID",
    description="Retrieve a result by its ID."
)
async def get_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a result by ID."""
    result = await crud_result.result.get(db, id=result_id)
    if not result:
        raise NotFoundException(detail="Result not found")
    
    # Get the run to check permissions
    run = await crud_run.run.get(db, id=result.run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Check if user has access to the run's project
    if run.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run.project_id, user_id=current_user.id
        ) and run.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this result"
            )
    
    return result

@router.get(
    "/run/{run_id}", 
    response_model=ResultListResponse,
    summary="Get results by run ID",
    description="Retrieve all results for a specific run with pagination and filtering."
)
async def get_results_by_run(
    run_id: UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    filter_by: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all results for a specific run."""
    # First verify access to the run
    run = await crud_run.run.get(db, id=run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Check if user has access to the run's project
    if run.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run.project_id, user_id=current_user.id
        ) and run.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access these results"
            )
    
    # Parse filter_by if provided
    filter_dict = {}
    if filter_by:
        try:
            filter_dict = json.loads(filter_by)
            if not isinstance(filter_dict, dict):
                raise ValueError("filter_by must be a valid JSON object")
        except json.JSONDecodeError:
            raise BadRequestException(detail="Invalid filter_by format. Must be a valid JSON object.")
    
    # Get results
    results = await crud_result.result.get_run_results(
        db,
        run_id=run_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_by=filter_dict
    )
    
    # Get total count
    total = await crud_result.result.count_by_run(db, run_id=run_id)
    
    return {
        "items": results,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/run/{run_id}/metrics",
    summary="Get metrics for a run",
    description="Get aggregated metrics for all results in a run."
)
async def get_run_metrics(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated metrics for all results in a run."""
    # First verify access to the run
    run = await crud_run.run.get(db, id=run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Check if user has access to the run's project
    if run.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run.project_id, user_id=current_user.id
        ) and run.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access these metrics"
            )
    
    metrics = await crud_result.result.get_run_metrics_summary(db, run_id=run_id)
    return metrics

@router.get(
    "/compare/{run_id_1}/{run_id_2}",
    response_model=ResultComparison,
    summary="Compare two runs",
    description="Compare results between two runs."
)
async def compare_runs(
    run_id_1: UUID,
    run_id_2: UUID,
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Compare results between two runs."""
    # Verify access to both runs
    run1 = await crud_run.run.get(db, id=run_id_1)
    run2 = await crud_run.run.get(db, id=run_id_2)
    
    if not run1 or not run2:
        raise NotFoundException(detail="One or both runs not found")
    
    # Check if user has access to both runs
    if run1.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run1.project_id, user_id=current_user.id
        ) and run1.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access the first run"
            )
    
    if run2.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run2.project_id, user_id=current_user.id
        ) and run2.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access the second run"
            )
    
    # Compare the runs
    comparison = await crud_result.result.compare_runs(
        db, 
        run_id_1=run_id_1, 
        run_id_2=run_id_2,
        limit=limit
    )
    
    return comparison

@router.get(
    "/run/{run_id}/export",
    summary="Export results",
    description="Export results in various formats.",
    response_class=Response
)
async def export_results(
    run_id: UUID,
    format: ResultExportFormat = ResultExportFormat.JSON,
    include_columns: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Export results in the specified format."""
    # First verify access to the run
    run = await crud_run.run.get(db, id=run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Check if user has access to the run's project
    if run.project_id:
        from ...crud import project as crud_project
        if not await crud_project.project.is_collaborator(
            db, project_id=run.project_id, user_id=current_user.id
        ) and run.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to export these results"
            )
    
    # Export results
    export_data = await crud_result.result.export_results(
        db,
        run_id=run_id,
        export_format=format,
        include_columns=include_columns
    )
    
    # Return the appropriate response based on format
    if format == ResultExportFormat.JSON:
        return JSONResponse(
            content=export_data["content"],
            headers={"Content-Disposition": f"attachment; filename={export_data['filename']}"}
        )
    elif format == ResultExportFormat.CSV:
        return Response(
            content=export_data["content"],
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={export_data['filename']}"}
        )
    elif format == ResultExportFormat.EXCEL:
        return Response(
            content=export_data["content"],
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={export_data['filename']}"}
        )
    else:
        raise BadRequestException(detail=f"Unsupported export format: {format}")

@router.put(
    "/{result_id}",
    response_model=ResultSchema,
    summary="Update a result",
    description="Update a result's metadata or metrics."
)
async def update_result(
    result_id: UUID,
    result_in: ResultUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a result."""
    # First get the result
    result = await get_result(result_id, current_user, db)
    
    # Get the run to check permissions
    run = await crud_run.run.get(db, id=result.run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Only the run creator or an admin can update results
    if run.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this result"
        )
    
    # Update the result
    updated_result = await crud_result.result.update(
        db, db_obj=result, obj_in=result_in
    )
    
    return updated_result

@router.delete(
    "/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a result",
    description="Delete a result."
)
async def delete_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a result."""
    # First get the result
    result = await get_result(result_id, current_user, db)
    
    # Get the run to check permissions
    run = await crud_run.run.get(db, id=result.run_id)
    if not run:
        raise NotFoundException(detail="Run not found")
    
    # Only the run creator or an admin can delete results
    if run.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this result"
        )
    
    # Delete the result
    await crud_result.result.remove(db, id=result_id)
    
    return None
