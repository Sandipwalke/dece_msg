"""DeceMSG rate limiting module."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from decemsg.core.config import get_config


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on client IP or user."""
    # Check if user is authenticated
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Use token hash as key for authenticated users
        from decemsg.core.auth import decode_token
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    
    # Fall back to IP address
    return get_remote_address(request)


def create_limiter() -> Limiter:
    """Create rate limiter instance."""
    config = get_config()
    
    if not config.rate_limit.enabled:
        # Return a limiter that doesn't actually limit
        return Limiter(key_func=get_rate_limit_key, default_limits=[])
    
    return Limiter(
        key_func=get_rate_limit_key,
        default_limits=[config.rate_limit.api_rate],
        storage_uri="memory://"
    )


# Create global limiter instance
limiter = create_limiter()


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": getattr(exc, "detail", "Rate limit exceeded")
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(getattr(exc, "limit", "unknown")),
        }
    )


def get_login_rate_limit() -> str:
    """Get login rate limit from config."""
    config = get_config()
    return config.rate_limit.login_rate


def get_api_rate_limit() -> str:
    """Get API rate limit from config."""
    config = get_config()
    return config.rate_limit.api_rate
