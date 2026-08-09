"""Push notification relay for DeceMSG federation.

This module provides:
- Push notification delivery to offline users via federated servers
- Notification subscription management
- Multi-server notification routing
"""
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

from decemsg.core.config import get_config


class NotificationType(Enum):
    """Types of push notifications."""
    MESSAGE = "message"
    MENTION = "mention"
    REACTION = "reaction"
    CALL = "call"
    SYSTEM = "system"


@dataclass
class PushSubscription:
    """A push notification subscription."""
    id: str
    user_id: str
    endpoint: str
    keys: Dict[str, str]  # p256dh and auth keys
    created_at: datetime
    expires_at: Optional[datetime]
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "keys": self.keys,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PushSubscription":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            endpoint=data["endpoint"],
            keys=data["keys"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )


@dataclass 
class NotificationPayload:
    """A push notification payload."""
    title: str
    body: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, str]]] = None


class PushNotificationRelay:
    """Manages push notifications and relay to federated servers."""
    
    def __init__(self, storage_path: str = "./data/push_subscriptions.json"):
        self._storage_path = storage_path
        self._subscriptions: Dict[str, PushSubscription] = {}
        self._load()
    
    def _load(self):
        """Load subscriptions from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for sub_data in data.get("subscriptions", []):
                    sub = PushSubscription.from_dict(sub_data)
                    self._subscriptions[sub.id] = sub
        except Exception as e:
            print(f"Error loading push subscriptions: {e}")
    
    def _save(self):
        """Save subscriptions to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "subscriptions": [sub.to_dict() for sub in self._subscriptions.values()]
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def subscribe(
        self,
        user_id: str,
        endpoint: str,
        keys: Dict[str, str]
    ) -> PushSubscription:
        """Subscribe a user to push notifications."""
        # Check for existing subscription with same endpoint
        for sub in self._subscriptions.values():
            if sub.endpoint == endpoint:
                sub.user_id = user_id
                sub.keys = keys
                self._save()
                return sub
        
        subscription = PushSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            endpoint=endpoint,
            keys=keys,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        self._subscriptions[subscription.id] = subscription
        self._save()
        
        return subscription
    
    def unsubscribe(self, endpoint: str) -> bool:
        """Unsubscribe from push notifications."""
        to_remove = None
        for sub in self._subscriptions.values():
            if sub.endpoint == endpoint:
                to_remove = sub.id
                break
        
        if to_remove:
            del self._subscriptions[to_remove]
            self._save()
            return True
        return False
    
    def get_user_subscriptions(self, user_id: str) -> List[PushSubscription]:
        """Get all subscriptions for a user."""
        return [
            sub for sub in self._subscriptions.values()
            if sub.user_id == user_id
            and (not sub.expires_at or sub.expires_at > datetime.utcnow())
        ]
    
    def cleanup_expired(self) -> int:
        """Remove expired subscriptions."""
        now = datetime.utcnow()
        expired = [
            sub_id for sub_id, sub in self._subscriptions.items()
            if sub.expires_at and sub.expires_at < now
        ]
        
        for sub_id in expired:
            del self._subscriptions[sub_id]
        
        if expired:
            self._save()
        
        return len(expired)


# Push notification sending
async def send_push_notification(
    user_id: str,
    notification: NotificationPayload,
    user_domain: Optional[str] = None
) -> bool:
    """Send a push notification to a user.
    
    Args:
        user_id: User ID
        notification: Notification payload
        user_domain: User's domain (for federated users)
    
    Returns:
        True if notification was sent successfully
    """
    from decemsg.api.websocket import manager
    
    config = get_config()
    
    # Check if user is online
    if manager.is_user_online(user_id):
        # Send via WebSocket instead
        ws_message = {
            "type": "push_notification",
            "title": notification.title,
            "body": notification.body,
            "icon": notification.icon,
            "tag": notification.tag,
            "data": notification.data
        }
        await manager.send_personal_message(ws_message, user_id)
        return True
    
    # Get push subscriptions for user
    push_relay = get_push_relay()
    subscriptions = push_relay.get_user_subscriptions(user_id)
    
    if not subscriptions and user_domain and user_domain != config.server.domain:
        # Relay to federated server
        return await relay_push_to_federated(
            user_id=user_id,
            user_domain=user_domain,
            notification=notification
        )
    
    # Send to local subscriptions
    sent_count = 0
    for sub in subscriptions:
        try:
            await _send_to_push_service(sub, notification)
            sent_count += 1
        except Exception as e:
            print(f"Error sending push to {sub.endpoint}: {e}")
    
    return sent_count > 0


async def _send_to_push_service(
    subscription: PushSubscription,
    notification: NotificationPayload
):
    """Send notification to a push service (VAPID)."""
    # In production, this would use pywebpush to send to the push service
    # For now, we just log the notification
    print(f"Push notification to {subscription.endpoint}:")
    print(f"  Title: {notification.title}")
    print(f"  Body: {notification.body}")
    
    # VAPID implementation would go here:
    # from pywebpush import webpush
    # webpush(
    #     subscription_info=subscription.to_vapid_format(),
    #     data=notification.to_json(),
    #     vapid_private_key=settings.VAPID_PRIVATE_KEY,
    #     vapid_claims={"sub": "mailto:admin@example.com"}
    # )


async def relay_push_to_federated(
    user_id: str,
    user_domain: str,
    notification: NotificationPayload
) -> bool:
    """Relay a push notification to a federated server.
    
    Returns:
        True if relay was successful
    """
    from decemsg.federation.discovery import get_federation_client
    
    config = get_config()
    
    if user_domain == config.server.domain:
        return False
    
    try:
        client = get_federation_client()
        server_info = await client.discover_server(user_domain)
        
        if not server_info:
            return False
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(
                f"{server_info.api_url}/federation/push/relay",
                json={
                    "user_id": user_id,
                    "notification": {
                        "title": notification.title,
                        "body": notification.body,
                        "icon": notification.icon,
                        "tag": notification.tag,
                        "data": notification.data
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return response.status_code in (200, 201, 202)
            
    except Exception as e:
        print(f"Error relaying push to {user_domain}: {e}")
        return False


# Global instance
_push_relay: Optional[PushNotificationRelay] = None


def get_push_relay() -> PushNotificationRelay:
    """Get the global push notification relay."""
    global _push_relay
    if _push_relay is None:
        _push_relay = PushNotificationRelay()
    return _push_relay
