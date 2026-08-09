"""Server health monitoring for DeceMSG federation.

This module provides:
- Server uptime and reliability tracking
- Health check scheduling
- Automatic server status updates
- Preferred server selection
"""
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from collections import deque
import statistics

from decemsg.core.config import get_config


@dataclass
class ServerHealth:
    """Health metrics for a federated server."""
    domain: str
    api_url: str
    is_online: bool
    last_check: datetime
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    consecutive_failures: int
    avg_response_time_ms: float
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    response_times_ms: List[float]  # Recent response times
    
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "api_url": self.api_url,
            "is_online": self.is_online,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "consecutive_failures": self.consecutive_failures,
            "avg_response_time_ms": self.avg_response_time_ms,
            "uptime_percentage": self.uptime_percentage,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks
        }


class HealthMonitor:
    """Monitors health of federated servers."""
    
    def __init__(
        self,
        storage_path: str = "./data/server_health.json",
        check_interval: int = 60,
        max_response_times: int = 100
    ):
        self._storage_path = storage_path
        self._check_interval = check_interval
        self._max_response_times = max_response_times
        self._servers: Dict[str, ServerHealth] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._load()
    
    def _load(self):
        """Load health data from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for domain, health_data in data.get("servers", {}).items():
                    self._servers[domain] = ServerHealth(
                        domain=domain,
                        api_url=health_data["api_url"],
                        is_online=health_data.get("is_online", False),
                        last_check=datetime.fromisoformat(health_data["last_check"]) if health_data.get("last_check") else datetime.utcnow(),
                        last_success=datetime.fromisoformat(health_data["last_success"]) if health_data.get("last_success") else None,
                        last_failure=datetime.fromisoformat(health_data["last_failure"]) if health_data.get("last_failure") else None,
                        consecutive_failures=health_data.get("consecutive_failures", 0),
                        avg_response_time_ms=health_data.get("avg_response_time_ms", 0),
                        uptime_percentage=health_data.get("uptime_percentage", 100),
                        total_checks=health_data.get("total_checks", 0),
                        successful_checks=health_data.get("successful_checks", 0),
                        response_times_ms=health_data.get("response_times_ms", [])
                    )
        except Exception as e:
            print(f"Error loading health data: {e}")
    
    def _save(self):
        """Save health data to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "servers": {
                domain: health.to_dict()
                for domain, health in self._servers.items()
            }
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_server(self, domain: str, api_url: str):
        """Register a server for health monitoring."""
        if domain not in self._servers:
            self._servers[domain] = ServerHealth(
                domain=domain,
                api_url=api_url,
                is_online=False,
                last_check=datetime.utcnow(),
                last_success=None,
                last_failure=None,
                consecutive_failures=0,
                avg_response_time_ms=0,
                uptime_percentage=100,
                total_checks=0,
                successful_checks=0,
                response_times_ms=[]
            )
            self._save()
    
    def get_health(self, domain: str) -> Optional[ServerHealth]:
        """Get health data for a server."""
        return self._servers.get(domain)
    
    def get_all_health(self) -> List[ServerHealth]:
        """Get health data for all servers."""
        return list(self._servers.values())
    
    def get_online_servers(self) -> List[ServerHealth]:
        """Get all online servers."""
        return [s for s in self._servers.values() if s.is_online]
    
    def get_best_server(self, domains: List[str]) -> Optional[ServerHealth]:
        """Get the best server based on response time and uptime.
        
        Args:
            domains: List of server domains to consider
        
        Returns:
            The best server, or None if none are online
        """
        candidates = [
            self._servers[d] for d in domains
            if d in self._servers and self._servers[d].is_online
        ]
        
        if not candidates:
            return None
        
        # Sort by: uptime first, then response time
        candidates.sort(key=lambda s: (-s.uptime_percentage, s.avg_response_time_ms))
        
        return candidates[0]
    
    async def check_server(self, domain: str) -> ServerHealth:
        """Check the health of a server.
        
        Returns:
            Updated health data
        """
        import httpx
        
        if domain not in self._servers:
            # Auto-register with default URL
            api_url = f"https://{domain}"
            self.register_server(domain, api_url)
        
        health = self._servers[domain]
        health.last_check = datetime.utcnow()
        health.total_checks += 1
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{health.api_url}/health")
                
                elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if response.status_code == 200:
                health.is_online = True
                health.last_success = datetime.utcnow()
                health.consecutive_failures = 0
                health.successful_checks += 1
                
                # Update response times
                health.response_times_ms.append(elapsed_ms)
                if len(health.response_times_ms) > self._max_response_times:
                    health.response_times_ms = health.response_times_ms[-self._max_response_times:]
                
                health.avg_response_time_ms = statistics.mean(health.response_times_ms)
                
                # Update uptime
                health.uptime_percentage = (
                    health.successful_checks / health.total_checks * 100
                )
            else:
                raise Exception(f"Health check returned {response.status_code}")
                
        except Exception as e:
            health.is_online = False
            health.last_failure = datetime.utcnow()
            health.consecutive_failures += 1
            print(f"Health check failed for {domain}: {e}")
        
        self._save()
        return health
    
    async def check_all_servers(self):
        """Check health of all registered servers."""
        for domain in list(self._servers.keys()):
            await self.check_server(domain)
    
    async def start_monitoring(self):
        """Start background health monitoring."""
        self._running = True
        
        while self._running:
            try:
                await self.check_all_servers()
            except Exception as e:
                print(f"Error in health monitoring: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()


# Global instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
