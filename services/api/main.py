from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info("Starting up...")
    
    # Initialize resources (database, etc.)
    # TODO: Initialize database connection pool
    
    yield  # App is running
    
    # Shutdown
    logger.info("Shutting down...")
    # TODO: Clean up resources

# Create FastAPI app
app = FastAPI(
    title="AI Evaluation Platform API",
    description="API for evaluating LLM outputs",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "AI Evaluation Platform API",
        "version": "0.1.0",
        "docs": "/docs"
    }

# Import and include routers
# from .routers import projects, datasets, runs, results

# Include API routers
# app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
# app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["datasets"])
# app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
# app.include_router(results.router, prefix="/api/v1/results", tags=["results"])
