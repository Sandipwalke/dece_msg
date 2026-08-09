"""Message retry queue for failed federated messages.

This module provides:
- Queue for failed messages pending retry
- Automatic retry with exponential backoff
- Persistence of queued messages
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from decemsg.core.config import get_config


class MessageType(Enum):
    """Types of messages that can be queued."""
    MESSAGE = "message"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_DELETE = "message_delete"
    TYPING = "typing"
    RECEIPT = "receipt"
    CHAT_SYNC = "chat_sync"
    GROUP_SYNC = "group_sync"
    PROFILE_UPDATE = "profile_update"


@dataclass
class QueuedMessage:
    """A message pending delivery to a federated server."""
    id: str
    message_type: str
    payload: dict
    target_domain: str
    created_at: datetime
    last_attempt: Optional[datetime]
    attempts: int
    max_attempts: int
    next_retry: Optional[datetime]
    
    def __init__(self, message_type: str, payload: dict, target_domain: str, max_attempts: int = 5):
        self.id = str(uuid.uuid4())
        self.message_type = message_type
        self.payload = payload
        self.target_domain = target_domain
        self.created_at = datetime.utcnow()
        self.last_attempt = None
        self.attempts = 0
        self.max_attempts = max_attempts
        self.next_retry = datetime.utcnow()  # Retry immediately
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "message_type": self.message_type,
            "payload": self.payload,
            "target_domain": self.target_domain,
            "created_at": self.created_at.isoformat(),
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "next_retry": self.next_retry.isoformat() if self.next_retry else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueuedMessage":
        """Load from dictionary."""
        msg = cls(
            message_type=data["message_type"],
            payload=data["payload"],
            target_domain=data["target_domain"],
            max_attempts=data.get("max_attempts", 5)
        )
        msg.id = data["id"]
        msg.created_at = datetime.fromisoformat(data["created_at"])
        msg.last_attempt = datetime.fromisoformat(data["last_attempt"]) if data.get("last_attempt") else None
        msg.attempts = data.get("attempts", 0)
        msg.next_retry = datetime.fromisoformat(data["next_retry"]) if data.get("next_retry") else None
        return msg
    
    def should_retry(self) -> bool:
        """Check if this message should be retried."""
        if self.attempts >= self.max_attempts:
            return False
        if self.next_retry and datetime.utcnow() < self.next_retry:
            return False
        return True
    
    def record_attempt(self, success: bool):
        """Record an attempt to send this message."""
        self.attempts += 1
        self.last_attempt = datetime.utcnow()
        
        if not success and self.attempts < self.max_attempts:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            delay = min(2 ** (self.attempts - 1), 60)  # Cap at 60 seconds
            self.next_retry = datetime.utcnow() + timedelta(seconds=delay)


class MessageRetryQueue:
    """Queue for messages that need to be retried."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self._queue: dict[str, QueuedMessage] = {}
        self._storage_path = storage_path
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None
        self._processing_lock = asyncio.Lock()
        
        # Load persisted queue if available
        if storage_path:
            self._load_queue()
    
    def add(self, message: QueuedMessage) -> str:
        """Add a message to the retry queue."""
        self._queue[message.id] = message
        self._save_queue()
        return message.id
    
    def remove(self, message_id: str) -> bool:
        """Remove a message from the queue."""
        if message_id in self._queue:
            del self._queue[message_id]
            self._save_queue()
            return True
        return False
    
    def get_pending(self) -> list[QueuedMessage]:
        """Get all messages that are ready to be retried."""
        return [msg for msg in self._queue.values() if msg.should_retry()]
    
    def get_all(self) -> list[QueuedMessage]:
        """Get all queued messages."""
        return list(self._queue.values())
    
    def count(self) -> int:
        """Get count of queued messages."""
        return len(self._queue)
    
    async def process_queue(self, sender: Callable[[QueuedMessage], bool]):
        """Process all pending messages in the queue.
        
        Args:
            sender: Async function that takes a QueuedMessage and returns True on success
        """
        async with self._processing_lock:
            pending = self.get_pending()
            
            for message in pending:
                try:
                    success = await sender(message)
                    message.record_attempt(success)
                    
                    if success or message.attempts >= message.max_attempts:
                        # Either delivered or exhausted retries
                        self.remove(message.id)
                except Exception as e:
                    print(f"Error processing queued message {message.id}: {e}")
                    message.record_attempt(False)
    
    async def start_processor(self, sender: Callable[[QueuedMessage], bool], interval: int = 5):
        """Start the background retry processor.
        
        Args:
            sender: Async function to send messages
            interval: Seconds between processing runs
        """
        self._running = True
        while self._running:
            try:
                await self.process_queue(sender)
            except Exception as e:
                print(f"Error in retry processor: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_processor(self):
        """Stop the background retry processor."""
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            self._retry_task = None
    
    def _save_queue(self):
        """Persist queue to disk."""
        if not self._storage_path:
            return
        
        try:
            with open(self._storage_path, 'w') as f:
                json.dump(
                    [msg.to_dict() for msg in self._queue.values()],
                    f,
                    indent=2
                )
        except Exception as e:
            print(f"Error saving retry queue: {e}")
    
    def _load_queue(self):
        """Load queue from disk."""
        if not self._storage_path:
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for msg_data in data:
                    msg = QueuedMessage.from_dict(msg_data)
                    self._queue[msg.id] = msg
        except FileNotFoundError:
            pass  # No persisted queue yet
        except Exception as e:
            print(f"Error loading retry queue: {e}")


# Global retry queue instance
_retry_queue: Optional[MessageRetryQueue] = None


def get_retry_queue() -> MessageRetryQueue:
    """Get the global retry queue instance."""
    global _retry_queue
    if _retry_queue is None:
        config = get_config()
        storage_path = None
        if hasattr(config, 'federation') and config.federation:
            # Could store in data directory
            storage_path = "./data/federation_retry_queue.json"
        
        _retry_queue = MessageRetryQueue(storage_path=storage_path)
    return _retry_queue


def queue_federated_message(
    message_type: str,
    payload: dict,
    target_domain: str
) -> str:
    """Queue a message for delivery to a federated server.
    
    Args:
        message_type: Type of message (from MessageType enum)
        payload: Message data to send
        target_domain: Domain of the target server
        
    Returns:
        Queue ID for the message
    """
    queue = get_retry_queue()
    message = QueuedMessage(
        message_type=message_type,
        payload=payload,
        target_domain=target_domain
    )
    return queue.add(message)


def cancel_queued_message(queue_id: str) -> bool:
    """Cancel a queued message.
    
    Args:
        queue_id: ID of the queued message
        
    Returns:
        True if message was found and removed
    """
    queue = get_retry_queue()
    return queue.remove(queue_id)
