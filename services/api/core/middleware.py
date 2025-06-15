"""
Custom middleware for the API.
"""
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from typing import Optional, Dict, Any, Callable, Awaitable

from .logging_config import request_id_filter

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add a unique request ID to each request."""
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Set request ID in the request state
        request.state.request_id = request_id
        
        # Set request ID in the filter for logging
        request_id_filter.request_id = request_id
        
        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Log request
        request_id = getattr(request.state, "request_id", "unknown")
        logger = request.app.state.logger
        
        # Skip logging for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client": {"host": request.client.host if request.client else None},
                "user_agent": request.headers.get("user-agent"),
            },
        )
        
        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.4f}s",
                },
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "process_time": f"{process_time:.4f}s",
                },
                exc_info=True,
            )
            raise

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle errors and format error responses."""
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
            
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            logger = request.app.state.logger
            
            logger.error(
                "Unhandled exception",
                extra={"request_id": request_id, "error": str(e)},
                exc_info=True,
            )
            
            # Import here to avoid circular imports
            from fastapi import status
            from fastapi.responses import JSONResponse
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
            )

def setup_middleware(app: ASGIApp) -> None:
    """Set up all middleware for the application."""
    # Add middleware in reverse order of execution
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
