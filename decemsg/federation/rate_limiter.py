"""Per-server rate limiting for DeceMSG federation.

This module provides:
- Rate limiting per federated server
- Request counting and throttling
- Configurable limits per server
- Automatic limit enforcement
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from collections import defaultdict, deque
import time

from decemsg.core.config import get_config


@dataclass
class RateLimit:
    """Rate limit configuration for a server."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10


@dataclass
class ServerRateStatus:
    """Current rate limiting status for a server."""
    domain: str
    minute_requests: List[float] = field(default_factory=list)
    hour_requests: List[float] = field(default_factory=list)
    day_requests: List[float] = field(default_factory=list)
    is_limited: bool = False
    limited_until: Optional[datetime] = None
    total_requests: int = 0
    blocked_requests: int = 0
    
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "minute_count": len(self.minute_requests),
            "hour_count": len(self.hour_requests),
            "day_count": len(self.day_requests),
            "is_limited": self.is_limited,
            "limited_until": self.limited_until.isoformat() if self.limited_until else None,
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests
        }


class PerServerRateLimiter:
    """Rate limiter with per-server tracking."""
    
    def __init__(self, storage_path: str = "./data/server_rate_limits.json"):
        self._storage_path = storage_path
        self._limits: Dict[str, RateLimit] = {}
        self._status: Dict[str, ServerRateStatus] = {}
        self._default_limit = RateLimit()
        self._load()
    
    def _load(self):
        """Load rate limits from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                
            # Load custom limits
            for domain, limit_data in data.get("limits", {}).items():
                self._limits[domain] = RateLimit(
                    requests_per_minute=limit_data.get("requests_per_minute", 60),
                    requests_per_hour=limit_data.get("requests_per_hour", 1000),
                    requests_per_day=limit_data.get("requests_per_day", 10000),
                    burst_limit=limit_data.get("burst_limit", 10)
                )
            
            # Load status
            for domain, status_data in data.get("status", {}).items():
                status = ServerRateStatus(
                    domain=domain,
                    minute_requests=[datetime.fromisoformat(t) for t in status_data.get("minute_requests", [])],
                    hour_requests=[datetime.fromisoformat(t) for t in status_data.get("hour_requests", [])],
                    day_requests=[datetime.fromisoformat(t) for t in status_data.get("day_requests", [])],
                    is_limited=status_data.get("is_limited", False),
                    limited_until=datetime.fromisoformat(status_data["limited_until"]) if status_data.get("limited_until") else None,
                    total_requests=status_data.get("total_requests", 0),
                    blocked_requests=status_data.get("blocked_requests", 0)
                )
                self._status[domain] = status
                
        except Exception as e:
            print(f"Error loading rate limits: {e}")
    
    def _save(self):
        """Save rate limits to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "limits": {
                domain: {
                    "requests_per_minute": limit.requests_per_minute,
                    "requests_per_hour": limit.requests_per_hour,
                    "requests_per_day": limit.requests_per_day,
                    "burst_limit": limit.burst_limit
                }
                for domain, limit in self._limits.items()
            },
            "status": {
                domain: {
                    "minute_requests": [t.isoformat() for t in status.minute_requests],
                    "hour_requests": [t.isoformat() for t in status.hour_requests],
                    "day_requests": [t.isoformat() for t in status.day_requests],
                    "is_limited": status.is_limited,
                    "limited_until": status.limited_until.isoformat() if status.limited_until else None,
                    "total_requests": status.total_requests,
                    "blocked_requests": status.blocked_requests
                }
                for domain, status in self._status.items()
            }
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _cleanup_old_requests(self, status: ServerRateStatus):
        """Remove expired request timestamps."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        status.minute_requests = [t for t in status.minute_requests if t > minute_ago]
        status.hour_requests = [t for t in status.hour_requests if t > hour_ago]
        status.day_requests = [t for t in status.day_requests if t > day_ago]
    
    def set_limit(self, domain: str, limit: RateLimit):
        """Set custom rate limit for a server."""
        self._limits[domain] = limit
        self._save()
    
    def get_limit(self, domain: str) -> RateLimit:
        """Get rate limit for a server."""
        return self._limits.get(domain, self._default_limit)
    
    def check_rate_limit(self, domain: str) -> tuple[bool, str]:
        """Check if a request from a server is within rate limits.
        
        Returns:
            Tuple of (is_allowed, reason)
        """
        now = datetime.utcnow()
        
        # Ensure status exists
        if domain not in self._status:
            self._status[domain] = ServerRateStatus(domain=domain)
        
        status = self._status[domain]
        limit = self.get_limit(domain)
        
        # Check if currently limited
        if status.is_limited and status.limited_until:
            if now < status.limited_until:
                status.blocked_requests += 1
                self._save()
                return False, f"Rate limited until {status.limited_until.isoformat()}"
            else:
                # Limit expired
                status.is_limited = False
                status.limited_until = None
        
        # Cleanup old requests
        self._cleanup_old_requests(status)
        
        # Check minute limit
        if len(status.minute_requests) >= limit.requests_per_minute:
            status.is_limited = True
            status.limited_until = now + timedelta(minutes=1)
            status.blocked_requests += 1
            self._save()
            return False, "Minute rate limit exceeded"
        
        # Check hour limit
        if len(status.hour_requests) >= limit.requests_per_hour:
            status.is_limited = True
            status.limited_until = now + timedelta(minutes=5)
            status.blocked_requests += 1
            self._save()
            return False, "Hour rate limit exceeded"
        
        # Check day limit
        if len(status.day_requests) >= limit.requests_per_day:
            status.is_limited = True
            status.limited_until = now + timedelta(hours=1)
            status.blocked_requests += 1
            self._save()
            return False, "Day rate limit exceeded"
        
        # Record request
        status.minute_requests.append(now)
        status.hour_requests.append(now)
        status.day_requests.append(now)
        status.total_requests += 1
        
        self._save()
        return True, "OK"
    
    def record_request(self, domain: str):
        """Record a request from a server."""
        now = datetime.utcnow()
        
        if domain not in self._status:
            self._status[domain] = ServerRateStatus(domain=domain)
        
        status = self._status[domain]
        status.minute_requests.append(now)
        status.hour_requests.append(now)
        status.day_requests.append(now)
        status.total_requests += 1
        
        self._save()
    
    def get_status(self, domain: str) -> Optional[ServerRateStatus]:
        """Get rate limiting status for a server."""
        return self._status.get(domain)
    
    def get_all_status(self) -> List[Dict]:
        """Get status for all servers."""
        return [status.to_dict() for status in self._status.values()]
    
    def reset_server(self, domain: str) -> bool:
        """Reset rate limits for a server."""
        if domain in self._status:
            del self._status[domain]
            self._save()
            return True
        return False
    
    def get_stats(self) -> Dict:
        """Get overall rate limiting statistics."""
        total_requests = sum(s.total_requests for s in self._status.values())
        total_blocked = sum(s.blocked_requests for s in self._status.values())
        
        return {
            "total_servers_tracked": len(self._status),
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "blocked_percentage": (total_blocked / total_requests * 100) if total_requests > 0 else 0
        }


# Global instance
_rate_limiter: Optional[PerServerRateLimiter] = None


def get_rate_limiter() -> PerServerRateLimiter:
    """Get the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = PerServerRateLimiter()
    return _rate_limiter
