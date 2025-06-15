"""
Pydantic schemas for evaluation results.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, HttpUrl
from uuid import UUID as PyUUID

# Shared properties
class ResultBase(BaseModel):
    input_text: str = Field(..., description="The input text that was evaluated")
    output_text: str = Field(..., description="The generated output text")
    expected_output: Optional[str] = Field(None, description="Expected output (if available)")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation metrics for this result"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the result"
    )

# Properties to receive on result creation
class ResultCreate(ResultBase):
    run_id: PyUUID = Field(..., description="ID of the run this result belongs to")

# Properties to receive on result update
class ResultUpdate(BaseModel):
    metrics: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

# Properties shared by models stored in DB
class ResultInDBBase(ResultBase):
    id: PyUUID
    run_id: PyUUID
    created_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            PyUUID: str
        }

# Properties to return to client
class Result(ResultInDBBase):
    pass

# Properties stored in DB
class ResultInDB(ResultInDBBase):
    pass

# Response models
class ResultListResponse(BaseModel):
    items: List[Result]
    total: int

class ResultCreateResponse(BaseModel):
    id: PyUUID
    message: str = "Result created successfully"

class ResultUpdateResponse(BaseModel):
    message: str = "Result updated successfully"

class ResultDeleteResponse(BaseModel):
    message: str = "Result deleted successfully"

class ResultMetricsResponse(BaseModel):
    run_id: PyUUID
    metrics: Dict[str, Any]
    result_count: int

class ResultComparisonItem(BaseModel):
    input_text: str
    output_text: str
    expected_output: Optional[str]
    metrics: Dict[str, Any]

class ResultComparisonResponse(BaseModel):
    run_id: PyUUID
    model_name: str
    dataset_name: str
    results: List[ResultComparisonItem]
    summary_metrics: Dict[str, Any]

class ResultExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"

class ResultExportResponse(BaseModel):
    run_id: PyUUID
    format: ResultExportFormat
    url: Optional[str] = None
    content: Optional[Union[Dict, str, bytes]] = None
    message: str = "Export completed successfully"
