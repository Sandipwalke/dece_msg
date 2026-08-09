"""SRV record publishing for DeceMSG federation.

This module provides:
- DNS SRV record generation
- Automatic SRV record publishing
- Well-known endpoint for SRV discovery
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from decemsg.core.config import get_config


@dataclass
class SRVRecord:
    """A DNS SRV record for service discovery."""
    service: str
    proto: str = "_tcp"
    name: str = ""
    priority: int = 10
    weight: int = 1
    port: int = 443
    target: str = ""
    
    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "proto": self.proto,
            "name": self.name,
            "priority": self.priority,
            "weight": self.weight,
            "port": self.port,
            "target": self.target
        }


class SRVRecordPublisher:
    """Generates and manages SRV records for the server."""
    
    SERVICE_MESSAGING = "_decemsg._tcp"
    SERVICE_ACTIVITYPUB = "_activitypub._tcp"
    SERVICE_WEBSOCKET = "_decemsg-ws._tcp"
    
    def __init__(self, storage_path: str = "./data/srv_records.json"):
        self._storage_path = storage_path
        self._config: Dict = {}
        self._load()
    
    def _load(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, 'r') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading SRV config: {e}")
    
    def _save(self):
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        with open(self._storage_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def generate_records(self) -> Dict:
        """Generate all SRV records for this server."""
        config = get_config()
        domain = config.server.domain
        base_url = f"https://{domain}"
        
        srv_records = []
        
        for service in ["_decemsg", "_activitypub", "_decemsg-ws"]:
            srv = SRVRecord(
                service=service,
                proto="_tcp",
                name=domain,
                port=443,
                target=domain
            )
            srv_records.append(srv.to_dict())
        
        return {
            "srv_records": srv_records,
            "well_known": {
                "host-meta": f"{base_url}/federation/.well-known/host-meta",
                "webfinger": f"{base_url}/federation/.well-known/webfinger",
                "nodeinfo": f"{base_url}/federation/.well-known/nodeinfo",
                "actor": f"{base_url}/federation/actor",
                "inbox": f"{base_url}/federation/inbox",
                "outbox": f"{base_url}/federation/outbox"
            }
        }
    
    def generate_zone_file(self) -> str:
        """Generate zone file snippet."""
        config = get_config()
        domain = config.server.domain
        
        return f"""
; DeceMSG SRV Records for {domain}
_decemsg._tcp.{domain}. IN SRV 10 1 443 {domain}.
_activitypub._tcp.{domain}. IN SRV 10 1 443 {domain}.
_decemsg-ws._tcp.{domain}. IN SRV 10 1 443 {domain}.
"""
    
    def get_discovery_document(self) -> Dict:
        """Generate discovery document."""
        config = get_config()
        domain = config.server.domain
        base_url = f"https://{domain}"
        
        return {
            "name": "DeceMSG",
            "domain": domain,
            "urls": {
                "api": base_url,
                "nodeinfo": f"{base_url}/federation/.well-known/nodeinfo",
                "actor": f"{base_url}/federation/actor",
                "inbox": f"{base_url}/federation/inbox",
                "outbox": f"{base_url}/federation/outbox",
                "peers": f"{base_url}/federation/peers"
            },
            "features": ["messaging", "group_chat", "activitypub"],
            "srv_records": self.generate_records()["srv_records"]
        }
    
    def save_config(self):
        self._config = {
            "domain": get_config().server.domain,
            "records": self.generate_records(),
            "generated_at": datetime.utcnow().isoformat()
        }
        self._save()


_srv_publisher: Optional[SRVRecordPublisher] = None

def get_srv_publisher() -> SRVRecordPublisher:
    global _srv_publisher
    if _srv_publisher is None:
        _srv_publisher = SRVRecordPublisher()
    return _srv_publisher
