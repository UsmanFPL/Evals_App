"""
Pydantic schemas for datasets.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, HttpUrl
from uuid import UUID as PyUUID

# Shared properties
class DatasetBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the dataset")
    description: Optional[str] = Field(None, description="Dataset description")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for the dataset"
    )

# Properties to receive on dataset creation
class DatasetCreate(DatasetBase):
    project_id: PyUUID = Field(..., description="ID of the project this dataset belongs to")
    file_path: str = Field(..., description="Path to the dataset file")

# Properties to receive on dataset update
class DatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Name of the dataset")
    description: Optional[str] = Field(None, description="Dataset description")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for the dataset"
    )

# Properties shared by models stored in DB
class DatasetInDBBase(DatasetBase):
    id: PyUUID
    project_id: PyUUID
    file_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            PyUUID: str
        }

# Properties to return to client
class Dataset(DatasetInDBBase):
    pass

# Properties stored in DB
class DatasetInDB(DatasetInDBBase):
    pass

# Response models
class DatasetListResponse(BaseModel):
    items: List[Dataset]
    total: int

class DatasetCreateResponse(BaseModel):
    id: PyUUID
    message: str = "Dataset created successfully"

class DatasetUpdateResponse(BaseModel):
    message: str = "Dataset updated successfully"

class DatasetDeleteResponse(BaseModel):
    message: str = "Dataset deleted successfully"

class DatasetUploadResponse(BaseModel):
    id: PyUUID
    file_path: str
    message: str = "File uploaded successfully"

class DatasetPreviewResponse(BaseModel):
    id: PyUUID
    name: str
    columns: List[str]
    preview: List[Dict[str, Any]]
    total_rows: int
