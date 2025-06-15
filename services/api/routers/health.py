from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health", response_model=dict, status_code=200)
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
