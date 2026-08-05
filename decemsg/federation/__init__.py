"""Federation API endpoints for DeceMSG."""
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from decemsg.core.database import get_db
from decemsg.core.config import get_config
from decemsg.federation.discovery import get_federation_client, ServerInfo
from decemsg.models.user import User
from decemsg.models.message import Message
from decemsg.models.chat import Chat, ChatMember
from sqlalchemy import select

router = APIRouter(prefix="/federation", tags=["Federation"])


# Request/Response Models
class FederationUserLookup(BaseModel):
    """Response for user lookup."""
    username: str
    display_name: str
    domain: str
    avatar_url: Optional[str] = None


class IncomingMessage(BaseModel):
    """Incoming federated message."""
    from_user: str
    from_domain: str
    to_user: str
    content: str
    message_type: str = "text"


class OutgoingMessage(BaseModel):
    """Outgoing federated message."""
    id: str
    from_user: str
    from_domain: str
    to_user: str
    to_domain: str
    content: str
    message_type: str
    created_at: str


class PresenceUpdate(BaseModel):
    """Presence update from federated server."""
    user: str
    domain: str
    is_online: bool


# NodeInfo endpoint for server discovery
@router.get("/.well-known/nodeinfo")
async def get_nodeinfo():
    """Return NodeInfo for server discovery."""
    config = get_config()
    return {
        "name": config.server.title,
        "version": "0.1.0",
        "protocols": ["activitypub", "simple-federation"],
        "software": {
            "name": "decemsg",
            "version": "0.1.0"
        },
        "usage": {
            "users": {"total": 0, "activeMonth": 0, "activeWeek": 0}
        }
    }


@router.get("/.well-known/host-meta")
async def get_host_meta():
    """Return XRD/HostMeta for WebFinger discovery."""
    config = get_config()
    return {
        "Subject": config.server.domain,
        "Links": [
            {
                "rel": "lrdd",
                "type": "application/xrd+xml",
                "template": f"https://{config.server.domain}/.well-known/webfinger?resource={{uri}}"
            }
        ]
    }


@router.get("/.well-known/webfinger")
async def webfinger(
    resource: str,
    rel: str = "acct"
):
    """WebFinger endpoint for user discovery."""
    config = get_config()
    
    # Parse the resource (e.g., user@example.com)
    if not resource.startswith("acct:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource format"
        )
    
    account = resource[5:]  # Remove "acct:"
    parts = account.split("@")
    
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account format"
        )
    
    username, domain = parts
    
    # Only respond to requests for this domain
    if domain != config.server.domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found on this server"
        )
    
    # Look up user
    return {
        "subject": resource,
        "aliases": [
            f"https://{domain}/users/{username}",
            f"https://{domain}/@{username}"
        ],
        "links": [
            {
                "rel": "http://webfinger.net/rel/profile-page",
                "type": "text/html",
                "href": f"https://{domain}/users/{username}"
            },
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": f"https://{domain}/users/{username}"
            }
        ]
    }


@router.get("/users/{username}", response_model=FederationUserLookup)
async def get_federated_user(
    username: str,
    db: AsyncSession = Depends(get_db)
):
    """Get user information for federation."""
    config = get_config()
    
    # Look up user
    result = await db.execute(
        select(User).where(
            User.username == username,
            User.domain == config.server.domain,
            User.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return FederationUserLookup(
        username=user.username,
        display_name=user.display_name,
        domain=user.domain,
        avatar_url=user.avatar_url
    )


@router.post("/messages")
async def receive_message(
    message: IncomingMessage,
    db: AsyncSession = Depends(get_db)
):
    """Receive a message from a federated server."""
    config = get_config()
    
    # Find the recipient user
    result = await db.execute(
        select(User).where(
            User.username == message.to_user,
            User.domain == config.server.domain
        )
    )
    recipient = result.scalar_one_or_none()
    
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found"
        )
    
    # Find or create direct chat with federated user
    # For simplicity, we'll store the message and associate with a placeholder
    # In production, you'd create proper cross-server chats
    
    # Create a new message
    new_message = Message(
        chat_id="federated",  # Placeholder
        sender_id="system",
        content=f"[Federated from {message.from_user}@{message.from_domain}] {message.content}",
        message_type=message.message_type
    )
    db.add(new_message)
    await db.commit()
    
    return {"status": "received", "message_id": str(new_message.id)}


@router.post("/presence")
async def receive_presence(
    presence: PresenceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Receive presence update from federated server."""
    # In production, you'd update local presence cache
    # For now, just acknowledge
    return {"status": "ok"}


# Internal API for local federation
@router.get("/servers")
async def list_federated_servers():
    """List all known federated servers."""
    client = get_federation_client()
    servers = await client.discover_all_known_servers()
    return {"servers": [s.dict() for s in servers]}


@router.post("/servers/discover")
async def discover_server(
    domain: str,
):
    """Discover a new federated server."""
    client = get_federation_client()
    server_info = await client.discover_server(domain)
    
    if server_info:
        return {"status": "discovered", "server": server_info.dict()}
    return {"status": "failed", "message": "Could not discover server"}


@router.get("/lookup/{username}@{domain}")
async def lookup_remote_user(
    username: str,
    domain: str,
):
    """Look up a user on a remote federated server."""
    client = get_federation_client()
    user_info = await client.lookup_user(username, domain)
    
    if user_info:
        return {"status": "found", "user": user_info}
    return {"status": "not_found", "message": "User not found on remote server"}


@router.post("/send")
async def send_federated_message(
    from_user: str,
    from_domain: str,
    to_user: str,
    to_domain: str,
    content: str,
    message_type: str = "text"
):
    """Send a message to a federated user."""
    client = get_federation_client()
    success = await client.send_message(
        from_user, from_domain,
        to_user, to_domain,
        content, message_type
    )
    
    if success:
        return {"status": "sent"}
    return {"status": "failed", "message": "Could not send message"}
