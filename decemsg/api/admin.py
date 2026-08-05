"""DeceMSG admin API endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from decemsg.core.database import get_db
from decemsg.core.auth import get_current_admin_user
from decemsg.core.config import get_config, reset_config
from decemsg.models.user import User
from decemsg.models.chat import Chat
from decemsg.models.message import Message

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# Response Models
class ServerStats(BaseModel):
    """Server statistics response."""
    total_users: int
    active_users_24h: int
    active_users_7d: int
    active_users_30d: int
    total_chats: int
    total_messages: int
    storage_used_mb: float
    uptime_seconds: int


class ServerConfig(BaseModel):
    """Server configuration response."""
    domain: str
    title: str
    allow_public_registration: bool
    allow_user_group_creation: bool
    default_keep_history: bool
    max_file_size_mb: int
    allowed_file_types: List[str]
    federation_enabled: bool


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    title: Optional[str] = None
    allow_public_registration: Optional[bool] = None
    allow_user_group_creation: Optional[bool] = None
    default_keep_history: Optional[bool] = None
    max_file_size_mb: Optional[int] = None
    federation_enabled: Optional[bool] = None


# Store server start time
_server_start_time = datetime.utcnow()


@router.get("/stats", response_model=ServerStats)
async def get_server_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get server statistics."""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Total users
    total_users_result = await db.execute(select(func.count()).select_from(User).where(User.is_active == True))
    total_users = total_users_result.scalar()
    
    # Active users in timeframes
    active_24h_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.is_active == True,
            User.last_seen >= day_ago
        )
    )
    active_24h = active_24h_result.scalar()
    
    active_7d_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.is_active == True,
            User.last_seen >= week_ago
        )
    )
    active_7d = active_7d_result.scalar()
    
    active_30d_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.is_active == True,
            User.last_seen >= month_ago
        )
    )
    active_30d = active_30d_result.scalar()
    
    # Total chats
    total_chats_result = await db.execute(select(func.count()).select_from(Chat).where(Chat.is_active == True))
    total_chats = total_chats_result.scalar()
    
    # Total messages
    total_messages_result = await db.execute(select(func.count()).select_from(Message))
    total_messages = total_messages_result.scalar()
    
    # Storage used
    storage_path = "./data"
    storage_used_mb = 0.0
    if os.path.exists(storage_path):
        for dirpath, dirnames, filenames in os.walk(storage_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    storage_used_mb += os.path.getsize(filepath) / (1024 * 1024)
    
    # Uptime
    uptime_seconds = int((now - _server_start_time).total_seconds())
    
    return ServerStats(
        total_users=total_users,
        active_users_24h=active_24h,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        total_chats=total_chats,
        total_messages=total_messages,
        storage_used_mb=round(storage_used_mb, 2),
        uptime_seconds=uptime_seconds
    )


@router.get("/config", response_model=ServerConfig)
async def get_server_config(
    current_user: User = Depends(get_current_admin_user)
):
    """Get server configuration."""
    config = get_config()
    
    return ServerConfig(
        domain=config.server.domain,
        title=config.server.title,
        allow_public_registration=config.auth.allow_public_registration,
        allow_user_group_creation=config.auth.allow_user_group_creation,
        default_keep_history=config.messaging.default_keep_history,
        max_file_size_mb=config.messaging.max_file_size_mb,
        allowed_file_types=config.messaging.allowed_file_types,
        federation_enabled=config.federation.enabled
    )


@router.put("/config")
async def update_server_config(
    config_update: ConfigUpdate,
    current_user: User = Depends(get_current_admin_user)
):
    """Update server configuration."""
    config = get_config()
    
    # Update values if provided
    if config_update.title is not None:
        config.server.title = config_update.title
    if config_update.allow_public_registration is not None:
        config.auth.allow_public_registration = config_update.allow_public_registration
    if config_update.allow_user_group_creation is not None:
        config.auth.allow_user_group_creation = config_update.allow_user_group_creation
    if config_update.default_keep_history is not None:
        config.messaging.default_keep_history = config_update.default_keep_history
    if config_update.max_file_size_mb is not None:
        config.messaging.max_file_size_mb = config_update.max_file_size_mb
    if config_update.federation_enabled is not None:
        config.federation.enabled = config_update.federation_enabled
    
    # Save configuration
    config.save_to_yaml()
    
    # Reset cached config
    reset_config()
    
    return {"message": "Configuration updated successfully"}


@router.post("/backup")
async def create_backup(
    current_user: User = Depends(get_current_admin_user)
):
    """Create a backup of the database."""
    config = get_config()
    db_path = config.database.path
    
    if not os.path.exists(db_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database file not found"
        )
    
    # Create backup filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = "./data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
    
    # Copy database file
    shutil.copy2(db_path, backup_path)
    
    return {
        "message": "Backup created successfully",
        "backup_path": backup_path
    }


@router.get("/logs")
async def get_server_logs(
    lines: int = Query(100, ge=10, le=500),
    current_user: User = Depends(get_current_admin_user)
):
    """Get recent server logs."""
    log_path = "./data/decemsg.log"
    
    if not os.path.exists(log_path):
        return {"logs": [], "message": "No log file found"}
    
    try:
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {"logs": recent_lines}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading logs: {str(e)}"
        )
