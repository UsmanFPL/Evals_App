"""
Custom exceptions for the API.
"""
from fastapi import status
from fastapi.exceptions import HTTPException
from typing import Any, Dict, Optional, Union

class APIException(HTTPException):
    """Base exception for API errors."""
    
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Any = None,
        headers: Optional[Dict[str, str]] = None,
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail or "An error occurred"
        self.error_code = error_code or f"HTTP_{status_code}"
        self.extra = extra or {}
        
        super().__init__(
            status_code=status_code,
            detail=self.detail,
            headers=headers
        )

class BadRequestException(APIException):
    """400 Bad Request."""
    def __init__(
        self,
        detail: str = "Bad request",
        error_code: str = "BAD_REQUEST",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class UnauthorizedException(APIException):
    """401 Unauthorized."""
    def __init__(
        self,
        detail: str = "Not authenticated",
        error_code: str = "UNAUTHORIZED",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class ForbiddenException(APIException):
    """403 Forbidden."""
    def __init__(
        self,
        detail: str = "Forbidden",
        error_code: str = "FORBIDDEN",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class NotFoundException(APIException):
    """404 Not Found."""
    def __init__(
        self,
        detail: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class ConflictException(APIException):
    """409 Conflict."""
    def __init__(
        self,
        detail: str = "Resource already exists",
        error_code: str = "CONFLICT",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class ValidationException(APIException):
    """422 Unprocessable Entity."""
    def __init__(
        self,
        detail: Union[str, Dict[str, Any]] = "Validation error",
        error_code: str = "VALIDATION_ERROR",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class RateLimitException(APIException):
    """429 Too Many Requests."""
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
            
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code=error_code,
            headers=headers,
            **kwargs
        )

class InternalServerError(APIException):
    """500 Internal Server Error."""
    def __init__(
        self,
        detail: str = "Internal server error",
        error_code: str = "INTERNAL_SERVER_ERROR",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code=error_code,
            **kwargs
        )

class ServiceUnavailableError(APIException):
    """503 Service Unavailable."""
    def __init__(
        self,
        detail: str = "Service temporarily unavailable",
        error_code: str = "SERVICE_UNAVAILABLE",
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
            
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
            headers=headers,
            **kwargs
        )
