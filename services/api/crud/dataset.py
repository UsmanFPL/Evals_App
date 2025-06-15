"""
CRUD operations for datasets.
"""
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import pandas as pd
import json
import os

from ...db.models import Dataset as DatasetModel, Project, Run
from .base import CRUDBase
from ..schemas.dataset import DatasetCreate, DatasetUpdate, DatasetPreviewResponse
from ...core.config import get_settings

settings = get_settings()

class CRUDDataset(CRUDBase[DatasetModel, DatasetCreate, DatasetUpdate]):
    """CRUD operations for datasets."""
    
    async def get_by_name(
        self, db: AsyncSession, *, name: str, project_id: Optional[UUID] = None
    ) -> Optional[DatasetModel]:
        """Get a dataset by name and optionally by project."""
        query = select(DatasetModel).where(DatasetModel.name == name)
        if project_id:
            query = query.where(DatasetModel.project_id == project_id)
            
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multi_by_project(
        self, db: AsyncSession, *, project_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[DatasetModel]:
        """Get multiple datasets by project ID."""
        result = await db.execute(
            select(DatasetModel)
            .where(DatasetModel.project_id == project_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_with_owner(
        self, db: AsyncSession, *, obj_in: DatasetCreate, owner_id: UUID
    ) -> DatasetModel:
        """Create a new dataset with an owner."""
        # Check if project exists and user has access
        project = await db.get(Project, obj_in.project_id)
        if not project:
            from ...core.exceptions import NotFoundException
            raise NotFoundException(detail="Project not found")
        
        # Create uploads directory if it doesn't exist
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        
        # Generate a unique filename
        import uuid
        file_extension = os.path.splitext(obj_in.file.filename)[1]
        filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await obj_in.file.read()
            buffer.write(content)
        
        # Create dataset record
        db_obj = DatasetModel(
            name=obj_in.name,
            description=obj_in.description,
            file_path=file_path,
            file_name=obj_in.file.filename,
            file_size=os.path.getsize(file_path),
            file_type=file_extension.lstrip('.').lower(),
            project_id=obj_in.project_id,
            created_by=owner_id,
            metadata=obj_in.metadata or {}
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_preview(
        self, db: AsyncSession, *, dataset_id: UUID, limit: int = 10
    ) -> Optional[DatasetPreviewResponse]:
        """Get a preview of the dataset."""
        dataset = await self.get(db, id=dataset_id)
        if not dataset:
            return None
            
        # Read the file based on its type
        if dataset.file_type == 'csv':
            df = pd.read_csv(dataset.file_path, nrows=limit+1)
        elif dataset.file_type == 'json':
            df = pd.read_json(dataset.file_path, lines=True, nrows=limit+1)
        else:
            # For other file types, read as text
            with open(dataset.file_path, 'r') as f:
                lines = [line.strip() for i, line in enumerate(f) if i < limit]
            return DatasetPreviewResponse(
                id=dataset.id,
                name=dataset.name,
                columns=["content"],
                preview=[{"content": line} for line in lines],
                total_rows=len(lines)
            )
        
        # For tabular data
        preview = df.head(limit).to_dict(orient='records')
        return DatasetPreviewResponse(
            id=dataset.id,
            name=dataset.name,
            columns=df.columns.tolist(),
            preview=preview,
            total_rows=len(df)
        )
    
    async def validate_dataset(
        self, db: AsyncSession, *, dataset_id: UUID
    ) -> Dict[str, Any]:
        """Validate dataset structure and content."""
        dataset = await self.get(db, id=dataset_id)
        if not dataset:
            from ...core.exceptions import NotFoundException
            raise NotFoundException(detail="Dataset not found")
            
        # Check if file exists
        if not os.path.exists(dataset.file_path):
            return {
                "valid": False,
                "error": f"File not found at path: {dataset.file_path}"
            }
            
        # Try to read the file
        try:
            if dataset.file_type == 'csv':
                df = pd.read_csv(dataset.file_path)
            elif dataset.file_type == 'json':
                df = pd.read_json(dataset.file_path, lines=True)
            else:
                # For other file types, just check if it's readable
                with open(dataset.file_path, 'r') as f:
                    f.read(1024)  # Read first KB to check if file is readable
                return {
                    "valid": True,
                    "message": "File is readable",
                    "file_type": dataset.file_type,
                    "size_bytes": os.path.getsize(dataset.file_path)
                }
            
            # For tabular data, check for required columns
            required_columns = ["input", "expected_output"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    "valid": False,
                    "error": f"Missing required columns: {', '.join(missing_columns)}",
                    "found_columns": df.columns.tolist()
                }
                
            return {
                "valid": True,
                "message": "Dataset is valid",
                "row_count": len(df),
                "columns": df.columns.tolist(),
                "sample": df.head().to_dict(orient='records')
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error reading file: {str(e)}"
            }
    
    async def get_usage_stats(
        self, db: AsyncSession, *, dataset_id: UUID
    ) -> Dict[str, Any]:
        """Get usage statistics for a dataset."""
        # Count runs that use this dataset
        result = await db.execute(
            select(Run)
            .where(Run.dataset_id == dataset_id)
        )
        runs = result.scalars().all()
        
        return {
            "total_runs": len(runs),
            "last_run": max([run.created_at for run in runs], default=None),
            "run_statuses": {
                "completed": len([r for r in runs if r.status == "completed"]),
                "failed": len([r for r in runs if r.status == "failed"]),
                "running": len([r for r in runs if r.status == "running"]),
                "pending": len([r for r in runs if r.status == "pending"]),
            }
        }

dataset = CRUDDataset(DatasetModel)
