"""DeceMSG users API endpoints."""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from decemsg.core.database import get_db
from decemsg.core.auth import get_current_user, get_current_admin_user
from decemsg.core.config import get_config
from decemsg.models.user import User
from decemsg.core.auth import get_password_hash

router = APIRouter(prefix="/api/users", tags=["Users"])


# Request/Response Models
class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)
    is_admin: bool = False


class UserUpdate(BaseModel):
    """User update request."""
    display_name: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: str | None = None
    password: str | None = Field(None, min_length=6)
    is_active: bool | None = None


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    display_name: str
    domain: str
    avatar_url: str | None
    created_at: str | None
    last_seen: str | None
    is_active: bool
    is_admin: bool


class UserListResponse(BaseModel):
    """User list response with pagination."""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all users (admin only)."""
    query = select(User)
    
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%")
            )
        )
    
    # Get total count
    count_query = select(User)
    if search:
        count_query = count_query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%")
            )
        )
    from sqlalchemy import func
    count_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
    total = count_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                domain=u.domain,
                avatar_url=u.avatar_url,
                created_at=u.created_at.isoformat() if u.created_at else None,
                last_seen=u.last_seen.isoformat() if u.last_seen else None,
                is_active=u.is_active,
                is_admin=u.is_admin,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new user (admin only)."""
    config = get_config()
    
    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    user = User(
        username=user_data.username,
        display_name=user_data.display_name,
        password_hash=get_password_hash(user_data.password),
        domain=config.server.domain,
        is_admin=user_data.is_admin if hasattr(user_data, 'is_admin') else False,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        domain=user.domain,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
        is_active=user.is_active,
        is_admin=user.is_admin,
    )


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search for users by username or display name."""
    result = await db.execute(
        select(User).where(
            User.is_active == True,
            or_(
                User.username.ilike(f"%{q}%"),
                User.display_name.ilike(f"%{q}%")
            )
        ).limit(20)
    )
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            domain=u.domain,
            avatar_url=u.avatar_url,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_seen=u.last_seen.isoformat() if u.last_seen else None,
            is_active=u.is_active,
            is_admin=u.is_admin,
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        domain=user.domain,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
        is_active=user.is_active,
        is_admin=user.is_admin,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile (self or admin)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permission: user can only update themselves unless admin
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )
    
    # Update fields
    if update_data.display_name is not None:
        user.display_name = update_data.display_name
    if update_data.avatar_url is not None:
        user.avatar_url = update_data.avatar_url
    if update_data.password is not None:
        user.password_hash = get_password_hash(update_data.password)
    if update_data.is_active is not None and current_user.is_admin:
        user.is_active = update_data.is_active
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        domain=user.domain,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
        is_active=user.is_active,
        is_admin=user.is_admin,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Deactivate user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting the last admin
    admin_count_result = await db.execute(
        select(User).where(User.is_admin == True, User.is_active == True)
    )
    admin_count = len(admin_count_result.scalars().all())
    
    if user.is_admin and admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last admin user"
        )
    
    user.is_active = False
    await db.commit()
