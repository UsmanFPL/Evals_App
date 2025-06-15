"""
Pydantic schemas for evaluation runs.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, HttpUrl
from uuid import UUID as PyUUID

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Shared properties
class RunBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the run")
    description: Optional[str] = Field(None, description="Run description")
    model_name: str = Field(..., description="Name of the model being evaluated")
    prompt: str = Field(..., description="Prompt template used for evaluation")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Model parameters used for generation"
    )

# Properties to receive on run creation
class RunCreate(RunBase):
    project_id: PyUUID = Field(..., description="ID of the project this run belongs to")
    dataset_id: Optional[PyUUID] = Field(None, description="ID of the dataset to evaluate against")

# Properties to receive on run update
class RunUpdate(BaseModel):
    status: Optional[RunStatus] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Properties shared by models stored in DB
class RunInDBBase(RunBase):
    id: PyUUID
    project_id: PyUUID
    dataset_id: Optional[PyUUID]
    status: RunStatus
    metrics: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        json_encoders = {
            PyUUID: str
        }
        use_enum_values = True

# Properties to return to client
class Run(RunInDBBase):
    pass

# Properties stored in DB
class RunInDB(RunInDBBase):
    pass

# Response models
class RunListResponse(BaseModel):
    items: List[Run]
    total: int

class RunCreateResponse(BaseModel):
    id: PyUUID
    message: str = "Run created successfully"

class RunUpdateResponse(BaseModel):
    message: str = "Run updated successfully"

class RunDeleteResponse(BaseModel):
    message: str = "Run deleted successfully"

class RunStatusResponse(BaseModel):
    run_id: PyUUID
    status: RunStatus
    progress: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class RunResultResponse(BaseModel):
    run_id: PyUUID
    status: RunStatus
    metrics: Dict[str, Any]
    results: List[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime] = None

class RunCancelResponse(BaseModel):
    run_id: PyUUID
    status: RunStatus
    message: str = "Run cancellation requested"

class RunLogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None

class RunLogsResponse(BaseModel):
    run_id: PyUUID
    logs: List[RunLogEntry]
