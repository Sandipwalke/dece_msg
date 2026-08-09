"""Disappearing messages sync for DeceMSG federation.

This module provides:
- Disappearing message timer sync
- Automatic message expiration across servers
- Timer settings per chat
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass
import json
import os

from decemsg.core.config import get_config


@dataclass
class DisappearingMessage:
    """A message with a disappearing timer."""
    message_id: str
    chat_id: str
    sender_id: str
    created_at: datetime
    expires_at: datetime
    duration_seconds: int
    is_expired: bool = False


class DisappearingMessageSync:
    """Manages disappearing messages and syncs timer settings across servers."""
    
    def __init__(self, storage_path: str = "./data/disappearing_messages.json"):
        self._storage_path = storage_path
        self._messages: Dict[str, DisappearingMessage] = {}
        self._chat_timers: Dict[str, int] = {}  # chat_id -> duration in seconds (0 = disabled)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._load()
    
    def _load(self):
        """Load data from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                
            for msg_data in data.get("messages", []):
                msg = DisappearingMessage(
                    message_id=msg_data["message_id"],
                    chat_id=msg_data["chat_id"],
                    sender_id=msg_data["sender_id"],
                    created_at=datetime.fromisoformat(msg_data["created_at"]),
                    expires_at=datetime.fromisoformat(msg_data["expires_at"]),
                    duration_seconds=msg_data["duration_seconds"],
                    is_expired=msg_data.get("is_expired", False)
                )
                self._messages[msg.message_id] = msg
            
            self._chat_timers = data.get("chat_timers", {})
            
        except Exception as e:
            print(f"Error loading disappearing messages: {e}")
    
    def _save(self):
        """Save data to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "messages": [
                {
                    "message_id": msg.message_id,
                    "chat_id": msg.chat_id,
                    "sender_id": msg.sender_id,
                    "created_at": msg.created_at.isoformat(),
                    "expires_at": msg.expires_at.isoformat(),
                    "duration_seconds": msg.duration_seconds,
                    "is_expired": msg.is_expired
                }
                for msg in self._messages.values()
            ],
            "chat_timers": self._chat_timers
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def set_chat_timer(self, chat_id: str, duration_seconds: int):
        """Set the disappearing timer for a chat.
        
        Args:
            chat_id: Chat ID
            duration_seconds: Timer duration (0 = disabled)
        """
        self._chat_timers[chat_id] = duration_seconds
        self._save()
    
    def get_chat_timer(self, chat_id: str) -> int:
        """Get the disappearing timer for a chat."""
        return self._chat_timers.get(chat_id, 0)
    
    def register_message(
        self,
        message_id: str,
        chat_id: str,
        sender_id: str,
        created_at: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Register a message with disappearing timer.
        
        Returns:
            Expiration datetime, or None if timer is disabled
        """
        duration = self.get_chat_timer(chat_id)
        if duration <= 0:
            return None
        
        if created_at is None:
            created_at = datetime.utcnow()
        
        expires_at = created_at + timedelta(seconds=duration)
        
        msg = DisappearingMessage(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            created_at=created_at,
            expires_at=expires_at,
            duration_seconds=duration
        )
        
        self._messages[message_id] = msg
        self._save()
        
        return expires_at
    
    def is_message_expired(self, message_id: str) -> bool:
        """Check if a message has expired."""
        if message_id not in self._messages:
            return False
        
        msg = self._messages[message_id]
        if msg.is_expired:
            return True
        
        if datetime.utcnow() >= msg.expires_at:
            msg.is_expired = True
            self._save()
            return True
        
        return False
    
    def mark_as_read(self, message_id: str, read_at: datetime) -> bool:
        """Mark a disappearing message as read, starting its timer.
        
        Returns:
            True if timer was started, False otherwise
        """
        if message_id not in self._messages:
            return False
        
        msg = self._messages[message_id]
        if msg.is_expired:
            return False
        
        # Recalculate expiration from read time
        msg.expires_at = read_at + timedelta(seconds=msg.duration_seconds)
        self._save()
        
        return True
    
    def get_pending_expirations(self) -> List[DisappearingMessage]:
        """Get all messages that should be expired."""
        now = datetime.utcnow()
        return [
            msg for msg in self._messages.values()
            if not msg.is_expired and now >= msg.expires_at
        ]
    
    def cleanup_expired(self) -> List[str]:
        """Remove expired messages from tracking.
        
        Returns:
            List of expired message IDs
        """
        expired_ids = []
        for msg in self._messages.values():
            if not msg.is_expired and datetime.utcnow() >= msg.expires_at:
                msg.is_expired = True
                expired_ids.append(msg.message_id)
        
        if expired_ids:
            self._save()
        
        return expired_ids
    
    async def start_cleanup_task(self, interval: int = 60):
        """Start background cleanup task.
        
        Args:
            interval: Seconds between cleanup runs
        """
        self._running = True
        while self._running:
            try:
                expired_ids = self.cleanup_expired()
                if expired_ids:
                    print(f"Expired {len(expired_ids)} disappearing messages")
            except Exception as e:
                print(f"Error in disappearing messages cleanup: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()


# Federation sync helpers
async def sync_disappearing_timer(
    chat_id: str,
    duration_seconds: int,
    members: List[str]
) -> dict:
    """Sync disappearing timer settings to federated servers.
    
    Args:
        chat_id: Chat ID
        duration_seconds: Timer duration
        members: List of member IDs (including federated)
    
    Returns:
        Dict with sync results
    """
    from decemsg.federation.federation_client import is_federated_user, parse_user_id
    from decemsg.federation.discovery import get_federation_client
    
    config = get_config()
    results = {"success": True, "synced": [], "failed": []}
    
    # Get unique domains from members
    domains = set()
    for member in members:
        if is_federated_user(member):
            _, domain = parse_user_id(member)
            if domain and domain != config.server.domain:
                domains.add(domain)
    
    for domain in domains:
        try:
            client = get_federation_client()
            server_info = await client.discover_server(domain)
            
            if server_info:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    response = await http_client.post(
                        f"{server_info.api_url}/federation/disappearing/sync",
                        json={
                            "chat_id": chat_id,
                            "duration_seconds": duration_seconds
                        }
                    )
                    
                    if response.status_code in (200, 201, 202):
                        results["synced"].append(domain)
                    else:
                        results["failed"].append(domain)
                        results["success"] = False
                        
        except Exception as e:
            print(f"Error syncing disappearing timer to {domain}: {e}")
            results["failed"].append(domain)
            results["success"] = False
    
    return results


# Global instance
_disappearing_manager: Optional[DisappearingMessageSync] = None


def get_disappearing_manager() -> DisappearingMessageSync:
    """Get the global disappearing messages manager."""
    global _disappearing_manager
    if _disappearing_manager is None:
        _disappearing_manager = DisappearingMessageSync()
    return _disappearing_manager
