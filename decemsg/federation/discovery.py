"""Federation discovery protocol for DeceMSG."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import httpx
import asyncio
from urllib.parse import urlparse

from decemsg.core.config import get_config


class ServerInfo(BaseModel):
    """Information about a federated server."""
    domain: str
    name: str
    version: str
    api_url: str
    is_online: bool = True
    last_seen: Optional[str] = None


class FederationRegistry:
    """Registry for known federated servers."""
    
    def __init__(self):
        self._servers: Dict[str, ServerInfo] = {}
    
    def add_server(self, domain: str, info: ServerInfo):
        """Add a server to the registry."""
        self._servers[domain] = info
    
    def remove_server(self, domain: str):
        """Remove a server from the registry."""
        if domain in self._servers:
            del self._servers[domain]
    
    def get_server(self, domain: str) -> Optional[ServerInfo]:
        """Get server info by domain."""
        return self._servers.get(domain)
    
    def get_all_servers(self) -> List[ServerInfo]:
        """Get all registered servers."""
        return list(self._servers.values())
    
    def is_server_known(self, domain: str) -> bool:
        """Check if a server is known."""
        return domain in self._servers


class FederationClient:
    """Client for federated server communication."""
    
    def __init__(self):
        self.registry = FederationRegistry()
        self._timeout = 10.0
    
    async def discover_server(self, domain: str) -> Optional[ServerInfo]:
        """Discover a server using the federation protocol."""
        config = get_config()
        
        # Don't discover self
        if domain == config.server.domain:
            return None
        
        # Check if already known
        if self.registry.is_server_known(domain):
            return self.registry.get_server(domain)
        
        # Try to discover via .well-known endpoint
        server_url = self._build_server_url(domain)
        nodeinfo_url = f"{server_url}/.well-known/nodeinfo"
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Try nodeinfo first
                response = await client.get(nodeinfo_url)
                
                if response.status_code == 200:
                    data = response.json()
                    server_info = ServerInfo(
                        domain=domain,
                        name=data.get("name", domain),
                        version=data.get("version", "unknown"),
                        api_url=server_url
                    )
                    self.registry.add_server(domain, server_info)
                    return server_info
                    
        except Exception as e:
            print(f"Discovery failed for {domain}: {e}")
        
        return None
    
    async def lookup_user(self, username: str, domain: str) -> Optional[Dict[str, Any]]:
        """Look up a user on a federated server."""
        server_info = await self.discover_server(domain)
        
        if not server_info:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Query the user lookup endpoint
                response = await client.get(
                    f"{server_info.api_url}/federation/users/{username}",
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                    
        except Exception as e:
            print(f"User lookup failed for {username}@{domain}: {e}")
        
        return None
    
    async def send_message(
        self,
        from_user: str,
        from_domain: str,
        to_user: str,
        to_domain: str,
        content: str,
        message_type: str = "text"
    ) -> bool:
        """Send a message to a federated user."""
        server_info = await self.discover_server(to_domain)
        
        if not server_info:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{server_info.api_url}/federation/messages",
                    json={
                        "from_user": from_user,
                        "from_domain": from_domain,
                        "to_user": to_user,
                        "content": content,
                        "message_type": message_type
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                return response.status_code in (200, 201, 202)
                
        except Exception as e:
            print(f"Message send failed: {e}")
        
        return False
    
    async def broadcast_presence(
        self,
        user: str,
        domain: str,
        is_online: bool
    ):
        """Broadcast presence status to federated servers."""
        for server in self.registry.get_all_servers():
            if server.domain == domain:
                continue
            
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    await client.post(
                        f"{server.api_url}/federation/presence",
                        json={
                            "user": user,
                            "domain": domain,
                            "is_online": is_online
                        }
                    )
            except Exception:
                pass
    
    def _build_server_url(self, domain: str) -> str:
        """Build server URL from domain."""
        # Default to HTTPS
        if domain.startswith("http"):
            return domain.rstrip("/")
        return f"https://{domain}"
    
    async def discover_all_known_servers(self) -> List[ServerInfo]:
        """Discover and return all known servers."""
        # Return cached servers for now
        # In production, this would query a federation directory
        return self.registry.get_all_servers()
    
    async def health_check(self, domain: str) -> bool:
        """Check if a federated server is healthy."""
        server_info = self.registry.get_server(domain)
        
        if not server_info:
            server_info = await self.discover_server(domain)
        
        if not server_info:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{server_info.api_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def sync_chat(
        self,
        chat_id: str,
        member_ids: list[str],
        domain: str
    ) -> bool:
        """Sync chat membership with a federated server."""
        server_info = await self.discover_server(domain)

        if not server_info:
            return False

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{server_info.api_url}/federation/chats/sync",
                    json={
                        "chat_id": chat_id,
                        "members": member_ids
                    },
                    headers={"Content-Type": "application/json"}
                )

                return response.status_code in (200, 201, 202)

        except Exception as e:
            print(f"Chat sync failed: {e}")

        return False


# Global federation client instance
_federation_client: Optional[FederationClient] = None


def get_federation_client() -> FederationClient:
    """Get the global federation client instance."""
    global _federation_client
    if _federation_client is None:
        _federation_client = FederationClient()
    return _federation_client
