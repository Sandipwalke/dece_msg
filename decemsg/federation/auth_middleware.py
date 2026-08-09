"""Federation authentication middleware.

This module provides:
- Request signing verification for incoming federation requests
- Server-to-server authentication
- Configurable trust levels
"""
import time
import hashlib
from typing import Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, Header, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from decemsg.federation.server_auth import (
    verify_authenticated_request,
    get_server_registry,
    ServerIdentity,
    get_key_manager
)
from decemsg.core.config import get_config


@dataclass
class AuthResult:
    """Result of authentication check."""
    is_authenticated: bool
    server_domain: Optional[str] = None
    public_key: Optional[str] = None
    error: Optional[str] = None


class FederationAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to verify federation request authentication."""
    
    # Paths that require federation authentication
    PROTECTED_PATHS = [
        "/federation/messages",
        "/federation/chats",
        "/federation/receipts",
        "/federation/files",
        "/federation/typing",
        "/federation/blocks",
        "/federation/profile",
    ]
    
    # Paths that are public (discovery, info)
    PUBLIC_PATHS = [
        "/federation/.well-known",
        "/federation/users",
        "/federation/keys",
        "/federation/servers",
        "/federation/lookup",
        "/federation/send",
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process the request with authentication check."""
        path = request.url.path
        
        # Check if this is a federation path
        if not path.startswith("/federation/"):
            return await call_next(request)
        
        # Check if path is public
        for public_path in self.PUBLIC_PATHS:
            if path.startswith(public_path):
                return await call_next(request)
        
        # Check if path requires auth
        requires_auth = any(path.startswith(p) for p in self.PROTECTED_PATHS)
        
        if not requires_auth:
            return await call_next(request)
        
        # Get authentication headers
        signature = request.headers.get("X-Server-Signature")
        timestamp = request.headers.get("X-Server-Timestamp")
        public_key = request.headers.get("X-Server-Public-Key")
        server_domain = request.headers.get("X-Server-Domain")
        
        # Check for missing headers
        if not all([signature, timestamp, public_key, server_domain]):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing authentication headers"}
            )
        
        # Get request body
        body = await request.body()
        if not isinstance(body, str):
            body = body.decode('utf-8') if body else ""
        
        # Verify signature
        method = request.method
        path_only = request.url.path
        
        if not verify_authenticated_request(
            method=method,
            path=path_only,
            body=body,
            headers={
                "X-Server-Signature": signature,
                "X-Server-Timestamp": timestamp,
                "X-Server-Public-Key": public_key,
                "X-Server-Domain": server_domain
            }
        ):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid signature"}
            )
        
        # Mark server as verified
        registry = get_server_registry()
        identity = registry.get_server(server_domain)
        if identity:
            registry.mark_verified(server_domain)
        else:
            # Register new server
            registry.register_server(server_domain, public_key, signature)
            registry.mark_verified(server_domain)
        
        # Store auth info in request state
        request.state.federation_auth = AuthResult(
            is_authenticated=True,
            server_domain=server_domain,
            public_key=public_key
        )
        
        return await call_next(request)


async def require_federation_auth(
    request: Request
) -> AuthResult:
    """Dependency to require federation authentication.
    
    Use this for endpoints that need explicit auth verification.
    """
    # First check if middleware already verified
    if hasattr(request.state, "federation_auth"):
        auth = request.state.federation_auth
        if auth.is_authenticated:
            return auth
    
    # If not, check headers and verify
    signature = request.headers.get("X-Server-Signature")
    timestamp = request.headers.get("X-Server-Timestamp")
    public_key = request.headers.get("X-Server-Public-Key")
    server_domain = request.headers.get("X-Server-Domain")
    
    if not all([signature, timestamp, public_key, server_domain]):
        raise HTTPException(status_code=401, detail="Missing authentication headers")
    
    body = await request.body()
    if not isinstance(body, str):
        body = body.decode('utf-8') if body else ""
    
    if not verify_authenticated_request(
        method=request.method,
        path=request.url.path,
        body=body,
        headers={
            "X-Server-Signature": signature,
            "X-Server-Timestamp": timestamp,
            "X-Server-Public-Key": public_key,
            "X-Server-Domain": server_domain
        }
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return AuthResult(
        is_authenticated=True,
        server_domain=server_domain,
        public_key=public_key
    )


def get_authenticated_request_headers() -> dict:
    """Get headers for authenticating requests to other servers.
    
    Use this when making requests to federated servers.
    """
    from decemsg.federation.server_auth import create_authenticated_request, get_config
    import json
    
    config = get_config()
    
    # For outgoing requests, we create empty body signature
    # The actual body will be added by the client
    return create_authenticated_request(
        method="POST",
        path="/",
        body=""
    )
