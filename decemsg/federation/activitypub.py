"""ActivityPub implementation for DeceMSG federation.

This module provides:
- ActivityStreams 2.0 objects
- AP inbox/outbox for activities
- Follow/Accept activity handling
- HTTP Signatures for AP
"""
import json
import hashlib
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio

from decemsg.core.config import get_config


class ActivityType(Enum):
    """ActivityPub activity types."""
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    FOLLOW = "Follow"
    ACCEPT = "Accept"
    REJECT = "Reject"
    UNDO = "Undo"
    LIKE = "Like"
    ANNOUNCE = "Announce"  # Boost/Share
    ADD = "Add"
    REMOVE = "Remove"


class ObjectType(Enum):
    """ActivityStreams object types."""
    NOTE = "Note"
    PERSON = "Person"
    CHAT_MESSAGE = "ChatMessage"
    CHAT = "Chat"
    GROUP = "Group"
    IMAGE = "Image"
    AUDIO = "Audio"
    VIDEO = "Video"
    DOCUMENT = "Document"
    LINK = "Link"
    MENTION = "Mention"


@dataclass
class APObject:
    """ActivityStreams 2.0 Object."""
    context: str = "https://www.w3.org/ns/activitystreams"
    type: str = "Object"
    id: str = ""
    
    def to_dict(self) -> dict:
        result = {
            "@context": self.context,
            "type": self.type,
            "id": self.id,
        }
        # Add any additional fields
        for key, value in self.__dict__.items():
            if key not in ['context', 'type', 'id'] and value is not None:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, APObject):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "APObject":
        """Create object from dict."""
        obj_type = data.get("type", "Object")
        obj = cls(type=obj_type, id=data.get("id", ""))
        
        for key, value in data.items():
            if key not in ["@context", "type", "id"]:
                setattr(obj, key, value)
        
        return obj


@dataclass
class APNote(APObject):
    """ActivityPub Note object (for messages)."""
    content: str = ""
    attributedTo: str = ""
    inReplyTo: Optional[str] = None
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    published: Optional[datetime] = None
    mediaType: str = "text/plain"
    url: Optional[str] = None
    
    def __post_init__(self):
        self.type = "Note"


@dataclass
class APPerson(APObject):
    """ActivityPub Person object."""
    preferredUsername: str = ""
    name: str = ""
    summary: str = ""
    inbox: str = ""
    outbox: str = ""
    followers: str = ""
    following: str = ""
    url: str = ""
    icon: Optional[Dict] = None
    publicKey: Optional[Dict] = None
    endpoints: Optional[Dict] = None
    
    def __post_init__(self):
        self.type = "Person"


@dataclass
class APActivity:
    """ActivityPub Activity."""
    context: str = "https://www.w3.org/ns/activitystreams"
    type: str = "Activity"
    id: str = ""
    actor: str = ""
    object: Optional[Dict] = None
    target: Optional[str] = None
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    published: Optional[datetime] = None
    result: Optional[Dict] = None
    
    def to_dict(self) -> dict:
        result = {
            "@context": self.context,
            "type": self.type,
            "id": self.id,
            "actor": self.actor,
        }
        
        if self.object:
            if isinstance(self.object, dict):
                result["object"] = self.object
            elif isinstance(self.object, APObject):
                result["object"] = self.object.to_dict()
            else:
                result["object"] = self.object
        
        if self.target:
            result["target"] = self.target
        if self.to:
            result["to"] = self.to
        if self.cc:
            result["cc"] = self.cc
        if self.published:
            result["published"] = self.published.isoformat()
        if self.result:
            result["result"] = self.result
            
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "APActivity":
        """Create activity from dict."""
        return cls(
            type=data.get("type", "Activity"),
            id=data.get("id", ""),
            actor=data.get("actor", ""),
            object=data.get("object"),
            target=data.get("target"),
            to=data.get("to", []),
            cc=data.get("cc", []),
            published=datetime.fromisoformat(data["published"]) if data.get("published") else None
        )


class InboxManager:
    """Manages the ActivityPub inbox."""
    
    def __init__(self, storage_path: str = "./data/ap_inbox.json"):
        self._storage_path = storage_path
        self._inbox: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load inbox from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                self._inbox = data.get("activities", [])
        except Exception as e:
            print(f"Error loading inbox: {e}")
    
    def _save(self):
        """Save inbox to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {"activities": self._inbox[-1000:]}  # Keep last 1000
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def receive(self, activity: Dict) -> bool:
        """Receive an activity into the inbox."""
        self._inbox.append({
            "activity": activity,
            "received_at": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4())
        })
        self._save()
        return True
    
    def get_inbox(self, recipient: str = None, limit: int = 100) -> List[Dict]:
        """Get inbox activities."""
        if recipient:
            return [
                item for item in self._inbox[-limit:]
                if recipient in item["activity"].get("to", []) or
                   recipient in item["activity"].get("cc", [])
            ]
        return self._inbox[-limit:]
    
    def mark_read(self, activity_id: str) -> bool:
        """Mark an activity as read."""
        for item in self._inbox:
            if item["id"] == activity_id:
                item["read"] = True
                self._save()
                return True
        return False


class OutboxManager:
    """Manages the ActivityPub outbox."""
    
    def __init__(self, storage_path: str = "./data/ap_outbox.json"):
        self._storage_path = storage_path
        self._outbox: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load outbox from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                self._outbox = data.get("activities", [])
        except Exception as e:
            print(f"Error loading outbox: {e}")
    
    def _save(self):
        """Save outbox to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {"activities": self._outbox[-1000:]}  # Keep last 1000
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def post(self, activity: Dict) -> str:
        """Post an activity to the outbox."""
        activity_id = str(uuid.uuid4())
        self._outbox.append({
            "activity": activity,
            "posted_at": datetime.utcnow().isoformat(),
            "id": activity_id,
            "status": "pending"
        })
        self._save()
        return activity_id
    
    def get_outbox(self, actor: str = None, limit: int = 100) -> List[Dict]:
        """Get outbox activities."""
        if actor:
            return [
                item for item in self._outbox[-limit:]
                if item["activity"].get("actor") == actor
            ]
        return self._outbox[-limit:]


class APProcessor:
    """Processes ActivityPub activities."""
    
    def __init__(self):
        self.inbox = InboxManager()
        self.outbox = OutboxManager()
    
    def create_note_activity(
        self,
        actor_id: str,
        content: str,
        recipients: List[str],
        in_reply_to: Optional[str] = None
    ) -> Dict:
        """Create a Note activity."""
        config = get_config()
        note_id = f"https://{config.server.domain}/objects/{uuid.uuid4()}"
        
        note = APNote(
            id=note_id,
            content=content,
            attributedTo=actor_id,
            inReplyTo=in_reply_to,
            to=recipients,
            published=datetime.utcnow()
        )
        
        activity = APActivity(
            id=f"{note_id}/activity",
            type="Create",
            actor=actor_id,
            object=note.to_dict(),
            to=recipients,
            published=datetime.utcnow()
        )
        
        return activity.to_dict()
    
    def create_follow_activity(
        self,
        actor_id: str,
        target_id: str
    ) -> Dict:
        """Create a Follow activity."""
        activity = APActivity(
            id=f"{actor_id}/follows/{uuid.uuid4()}",
            type="Follow",
            actor=actor_id,
            object=target_id,
            published=datetime.utcnow()
        )
        
        return activity.to_dict()
    
    def create_accept_activity(
        self,
        actor_id: str,
        activity: Dict
    ) -> Dict:
        """Create an Accept activity for a Follow."""
        accept = APActivity(
            id=f"{actor_id}/accepts/{uuid.uuid4()}",
            type="Accept",
            actor=actor_id,
            object=activity,
            published=datetime.utcnow()
        )
        
        return accept.to_dict()
    
    def process_activity(self, activity: Dict) -> Dict:
        """Process an incoming activity."""
        activity_type = activity.get("type", "Activity")
        
        if activity_type == "Create":
            return self._process_create(activity)
        elif activity_type == "Follow":
            return self._process_follow(activity)
        elif activity_type == "Accept":
            return self._process_accept(activity)
        elif activity_type == "Delete":
            return self._process_delete(activity)
        elif activity_type == "Update":
            return self._process_update(activity)
        else:
            return {"status": "unknown_activity", "type": activity_type}
    
    def _process_create(self, activity: Dict) -> Dict:
        """Process a Create activity."""
        obj = activity.get("object", {})
        
        # Store in inbox
        self.inbox.receive(activity)
        
        return {
            "status": "processed",
            "type": "Create",
            "object_id": obj.get("id")
        }
    
    def _process_follow(self, activity: Dict) -> Dict:
        """Process a Follow activity."""
        actor = activity.get("actor")
        target = activity.get("object")
        
        # Auto-accept follows
        return {
            "status": "auto_accepted",
            "follower": actor,
            "target": target
        }
    
    def _process_accept(self, activity: Dict) -> Dict:
        """Process an Accept activity."""
        self.inbox.receive(activity)
        
        return {
            "status": "processed",
            "type": "Accept"
        }
    
    def _process_delete(self, activity: Dict) -> Dict:
        """Process a Delete activity."""
        obj = activity.get("object", {})
        
        return {
            "status": "processed",
            "type": "Delete",
            "object_id": obj.get("id") if isinstance(obj, dict) else obj
        }
    
    def _process_update(self, activity: Dict) -> Dict:
        """Process an Update activity."""
        obj = activity.get("object", {})
        
        return {
            "status": "processed",
            "type": "Update",
            "object_id": obj.get("id") if isinstance(obj, dict) else obj
        }


# HTTP Signatures for AP
def create_http_signature(
    method: str,
    path: str,
    host: str,
    private_key_pem: str,
    key_id: str
) -> str:
    """Create an HTTP Signature for AP requests.
    
    Per draft-cavage-http-signatures-12
    """
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec
    
    # Create the signing string
    date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    signing_string = (
        f"(request-target): {method.lower()} {path}\n"
        f"host: {host}\n"
        f"date: {date}"
    )
    
    # Sign with private key
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(),
        password=None,
        backend=default_backend()
    )
    
    signature = private_key.sign(
        signing_string.encode(),
        ec.ECDSA(hashes.SHA256())
    )
    
    # Create signature header
    sig_b64 = base64.b64encode(signature).decode()
    
    return f'keyId="{key_id}",algorithm="ecdsa-sha256",headers="(request-target) host date",signature="{sig_b64}"'


# Global instance
_ap_processor: Optional[APProcessor] = None


def get_ap_processor() -> APProcessor:
    """Get the global AP processor."""
    global _ap_processor
    if _ap_processor is None:
        _ap_processor = APProcessor()
    return _ap_processor
