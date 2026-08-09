"""Offline message queue for DeceMSG federation.

This module provides:
- Queue for messages to offline users
- Automatic delivery when users come online
- Message persistence across server restarts
- Delivery tracking and status updates
"""
import json
import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

import asyncio

from decemsg.core.config import get_config


class MessageStatus(Enum):
    """Status of a queued message."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class QueuedOfflineMessage:
    """A message queued for an offline user."""
    id: str
    chat_id: str
    sender_id: str
    sender_domain: str
    recipient_id: str
    recipient_domain: str
    content: str
    message_type: str
    created_at: datetime
    expires_at: Optional[datetime]
    status: str
    delivery_attempts: int
    last_attempt: Optional[datetime]
    delivered_at: Optional[datetime]
    metadata: Dict[str, Any]
    
    def __init__(
        self,
        chat_id: str,
        sender_id: str,
        sender_domain: str,
        recipient_id: str,
        recipient_domain: str,
        content: str,
        message_type: str = "text",
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = str(uuid.uuid4())
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.sender_domain = sender_domain
        self.recipient_id = recipient_id
        self.recipient_domain = recipient_domain
        self.content = content
        self.message_type = message_type
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at
        self.status = MessageStatus.PENDING.value
        self.delivery_attempts = 0
        self.last_attempt = None
        self.delivered_at = None
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "sender_domain": self.sender_domain,
            "recipient_id": self.recipient_id,
            "recipient_domain": self.recipient_domain,
            "content": self.content,
            "message_type": self.message_type,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "delivery_attempts": self.delivery_attempts,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueuedOfflineMessage":
        """Load from dictionary."""
        msg = cls(
            chat_id=data["chat_id"],
            sender_id=data["sender_id"],
            sender_domain=data["sender_domain"],
            recipient_id=data["recipient_id"],
            recipient_domain=data["recipient_domain"],
            content=data["content"],
            message_type=data.get("message_type", "text"),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            metadata=data.get("metadata", {})
        )
        msg.id = data["id"]
        msg.created_at = datetime.fromisoformat(data["created_at"])
        msg.status = data.get("status", MessageStatus.PENDING.value)
        msg.delivery_attempts = data.get("delivery_attempts", 0)
        msg.last_attempt = datetime.fromisoformat(data["last_attempt"]) if data.get("last_attempt") else None
        msg.delivered_at = datetime.fromisoformat(data["delivered_at"]) if data.get("delivered_at") else None
        return msg
    
    def is_expired(self) -> bool:
        """Check if the message has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def should_retry(self) -> bool:
        """Check if delivery should be retried."""
        if self.status == MessageStatus.DELIVERED.value:
            return False
        if self.status == MessageStatus.EXPIRED.value:
            return False
        if self.is_expired():
            self.status = MessageStatus.EXPIRED.value
            return False
        if self.delivery_attempts >= 10:  # Max 10 attempts
            self.status = MessageStatus.FAILED.value
            return False
        return True


class OfflineMessageQueue:
    """Queue for messages to offline users."""
    
    def __init__(self, storage_path: str = "./data/offline_queue.json"):
        self._storage_path = storage_path
        self._queue: Dict[str, List[QueuedOfflineMessage]] = {}  # recipient_id -> messages
        self._all_messages: Dict[str, QueuedOfflineMessage] = {}  # message_id -> message
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        self._load()
    
    def _load(self):
        """Load queue from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                
            for msg_data in data:
                msg = QueuedOfflineMessage.from_dict(msg_data)
                self._all_messages[msg.id] = msg
                
                if msg.recipient_id not in self._queue:
                    self._queue[msg.recipient_id] = []
                self._queue[msg.recipient_id].append(msg)
                
        except Exception as e:
            print(f"Error loading offline queue: {e}")
    
    def _save(self):
        """Save queue to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        messages = [msg.to_dict() for msg in self._all_messages.values()]
        
        with open(self._storage_path, 'w') as f:
            json.dump(messages, f, indent=2)
    
    def queue_message(
        self,
        chat_id: str,
        sender_id: str,
        sender_domain: str,
        recipient_id: str,
        recipient_domain: str,
        content: str,
        message_type: str = "text",
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Queue a message for an offline user.
        
        Returns:
            The queued message ID
        """
        # Check if recipient is online - if so, don't queue
        from decemsg.api.websocket import manager
        if manager.is_user_online(recipient_id):
            return None  # User is online, no need to queue
        
        msg = QueuedOfflineMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            sender_domain=sender_domain,
            recipient_id=recipient_id,
            recipient_domain=recipient_domain,
            content=content,
            message_type=message_type,
            expires_at=expires_at,
            metadata=metadata
        )
        
        self._all_messages[msg.id] = msg
        
        if recipient_id not in self._queue:
            self._queue[recipient_id] = []
        self._queue[recipient_id].append(msg)
        
        self._save()
        return msg.id
    
    def get_messages_for_user(self, recipient_id: str) -> List[QueuedOfflineMessage]:
        """Get all pending messages for a user."""
        return [
            msg for msg in self._queue.get(recipient_id, [])
            if msg.status == MessageStatus.PENDING.value and msg.should_retry()
        ]
    
    def mark_delivered(self, message_id: str) -> bool:
        """Mark a message as delivered."""
        if message_id not in self._all_messages:
            return False
        
        msg = self._all_messages[message_id]
        msg.status = MessageStatus.DELIVERED.value
        msg.delivered_at = datetime.utcnow()
        
        # Remove from pending queue
        if msg.recipient_id in self._queue:
            self._queue[msg.recipient_id] = [
                m for m in self._queue[msg.recipient_id]
                if m.id != message_id
            ]
        
        self._save()
        return True
    
    def mark_failed(self, message_id: str, reason: str = None):
        """Mark a message as failed."""
        if message_id not in self._all_messages:
            return
        
        msg = self._all_messages[message_id]
        msg.status = MessageStatus.FAILED.value
        msg.metadata["failure_reason"] = reason
        
        self._save()
    
    async def deliver_pending_messages(self, recipient_id: str) -> int:
        """Attempt to deliver all pending messages to a user.
        
        Returns:
            Number of messages successfully delivered
        """
        from decemsg.federation.discovery import get_federation_client
        from decemsg.api.websocket import manager
        
        # Check if user is actually online now
        if not manager.is_user_online(recipient_id):
            return 0
        
        messages = self.get_messages_for_user(recipient_id)
        delivered_count = 0
        
        for msg in messages:
            msg.delivery_attempts += 1
            msg.last_attempt = datetime.utcnow()
            
            try:
                client = get_federation_client()
                
                # Send via federation
                success = await client.send_message(
                    from_user=msg.sender_id.split("#")[0] if "#" in msg.sender_id else msg.sender_id,
                    from_domain=msg.sender_domain,
                    to_user=msg.recipient_id.split("#")[0] if "#" in msg.recipient_id else msg.recipient_id,
                    to_domain=msg.recipient_domain,
                    content=msg.content,
                    message_type=msg.message_type
                )
                
                if success:
                    self.mark_delivered(msg.id)
                    delivered_count += 1
                    
                    # Notify via WebSocket
                    notification = {
                        "type": "offline_message_delivered",
                        "message_id": msg.id,
                        "chat_id": msg.chat_id,
                        "content": msg.content,
                        "sender_id": msg.sender_id
                    }
                    await manager.send_personal_message(notification, recipient_id)
                else:
                    self.mark_failed(msg.id, "Federation delivery failed")
                    
            except Exception as e:
                print(f"Error delivering offline message {msg.id}: {e}")
                self.mark_failed(msg.id, str(e))
        
        return delivered_count
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the offline queue."""
        pending = sum(
            1 for msg in self._all_messages.values()
            if msg.status == MessageStatus.PENDING.value
        )
        delivered = sum(
            1 for msg in self._all_messages.values()
            if msg.status == MessageStatus.DELIVERED.value
        )
        failed = sum(
            1 for msg in self._all_messages.values()
            if msg.status in [MessageStatus.FAILED.value, MessageStatus.EXPIRED.value]
        )
        
        return {
            "total_messages": len(self._all_messages),
            "pending": pending,
            "delivered": delivered,
            "failed_or_expired": failed,
            "unique_recipients": len(self._queue)
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired messages from the queue.
        
        Returns:
            Number of messages removed
        """
        expired_ids = [
            msg_id for msg_id, msg in self._all_messages.items()
            if msg.is_expired() and msg.status == MessageStatus.PENDING.value
        ]
        
        for msg_id in expired_ids:
            msg = self._all_messages[msg_id]
            msg.status = MessageStatus.EXPIRED.value
            
            if msg.recipient_id in self._queue:
                self._queue[msg.recipient_id] = [
                    m for m in self._queue[msg.recipient_id]
                    if m.id != msg_id
                ]
        
        if expired_ids:
            self._save()
        
        return len(expired_ids)


# Global offline queue instance
_offline_queue: Optional[OfflineMessageQueue] = None


def get_offline_queue() -> OfflineMessageQueue:
    """Get the global offline message queue instance."""
    global _offline_queue
    if _offline_queue is None:
        _offline_queue = OfflineMessageQueue()
    return _offline_queue


async def notify_user_online(user_id: str):
    """Called when a user comes online.
    
    Attempts to deliver any pending offline messages.
    """
    queue = get_offline_queue()
    count = await queue.deliver_pending_messages(user_id)
    if count > 0:
        print(f"Delivered {count} offline messages to {user_id}")


def queue_offline_message(
    chat_id: str,
    sender_id: str,
    sender_domain: str,
    recipient_id: str,
    recipient_domain: str,
    content: str,
    message_type: str = "text"
) -> Optional[str]:
    """Queue a message for an offline user.
    
    Call this when sending to a federated user who is offline.
    """
    queue = get_offline_queue()
    return queue.queue_message(
        chat_id=chat_id,
        sender_id=sender_id,
        sender_domain=sender_domain,
        recipient_id=recipient_id,
        recipient_domain=recipient_domain,
        content=content,
        message_type=message_type
    )
