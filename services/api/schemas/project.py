"""
Pydantic schemas for projects.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from uuid import UUID as PyUUID

# Shared properties
class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the project")
    description: Optional[str] = Field(None, description="Project description")

# Properties to receive on project creation
class ProjectCreate(ProjectBase):
    pass

# Properties to receive on project update
class ProjectUpdate(ProjectBase):
    name: Optional[str] = Field(None, max_length=255, description="Name of the project")
    description: Optional[str] = Field(None, description="Project description")

# Properties shared by models stored in DB
class ProjectInDBBase(ProjectBase):
    id: PyUUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            PyUUID: str
        }

# Properties to return to client
class Project(ProjectInDBBase):
    pass

# Properties stored in DB
class ProjectInDB(ProjectInDBBase):
    pass

# Response models
class ProjectListResponse(BaseModel):
    items: List[Project]
    total: int

class ProjectCreateResponse(BaseModel):
    id: PyUUID
    message: str = "Project created successfully"

class ProjectUpdateResponse(BaseModel):
    message: str = "Project updated successfully"

class ProjectDeleteResponse(BaseModel):
    message: str = "Project deleted successfully"
