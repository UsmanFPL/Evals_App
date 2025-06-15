"""
CRUD operations for evaluation runs.
"""
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
import json
import pandas as pd

from ...db.models import Run as RunModel, Project, Dataset, Result, RunStatus
from .base import CRUDBase
from ..schemas.run import RunCreate, RunUpdate, RunStatus as RunStatusEnum
from ...core.config import get_settings
from ...core.exceptions import NotFoundException, BadRequestException

settings = get_settings()

class CRUDRun(CRUDBase[RunModel, RunCreate, RunUpdate]):
    """CRUD operations for evaluation runs."""
    
    async def create_with_owner(
        self, db: AsyncSession, *, obj_in: RunCreate, owner_id: UUID
    ) -> RunModel:
        """Create a new run with an owner."""
        # Check if project exists and user has access
        project = await db.get(Project, obj_in.project_id)
        if not project:
            raise NotFoundException(detail="Project not found")
            
        # Check if dataset exists if provided
        if obj_in.dataset_id:
            dataset = await db.get(Dataset, obj_in.dataset_id)
            if not dataset:
                raise NotFoundException(detail="Dataset not found")
        
        # Create run
        db_obj = RunModel(
            **obj_in.dict(exclude={"parameters"}),
            parameters=json.dumps(obj_in.parameters) if obj_in.parameters else None,
            created_by=owner_id,
            status=RunStatus.PENDING.value
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def start_run(
        self, db: AsyncSession, *, run_id: UUID, worker_id: Optional[str] = None
    ) -> Optional[RunModel]:
        """Mark a run as started."""
        run = await self.get(db, id=run_id)
        if not run:
            return None
            
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        run.worker_id = worker_id
        
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run
    
    async def complete_run(
        self, 
        db: AsyncSession, 
        *, 
        run_id: UUID, 
        metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Optional[RunModel]:
        """Mark a run as completed or failed."""
        run = await self.get(db, id=run_id)
        if not run:
            return None
            
        run.completed_at = datetime.now(timezone.utc)
        
        if error:
            run.status = RunStatus.FAILED.value
            run.error = error
        else:
            run.status = RunStatus.COMPLETED.value
            run.metrics = metrics or {}
        
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run
    
    async def cancel_run(
        self, db: AsyncSession, *, run_id: UUID
    ) -> Optional[RunModel]:
        """Cancel a pending or running run."""
        run = await self.get(db, id=run_id)
        if not run:
            return None
            
        if run.status not in [RunStatus.PENDING.value, RunStatus.RUNNING.value]:
            raise BadRequestException(
                detail=f"Cannot cancel run with status: {run.status}"
            )
            
        run.status = RunStatus.CANCELLED.value
        run.completed_at = datetime.now(timezone.utc)
        
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run
    
    async def get_run_with_details(
        self, db: AsyncSession, *, run_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get a run with its details including project, dataset, and results."""
        result = await db.execute(
            select(
                RunModel,
                Project.name.label("project_name"),
                Dataset.name.label("dataset_name")
            )
            .outerjoin(Project, RunModel.project_id == Project.id)
            .outerjoin(Dataset, RunModel.dataset_id == Dataset.id)
            .where(RunModel.id == run_id)
        )
        
        row = result.first()
        if not row:
            return None
            
        run, project_name, dataset_name = row
        
        # Get results count
        result = await db.execute(
            select(func.count(Result.id))
            .where(Result.run_id == run_id)
        )
        result_count = result.scalar() or 0
        
        return {
            **run.__dict__,
            "project_name": project_name,
            "dataset_name": dataset_name,
            "result_count": result_count
        }
    
    async def get_run_status(
        self, db: AsyncSession, *, run_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get the status of a run with progress information."""
        # Get run with result count
        result = await db.execute(
            select(
                RunModel,
                func.count(Result.id).label("result_count")
            )
            .outerjoin(Result, RunModel.id == Result.run_id)
            .where(RunModel.id == run_id)
            .group_by(RunModel.id)
        )
        
        row = result.first()
        if not row:
            return None
            
        run, result_count = row
        
        # Calculate progress if total is known
        progress = None
        if run.dataset_id and hasattr(run, 'dataset') and run.dataset:
            # Get total items in dataset
            dataset = await db.get(Dataset, run.dataset_id)
            if dataset and hasattr(dataset, 'row_count') and dataset.row_count:
                progress = min(100, int((result_count / dataset.row_count) * 100))
        
        return {
            "run_id": str(run.id),
            "status": run.status,
            "progress": progress,
            "result_count": result_count,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error": run.error
        }
    
    async def get_run_metrics(
        self, db: AsyncSession, *, run_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get aggregated metrics for a run."""
        # Get run metrics
        run = await self.get(db, id=run_id)
        if not run:
            return None
            
        metrics = run.metrics or {}
        
        # Add result-level metrics if available
        result = await db.execute(
            select(Result.metrics)
            .where(Result.run_id == run_id)
            .limit(1000)  # Limit to avoid memory issues
        )
        
        result_metrics = result.scalars().all()
        if result_metrics:
            # Aggregate metrics across all results
            df = pd.DataFrame([m for m in result_metrics if m])
            if not df.empty:
                numeric_metrics = df.select_dtypes(include=['number'])
                if not numeric_metrics.empty:
                    metrics["result_metrics"] = {
                        "mean": numeric_metrics.mean().to_dict(),
                        "min": numeric_metrics.min().to_dict(),
                        "max": numeric_metrics.max().to_dict(),
                        "std": numeric_metrics.std().to_dict(),
                        "count": len(numeric_metrics)
                    }
        
        return metrics
    
    async def get_project_runs(
        self, 
        db: AsyncSession, 
        *, 
        project_id: UUID,
        status: Optional[RunStatusEnum] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all runs for a project with optional filtering."""
        query = (
            select(
                RunModel,
                Project.name.label("project_name"),
                Dataset.name.label("dataset_name"),
                func.count(Result.id).label("result_count")
            )
            .outerjoin(Project, RunModel.project_id == Project.id)
            .outerjoin(Dataset, RunModel.dataset_id == Dataset.id)
            .outerjoin(Result, RunModel.id == Result.run_id)
            .where(RunModel.project_id == project_id)
            .group_by(RunModel.id, Project.name, Dataset.name)
            .order_by(RunModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        if status:
            query = query.where(RunModel.status == status.value)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [{
            **run.__dict__,
            "project_name": project_name,
            "dataset_name": dataset_name,
            "result_count": result_count
        } for run, project_name, dataset_name, result_count in rows]

run = CRUDRun(RunModel)
