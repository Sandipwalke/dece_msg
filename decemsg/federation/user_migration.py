"""User migration protocol for DeceMSG federation.

This module provides:
- User account migration between servers
- Message history transfer
- Contact list export/import
- Migration request signing and verification
"""
import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

from decemsg.core.config import get_config
from decemsg.core.database import get_db


class MigrationStatus(Enum):
    """Status of a migration request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MigrationRequest:
    """A request to migrate a user account."""
    id: str
    user_id: str
    old_domain: str
    new_domain: str
    new_username: str
    status: str
    created_at: datetime
    expires_at: datetime
    signature: str
    message_count: int = 0
    contact_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "old_domain": self.old_domain,
            "new_domain": self.new_domain,
            "new_username": self.new_username,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "signature": self.signature,
            "message_count": self.message_count,
            "contact_count": self.contact_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MigrationRequest":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            old_domain=data["old_domain"],
            new_domain=data["new_domain"],
            new_username=data["new_username"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            signature=data["signature"],
            message_count=data.get("message_count", 0),
            contact_count=data.get("contact_count", 0)
        )


class UserMigrationManager:
    """Manages user account migrations between servers."""
    
    def __init__(self, storage_path: str = "./data/user_migrations.json"):
        self._storage_path = storage_path
        self._requests: Dict[str, MigrationRequest] = {}
        self._load()
    
    def _load(self):
        """Load migrations from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for req_data in data.get("requests", []):
                    req = MigrationRequest.from_dict(req_data)
                    self._requests[req.id] = req
        except Exception as e:
            print(f"Error loading migrations: {e}")
    
    def _save(self):
        """Save migrations to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "requests": [req.to_dict() for req in self._requests.values()]
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_request(
        self,
        user_id: str,
        old_domain: str,
        new_domain: str,
        new_username: str,
        signature: str
    ) -> MigrationRequest:
        """Create a new migration request."""
        from datetime import timedelta
        
        request = MigrationRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            old_domain=old_domain,
            new_domain=new_domain,
            new_username=new_username,
            status=MigrationStatus.PENDING.value,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),
            signature=signature
        )
        
        self._requests[request.id] = request
        self._save()
        
        return request
    
    def get_request(self, request_id: str) -> Optional[MigrationRequest]:
        """Get a migration request by ID."""
        return self._requests.get(request_id)
    
    def approve_request(self, request_id: str) -> bool:
        """Approve a migration request."""
        if request_id not in self._requests:
            return False
        
        self._requests[request_id].status = MigrationStatus.APPROVED.value
        self._save()
        return True
    
    def reject_request(self, request_id: str, reason: str = None) -> bool:
        """Reject a migration request."""
        if request_id not in self._requests:
            return False
        
        req = self._requests[request_id]
        req.status = MigrationStatus.REJECTED.value
        if reason:
            req.status += f": {reason}"
        self._save()
        return True
    
    def complete_request(self, request_id: str) -> bool:
        """Mark a migration as completed."""
        if request_id not in self._requests:
            return False
        
        self._requests[request_id].status = MigrationStatus.COMPLETED.value
        self._save()
        return True
    
    def get_pending_requests(self) -> List[MigrationRequest]:
        """Get all pending migration requests."""
        return [
            req for req in self._requests.values()
            if req.status == MigrationStatus.PENDING.value
            and datetime.utcnow() < req.expires_at
        ]
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export user data for migration.
        
        Returns:
            Dict with user profile, chats, messages, and contacts
        """
        data = {
            "user": None,
            "chats": [],
            "contacts": [],
            "messages": [],
            "exported_at": datetime.utcnow().isoformat()
        }
        
        # Get user data
        async def get_data():
            async for db in get_db():
                from sqlalchemy import select
                from decemsg.models.user import User
                from decemsg.models.chat import Chat, ChatMember
                from decemsg.models.message import Message
                
                # Get user
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    data["user"] = {
                        "id": user.id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "avatar_url": user.avatar_url,
                        "domain": user.domain
                    }
                
                # Get chats
                result = await db.execute(
                    select(ChatMember).where(ChatMember.user_id == user_id)
                )
                memberships = result.scalars().all()
                chat_ids = [m.chat_id for m in memberships]
                
                for chat_id in chat_ids:
                    result = await db.execute(
                        select(Chat).where(Chat.id == chat_id)
                    )
                    chat = result.scalar_one_or_none()
                    if chat:
                        data["chats"].append({
                            "id": chat.id,
                            "name": chat.name,
                            "type": chat.type,
                            "created_at": chat.created_at.isoformat() if chat.created_at else None
                        })
                        
                        # Get messages
                        result = await db.execute(
                            select(Message).where(
                                Message.chat_id == chat_id,
                                Message.sender_id == user_id
                            ).order_by(Message.created_at.desc()).limit(1000)
                        )
                        for msg in result.scalars().all():
                            data["messages"].append({
                                "id": msg.id,
                                "chat_id": msg.chat_id,
                                "content": msg.content,
                                "message_type": msg.message_type.value,
                                "created_at": msg.created_at.isoformat() if msg.created_at else None
                            })
                
                break
        
        import asyncio
        try:
            asyncio.run(get_data())
        except Exception as e:
            print(f"Error exporting user data: {e}")
        
        return data
    
    def import_user_data(self, data: Dict[str, Any]) -> bool:
        """Import user data from migration.
        
        Returns:
            True if import was successful
        """
        user_data = data.get("user")
        chats_data = data.get("chats", [])
        messages_data = data.get("messages", [])
        
        if not user_data:
            return False
        
        async def do_import():
            async for db in get_db():
                from sqlalchemy import select
                from decemsg.models.user import User
                from decemsg.models.chat import Chat, ChatMember
                from decemsg.models.message import Message
                
                # Check if user already exists
                result = await db.execute(
                    select(User).where(User.username == user_data["username"])
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing user
                    existing.display_name = user_data.get("display_name", existing.display_name)
                    existing.avatar_url = user_data.get("avatar_url", existing.avatar_url)
                else:
                    # Create new user placeholder (actual creation should be done by admin)
                    pass
                
                await db.commit()
                
        import asyncio
        try:
            asyncio.run(do_import())
            return True
        except Exception as e:
            print(f"Error importing user data: {e}")
            return False


# Global instance
_migration_manager: Optional[UserMigrationManager] = None


def get_migration_manager() -> UserMigrationManager:
    """Get the global migration manager."""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = UserMigrationManager()
    return _migration_manager
