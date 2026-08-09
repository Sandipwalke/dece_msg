"""Contact roster sync for DeceMSG federation.

This module provides:
- Contact list synchronization across servers
- Contact requests and accept/reject
- Block list management
- Online status sharing
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from decemsg.core.config import get_config
from decemsg.core.database import get_db


class ContactStatus(Enum):
    """Status of a contact."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


@dataclass
class Contact:
    """A contact entry."""
    id: str
    owner_id: str
    contact_id: str
    contact_username: str
    contact_domain: str
    contact_display_name: str
    status: str
    added_at: datetime
    last_interaction: Optional[datetime]
    is_federated: bool


class ContactSyncManager:
    """Manages contact synchronization across federated servers."""
    
    def __init__(self, storage_path: str = "./data/contacts_sync.json"):
        self._storage_path = storage_path
        self._contacts: Dict[str, Contact] = {}
        self._load()
    
    def _load(self):
        """Load contacts from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for contact_data in data.get("contacts", []):
                    contact = Contact(
                        id=contact_data["id"],
                        owner_id=contact_data["owner_id"],
                        contact_id=contact_data["contact_id"],
                        contact_username=contact_data["contact_username"],
                        contact_domain=contact_data["contact_domain"],
                        contact_display_name=contact_data["contact_display_name"],
                        status=contact_data["status"],
                        added_at=datetime.fromisoformat(contact_data["added_at"]),
                        last_interaction=datetime.fromisoformat(contact_data["last_interaction"]) if contact_data.get("last_interaction") else None,
                        is_federated=contact_data.get("is_federated", False)
                    )
                    self._contacts[contact.id] = contact
        except Exception as e:
            print(f"Error loading contacts: {e}")
    
    def _save(self):
        """Save contacts to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "contacts": [
                {
                    "id": c.id,
                    "owner_id": c.owner_id,
                    "contact_id": c.contact_id,
                    "contact_username": c.contact_username,
                    "contact_domain": c.contact_domain,
                    "contact_display_name": c.contact_display_name,
                    "status": c.status,
                    "added_at": c.added_at.isoformat(),
                    "last_interaction": c.last_interaction.isoformat() if c.last_interaction else None,
                    "is_federated": c.is_federated
                }
                for c in self._contacts.values()
            ]
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_contact(
        self,
        owner_id: str,
        contact_id: str,
        contact_username: str,
        contact_domain: str,
        contact_display_name: str,
        is_federated: bool = False,
        status: str = ContactStatus.ACCEPTED.value
    ) -> Contact:
        """Add a new contact."""
        # Check if contact already exists
        for contact in self._contacts.values():
            if contact.owner_id == owner_id and contact.contact_id == contact_id:
                return contact
        
        contact = Contact(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            contact_id=contact_id,
            contact_username=contact_username,
            contact_domain=contact_domain,
            contact_display_name=contact_display_name,
            status=status,
            added_at=datetime.utcnow(),
            last_interaction=None,
            is_federated=is_federated
        )
        
        self._contacts[contact.id] = contact
        self._save()
        
        return contact
    
    def get_contact(self, owner_id: str, contact_id: str) -> Optional[Contact]:
        """Get a specific contact."""
        for contact in self._contacts.values():
            if contact.owner_id == owner_id and contact.contact_id == contact_id:
                return contact
        return None
    
    def get_contacts(self, owner_id: str, status: Optional[str] = None) -> List[Contact]:
        """Get all contacts for a user."""
        contacts = [
            c for c in self._contacts.values()
            if c.owner_id == owner_id
        ]
        
        if status:
            contacts = [c for c in contacts if c.status == status]
        
        return sorted(contacts, key=lambda c: c.last_interaction or c.added_at, reverse=True)
    
    def update_status(self, owner_id: str, contact_id: str, status: str) -> bool:
        """Update contact status."""
        contact = self.get_contact(owner_id, contact_id)
        if contact:
            contact.status = status
            self._save()
            return True
        return False
    
    def remove_contact(self, owner_id: str, contact_id: str) -> bool:
        """Remove a contact."""
        to_remove = None
        for contact in self._contacts.values():
            if contact.owner_id == owner_id and contact.contact_id == contact_id:
                to_remove = contact.id
                break
        
        if to_remove:
            del self._contacts[to_remove]
            self._save()
            return True
        return False
    
    def record_interaction(self, owner_id: str, contact_id: str):
        """Record a interaction with a contact."""
        contact = self.get_contact(owner_id, contact_id)
        if contact:
            contact.last_interaction = datetime.utcnow()
            self._save()
    
    def is_blocked(self, owner_id: str, contact_id: str) -> bool:
        """Check if a contact is blocked."""
        contact = self.get_contact(owner_id, contact_id)
        return contact and contact.status == ContactStatus.BLOCKED.value


# Federation sync helpers
async def sync_contact_to_federated(
    owner_id: str,
    owner_username: str,
    owner_domain: str,
    contact_id: str,
    contact_username: str,
    contact_domain: str,
    action: str  # "add", "remove", "block", "unblock"
) -> bool:
    """Sync contact action to federated server.
    
    Returns:
        True if sync was successful
    """
    from decemsg.federation.discovery import get_federation_client
    
    config = get_config()
    
    # Don't sync to local domain
    if contact_domain == config.server.domain:
        return True
    
    try:
        client = get_federation_client()
        server_info = await client.discover_server(contact_domain)
        
        if not server_info:
            return False
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(
                f"{server_info.api_url}/federation/contacts/sync",
                json={
                    "action": action,
                    "owner_id": owner_id,
                    "owner_username": owner_username,
                    "owner_domain": owner_domain,
                    "contact_id": contact_id,
                    "contact_username": contact_username,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return response.status_code in (200, 201, 202)
            
    except Exception as e:
        print(f"Error syncing contact to {contact_domain}: {e}")
        return False


# Global instance
_contact_manager: Optional[ContactSyncManager] = None


def get_contact_manager() -> ContactSyncManager:
    """Get the global contact sync manager."""
    global _contact_manager
    if _contact_manager is None:
        _contact_manager = ContactSyncManager()
    return _contact_manager
