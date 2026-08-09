"""Server discovery bootstrap for DeceMSG federation.

This module provides:
- WebFinger protocol implementation
- Server directory/seed list
- Automatic server discovery
- Known servers caching
"""
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

import httpx

from decemsg.core.config import get_config
from decemsg.federation.discovery import get_federation_client, ServerInfo


@dataclass
class SeedServer:
    """A seed server for bootstrapping discovery."""
    domain: str
    api_url: str
    added_at: datetime
    last_checked: Optional[datetime] = None
    is_reachable: bool = False


class ServerDirectory:
    """Directory of known federated servers."""
    
    def __init__(self, storage_path: str = "./data/server_directory.json"):
        self._storage_path = storage_path
        self._servers: Dict[str, SeedServer] = {}
        self._load()
    
    def _load(self):
        """Load servers from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for domain, info in data.items():
                    self._servers[domain] = SeedServer(
                        domain=domain,
                        api_url=info["api_url"],
                        added_at=datetime.fromisoformat(info["added_at"]),
                        last_checked=datetime.fromisoformat(info["last_checked"]) if info.get("last_checked") else None,
                        is_reachable=info.get("is_reachable", False)
                    )
        except Exception as e:
            print(f"Error loading server directory: {e}")
    
    def _save(self):
        """Save servers to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            domain: {
                "api_url": server.api_url,
                "added_at": server.added_at.isoformat(),
                "last_checked": server.last_checked.isoformat() if server.last_checked else None,
                "is_reachable": server.is_reachable
            }
            for domain, server in self._servers.items()
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_server(self, domain: str, api_url: str) -> SeedServer:
        """Add a server to the directory."""
        server = SeedServer(
            domain=domain,
            api_url=api_url,
            added_at=datetime.utcnow()
        )
        self._servers[domain] = server
        self._save()
        return server
    
    def remove_server(self, domain: str) -> bool:
        """Remove a server from the directory."""
        if domain in self._servers:
            del self._servers[domain]
            self._save()
            return True
        return False
    
    def get_server(self, domain: str) -> Optional[SeedServer]:
        """Get a server from the directory."""
        return self._servers.get(domain)
    
    def get_all_servers(self) -> List[SeedServer]:
        """Get all servers in the directory."""
        return list(self._servers.values())
    
    def get_reachable_servers(self) -> List[SeedServer]:
        """Get all reachable servers."""
        return [s for s in self._servers.values() if s.is_reachable]
    
    async def check_server_health(self, domain: str) -> bool:
        """Check if a server is reachable."""
        server = self._servers.get(domain)
        if not server:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{server.api_url}/health")
                is_ok = response.status_code == 200
                
                server.last_checked = datetime.utcnow()
                server.is_reachable = is_ok
                self._save()
                
                return is_ok
        except Exception:
            server.last_checked = datetime.utcnow()
            server.is_reachable = False
            self._save()
            return False
    
    async def discover_servers_from_seed(self, seed_domain: str) -> List[str]:
        """Discover servers from a seed server.
        
        Queries the seed server for its list of known federated servers.
        """
        discovered = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Try to get server list from seed
                response = await client.get(
                    f"https://{seed_domain}/federation/servers",
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    servers = data.get("servers", [])
                    
                    for server_data in servers:
                        domain = server_data.get("domain")
                        api_url = server_data.get("api_url")
                        
                        if domain and api_url and domain not in self._servers:
                            self.add_server(domain, api_url)
                            discovered.append(domain)
        
        except Exception as e:
            print(f"Error discovering servers from {seed_domain}: {e}")
        
        return discovered


class WebFingerClient:
    """Client for WebFinger protocol (RFC 7033)."""
    
    @staticmethod
    async def finger(domain: str, resource: str) -> Optional[Dict[str, Any]]:
        """Perform a WebFinger lookup.
        
        Args:
            domain: The domain to query
            resource: The resource to look up (e.g., "user@example.com")
            
        Returns:
            WebFinger response data or None on failure
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://{domain}/.well-known/webfinger",
                    params={"resource": resource},
                    headers={"Accept": "application/jrd+json, application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"WebFinger lookup failed for {resource}: {e}")
        
        return None
    
    @staticmethod
    async def lookup_user(domain: str, username: str) -> Optional[Dict[str, Any]]:
        """Look up a user via WebFinger.
        
        Args:
            domain: User's domain
            username: Username to look up
            
        Returns:
            User info including profile URL, or None
        """
        resource = f"acct:{username}@{domain}"
        data = await WebFingerClient.finger(domain, resource)
        
        if data:
            # Extract links
            links = data.get("links", [])
            for link in links:
                if link.get("rel") == "self":
                    return {
                        "subject": data.get("subject"),
                        "profile_url": link.get("href"),
                        "rel": link.get("rel"),
                        "type": link.get("type")
                    }
        
        return None


class DiscoveryBootstrap:
    """Bootstrap service for discovering federated servers."""
    
    # Default seed servers (public DeceMSG servers)
    DEFAULT_SEEDS = [
        "decemsg.org",
        "fediverse.dece.chat"
    ]
    
    def __init__(self):
        self._directory = ServerDirectory()
        self._federation_client = get_federation_client()
        self._initialized = False
    
    async def initialize(self):
        """Initialize bootstrap - load seeds and check health."""
        if self._initialized:
            return
        
        config = get_config()
        
        # Add configured domain as first server
        if config.server.domain:
            self._directory.add_server(
                config.server.domain,
                f"https://{config.server.domain}"
            )
        
        # Try to discover servers from default seeds
        for seed in self.DEFAULT_SEEDS:
            if seed != config.server.domain:
                await self._directory.discover_servers_from_seed(seed)
        
        self._initialized = True
    
    async def discover_server(self, domain: str) -> Optional[ServerInfo]:
        """Discover a server, trying multiple methods.
        
        Methods tried in order:
        1. Local directory cache
        2. DNS SRV lookup
        3. WebFinger
        4. Webfinger on domain itself
        5. Default ports
        """
        config = get_config()
        
        # Skip self
        if domain == config.server.domain:
            return None
        
        # Check directory first
        dir_server = self._directory.get_server(domain)
        if dir_server:
            # Try to use cached info
            if dir_server.is_reachable:
                info = ServerInfo(
                    domain=domain,
                    name=domain,
                    version="unknown",
                    api_url=dir_server.api_url
                )
                self._federation_client.registry.add_server(domain, info)
                return info
        
        # Use federation client's discovery
        return await self._federation_client.discover_server(domain)
    
    async def add_peer_server(self, domain: str, api_url: str) -> bool:
        """Manually add a peer server.
        
        Args:
            domain: Server domain
            api_url: Server API URL
            
        Returns:
            True if server was added and is reachable
        """
        self._directory.add_server(domain, api_url)
        return await self._directory.check_server_health(domain)
    
    def get_known_servers(self) -> List[Dict[str, Any]]:
        """Get list of all known servers."""
        return [
            {
                "domain": s.domain,
                "api_url": s.api_url,
                "is_reachable": s.is_reachable,
                "last_checked": s.last_checked.isoformat() if s.last_checked else None
            }
            for s in self._directory.get_all_servers()
        ]
    
    async def refresh_server_list(self):
        """Refresh health status of all known servers."""
        for server in self._directory.get_all_servers():
            await self._directory.check_server_health(server.domain)


# Global bootstrap instance
_bootstrap: Optional[DiscoveryBootstrap] = None


def get_discovery_bootstrap() -> DiscoveryBootstrap:
    """Get the global discovery bootstrap instance."""
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = DiscoveryBootstrap()
    return _bootstrap
