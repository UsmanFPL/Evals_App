"""
CRUD operations for evaluation results.
"""
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc
import pandas as pd
import json

from ...db.models import Result as ResultModel, Run
from .base import CRUDBase
from ..schemas.result import ResultCreate, ResultUpdate, ResultComparisonItem, ResultExportFormat
from ...core.exceptions import NotFoundException, BadRequestException

class CRUDResult(CRUDBase[ResultModel, ResultCreate, ResultUpdate]):
    """CRUD operations for evaluation results."""
    
    async def create_batch(
        self, db: AsyncSession, *, results: List[ResultCreate]
    ) -> List[ResultModel]:
        """Create multiple results in a batch."""
        if not results:
            return []
            
        # Check if all runs exist
        run_ids = {r.run_id for r in results}
        existing_runs = await db.execute(
            select(Run.id).where(Run.id.in_(run_ids))
        )
        existing_run_ids = {str(r[0]) for r in existing_runs.all()}
        
        missing_runs = run_ids - existing_run_ids
        if missing_runs:
            raise NotFoundException(
                detail=f"Runs not found: {', '.join(str(r) for r in missing_runs)}"
            )
        
        # Create result objects
        db_objs = [
            ResultModel(
                **result.dict(exclude={"metrics"}),
                metrics=json.dumps(result.metrics) if result.metrics else None
            )
            for result in results
        ]
        
        db.add_all(db_objs)
        await db.commit()
        
        # Refresh all objects
        for obj in db_objs:
            await db.refresh(obj)
            
        return db_objs
    
    async def get_run_results(
        self, 
        db: AsyncSession, 
        *, 
        run_id: UUID, 
        skip: int = 0, 
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        filter_by: Optional[Dict[str, Any]] = None
    ) -> List[ResultModel]:
        """Get results for a specific run with filtering and sorting."""
        # Check if run exists
        run = await db.get(Run, run_id)
        if not run:
            raise NotFoundException(detail="Run not found")
        
        # Build query
        query = select(ResultModel).where(ResultModel.run_id == run_id)
        
        # Apply filters
        if filter_by:
            for field, value in filter_by.items():
                if hasattr(ResultModel, field):
                    if isinstance(value, list):
                        query = query.where(getattr(ResultModel, field).in_(value))
                    else:
                        query = query.where(getattr(ResultModel, field) == value)
        
        # Apply sorting
        if sort_by and hasattr(ResultModel, sort_by):
            sort_field = getattr(ResultModel, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_field))
            else:
                query = query.order_by(asc(sort_field))
        else:
            # Default sorting by creation date
            query = query.order_by(ResultModel.created_at.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_run_metrics_summary(
        self, db: AsyncSession, *, run_id: UUID
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a run's results."""
        # Check if run exists
        run = await db.get(Run, run_id)
        if not run:
            raise NotFoundException(detail="Run not found")
        
        # Get all results with metrics
        results = await db.execute(
            select(ResultModel.metrics)
            .where(
                and_(
                    ResultModel.run_id == run_id,
                    ResultModel.metrics.isnot(None)
                )
            )
        )
        
        metrics_list = [r[0] for r in results.all() if r[0]]
        
        if not metrics_list:
            return {"count": 0, "metrics": {}}
        
        # Convert to DataFrame for easier aggregation
        df = pd.DataFrame(metrics_list)
        
        # Calculate summary statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        summary = {}
        
        for col in numeric_cols:
            summary[col] = {
                "mean": float(df[col].mean()),
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "std": float(df[col].std()),
                "count": int(df[col].count())
            }
        
        # Add count of results with/without metrics
        total_count = await self.count_by_run(db, run_id=run_id)
        
        return {
            "count": len(metrics_list),
            "total_count": total_count,
            "metrics": summary
        }
    
    async def compare_runs(
        self, 
        db: AsyncSession, 
        *, 
        run_id_1: UUID, 
        run_id_2: UUID,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Compare results between two runs."""
        # Check if runs exist
        run1 = await db.get(Run, run_id_1)
        run2 = await db.get(Run, run_id_2)
        
        if not run1 or not run2:
            raise NotFoundException(detail="One or both runs not found")
        
        # Get results for both runs
        results1 = await db.execute(
            select(ResultModel)
            .where(ResultModel.run_id == run_id_1)
            .limit(limit)
        )
        results1 = results1.scalars().all()
        
        results2 = await db.execute(
            select(ResultModel)
            .where(ResultModel.run_id == run_id_2)
            .limit(limit)
        )
        results2 = results2.scalars().all()
        
        # Create comparison items
        comparison_items = []
        for r1, r2 in zip(results1, results2):
            comparison_items.append(ResultComparisonItem(
                input_text=r1.input_text,
                output_1=r1.output_text,
                output_2=r2.output_text,
                metrics_1=r1.metrics or {},
                metrics_2=r2.metrics or {}
            ))
        
        # Get metrics summary for both runs
        metrics_1 = await self.get_run_metrics_summary(db, run_id=run_id_1)
        metrics_2 = await self.get_run_metrics_summary(db, run_id=run_id_2)
        
        return {
            "run_1": {
                "id": str(run_id_1),
                "name": run1.name or f"Run {run_id_1[:8]}",
                "metrics_summary": metrics_1
            },
            "run_2": {
                "id": str(run_id_2),
                "name": run2.name or f"Run {run_id_2[:8]}",
                "metrics_summary": metrics_2
            },
            "comparison": comparison_items
        }
    
    async def export_results(
        self, 
        db: AsyncSession, 
        *, 
        run_id: UUID,
        export_format: ResultExportFormat = ResultExportFormat.JSON,
        include_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Export results in the specified format."""
        # Check if run exists
        run = await db.get(Run, run_id)
        if not run:
            raise NotFoundException(detail="Run not found")
        
        # Get all results for the run
        results = await db.execute(
            select(ResultModel)
            .where(ResultModel.run_id == run_id)
        )
        results = results.scalars().all()
        
        if not results:
            raise NotFoundException(detail="No results found for this run")
        
        # Convert to list of dicts
        result_dicts = []
        for result in results:
            result_dict = {
                "id": str(result.id),
                "run_id": str(result.run_id),
                "input_text": result.input_text,
                "output_text": result.output_text,
                "expected_output": result.expected_output,
                "created_at": result.created_at.isoformat(),
                "metrics": result.metrics or {}
            }
            
            # Filter columns if specified
            if include_columns:
                result_dict = {
                    k: v for k, v in result_dict.items() 
                    if k in include_columns or k in ["id", "run_id"]
                }
                
            result_dicts.append(result_dict)
        
        # Export based on format
        if export_format == ResultExportFormat.JSON:
            return {
                "format": "json",
                "content": result_dicts,
                "filename": f"results_run_{run_id[:8]}.json"
            }
            
        elif export_format == ResultExportFormat.CSV:
            import io
            import csv
            
            # Convert to DataFrame for easier CSV export
            df = pd.DataFrame(result_dicts)
            
            # Flatten metrics if present
            if "metrics" in df.columns:
                metrics_df = pd.json_normalize(df["metrics"])
                if not metrics_df.empty:
                    metrics_df.columns = [f"metrics.{c}" for c in metrics_df.columns]
                    df = pd.concat([df.drop(["metrics"], axis=1), metrics_df], axis=1)
            
            # Export to CSV
            output = io.StringIO()
            df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
            
            return {
                "format": "csv",
                "content": output.getvalue(),
                "filename": f"results_run_{run_id[:8]}.csv"
            }
            
        elif export_format == ResultExportFormat.EXCEL:
            import io
            
            # Convert to DataFrame
            df = pd.DataFrame(result_dicts)
            
            # Flatten metrics if present
            if "metrics" in df.columns:
                metrics_df = pd.json_normalize(df["metrics"])
                if not metrics_df.empty:
                    metrics_df.columns = [f"metrics.{c}" for c in metrics_df.columns]
                    df = pd.concat([df.drop(["metrics"], axis=1), metrics_df], axis=1)
            
            # Export to Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
            
            return {
                "format": "excel",
                "content": output.getvalue(),
                "filename": f"results_run_{run_id[:8]}.xlsx"
            }
            
        else:
            raise BadRequestException(detail=f"Unsupported export format: {export_format}")
    
    async def count_by_run(
        self, db: AsyncSession, *, run_id: UUID
    ) -> int:
        """Count results for a specific run."""
        result = await db.execute(
            select(func.count(ResultModel.id))
            .where(ResultModel.run_id == run_id)
        )
        return result.scalar() or 0

result = CRUDResult(ResultModel)
