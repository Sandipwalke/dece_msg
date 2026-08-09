"""Spam filtering for DeceMSG federation.

This module provides:
- Content-based spam filtering
- Server reputation tracking
- Block list management
- Automated spam detection
"""
import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, field
from collections import defaultdict
import re

from decemsg.core.config import get_config


@dataclass
class ServerReputation:
    """Reputation score for a federated server."""
    domain: str
    score: float = 100.0  # 0-100, higher is better
    message_count: int = 0
    spam_count: int = 0
    false_positive_count: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_message: Optional[datetime] = None
    is_blocked: bool = False
    blocked_reason: Optional[str] = None
    blocked_until: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "score": self.score,
            "message_count": self.message_count,
            "spam_count": self.spam_count,
            "is_blocked": self.is_blocked,
            "blocked_reason": self.blocked_reason,
            "spam_rate": (self.spam_count / self.message_count * 100) if self.message_count > 0 else 0
        }


@dataclass
class FilterResult:
    """Result of spam filtering."""
    is_allowed: bool
    is_spam: bool
    score: float
    reasons: List[str]
    matched_patterns: List[str]


class SpamFilter:
    """Content-based spam filter for federated messages."""
    
    # Common spam patterns
    SPAM_PATTERNS = [
        # Excessive caps
        r'^[A-Z\s]{20,}$',
        # Excessive punctuation
        r'[!]{5,}',
        r'[?]{5,}',
        r'[0-9]{10,}',  # Phone numbers
        # Suspicious URLs
        r'https?://[^\s]*\.(xyz|tk|ml|ga|cf|gq)/[^\s]+',
        # Cryptocurrency addresses
        r'\b(1|3|bc1)[a-zA-Z0-9]{25,}\b',
        # Common scam phrases
        r'\b(urgent|act now|limited time|click here|free money)\b',
        r'\b(winner|congratulations|you won)\b',
        # Excessive emoji
        r'[\U0001F600-\U0001F64F]{10,}',
    ]
    
    # Patterns that trigger immediate block
    BLOCK_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # XSS
        r'on\w+\s*=',  # Event handlers
    ]
    
    def __init__(self, storage_path: str = "./data/spam_filter.json"):
        self._storage_path = storage_path
        self._server_reputations: Dict[str, ServerReputation] = {}
        self._blocked_domains: Set[str] = set()
        self._whitelist_domains: Set[str] = set()
        self._content_hashes: Dict[str, int] = {}  # Track duplicate content
        self._load()
    
    def _load(self):
        """Load spam filter data from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
            
            for domain, rep_data in data.get("reputations", {}).items():
                self._server_reputations[domain] = ServerReputation(
                    domain=domain,
                    score=rep_data.get("score", 100),
                    message_count=rep_data.get("message_count", 0),
                    spam_count=rep_data.get("spam_count", 0),
                    false_positive_count=rep_data.get("false_positive_count", 0),
                    first_seen=datetime.fromisoformat(rep_data.get("first_seen", datetime.utcnow().isoformat())),
                    last_message=datetime.fromisoformat(rep_data["last_message"]) if rep_data.get("last_message") else None,
                    is_blocked=rep_data.get("is_blocked", False),
                    blocked_reason=rep_data.get("blocked_reason"),
                    blocked_until=datetime.fromisoformat(rep_data["blocked_until"]) if rep_data.get("blocked_until") else None
                )
            
            self._blocked_domains = set(data.get("blocked_domains", []))
            self._whitelist_domains = set(data.get("whitelist_domains", []))
            self._content_hashes = data.get("content_hashes", {})
            
        except Exception as e:
            print(f"Error loading spam filter: {e}")
    
    def _save(self):
        """Save spam filter data to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "reputations": {
                domain: {
                    "score": rep.score,
                    "message_count": rep.message_count,
                    "spam_count": rep.spam_count,
                    "false_positive_count": rep.false_positive_count,
                    "first_seen": rep.first_seen.isoformat(),
                    "last_message": rep.last_message.isoformat() if rep.last_message else None,
                    "is_blocked": rep.is_blocked,
                    "blocked_reason": rep.blocked_reason,
                    "blocked_until": rep.blocked_until.isoformat() if rep.blocked_until else None
                }
                for domain, rep in self._server_reputations.items()
            },
            "blocked_domains": list(self._blocked_domains),
            "whitelist_domains": list(self._whitelist_domains),
            "content_hashes": self._content_hashes
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_content(self, content: str) -> FilterResult:
        """Check content for spam patterns.
        
        Returns:
            FilterResult with spam assessment
        """
        reasons = []
        matched_patterns = []
        spam_score = 0.0
        
        # Check block patterns (immediate rejection)
        for pattern in self.BLOCK_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                reasons.append(f"Blocked pattern: {pattern[:30]}...")
                matched_patterns.append(pattern)
                spam_score += 100
        
        if spam_score >= 100:
            return FilterResult(
                is_allowed=False,
                is_spam=True,
                score=spam_score,
                reasons=reasons,
                matched_patterns=matched_patterns
            )
        
        # Check spam patterns
        for pattern in self.SPAM_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                reasons.append(f"Spam pattern: {pattern[:30]}...")
                matched_patterns.append(pattern)
                spam_score += 10
        
        # Check for duplicate content
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if content_hash in self._content_hashes:
            reasons.append("Duplicate content detected")
            spam_score += 15
            self._content_hashes[content_hash] += 1
        else:
            self._content_hashes[content_hash] = 1
        
        # Check content length
        if len(content) > 5000:
            reasons.append("Content too long")
            spam_score += 5
        
        # Check for excessive links
        url_count = len(re.findall(r'https?://[^\s]+', content))
        if url_count > 5:
            reasons.append(f"Too many links: {url_count}")
            spam_score += 10
        
        # Check for excessive mentions
        mention_count = len(re.findall(r'@[a-zA-Z0-9_]+', content))
        if mention_count > 10:
            reasons.append(f"Too many mentions: {mention_count}")
            spam_score += 10
        
        return FilterResult(
            is_allowed=spam_score < 50,
            is_spam=spam_score >= 50,
            score=spam_score,
            reasons=reasons,
            matched_patterns=matched_patterns
        )
    
    def check_server(self, domain: str) -> bool:
        """Check if a server is allowed.
        
        Returns:
            True if server is allowed
        """
        # Check whitelist
        if domain in self._whitelist_domains:
            return True
        
        # Check block list
        if domain in self._blocked_domains:
            return False
        
        # Check reputation
        if domain in self._server_reputations:
            rep = self._server_reputations[domain]
            
            # Check if temporarily blocked
            if rep.is_blocked and rep.blocked_until:
                if datetime.utcnow() < rep.blocked_until:
                    return False
                else:
                    # Unblock if time expired
                    rep.is_blocked = False
                    rep.blocked_until = None
            
            # Block if score too low
            if rep.score < 20:
                return False
        
        return True
    
    def record_message(self, domain: str, is_spam: bool = False):
        """Record a message from a server for reputation tracking."""
        if domain not in self._server_reputations:
            self._server_reputations[domain] = ServerReputation(domain=domain)
        
        rep = self._server_reputations[domain]
        rep.message_count += 1
        rep.last_message = datetime.utcnow()
        
        if is_spam:
            rep.spam_count += 1
            # Decrease score
            rep.score = max(0, rep.score - 5)
            
            # Auto-block if too many spams
            if rep.spam_count > 10 and (rep.spam_count / rep.message_count) > 0.5:
                rep.is_blocked = True
                rep.blocked_until = datetime.utcnow() + timedelta(hours=24)
                rep.blocked_reason = "High spam rate"
                self._blocked_domains.add(domain)
        else:
            # Increase score slowly
            rep.score = min(100, rep.score + 0.1)
        
        self._save()
    
    def report_false_positive(self, domain: str):
        """Report a false positive spam detection."""
        if domain in self._server_reputations:
            rep = self._server_reputations[domain]
            rep.false_positive_count += 1
            rep.score = min(100, rep.score + 5)
            
            if rep.score > 50:
                rep.is_blocked = False
                rep.blocked_until = None
                self._blocked_domains.discard(domain)
        
        self._save()
    
    def block_domain(self, domain: str, reason: str, duration: Optional[timedelta] = None):
        """Block a domain manually."""
        self._blocked_domains.add(domain)
        
        if domain not in self._server_reputations:
            self._server_reputations[domain] = ServerReputation(domain=domain)
        
        rep = self._server_reputations[domain]
        rep.is_blocked = True
        rep.blocked_reason = reason
        if duration:
            rep.blocked_until = datetime.utcnow() + duration
        
        self._save()
    
    def unblock_domain(self, domain: str) -> bool:
        """Unblock a domain."""
        if domain in self._blocked_domains:
            self._blocked_domains.discard(domain)
        
        if domain in self._server_reputations:
            rep = self._server_reputations[domain]
            rep.is_blocked = False
            rep.blocked_until = None
            rep.blocked_reason = None
        
        self._save()
        return True
    
    def whitelist_domain(self, domain: str):
        """Add a domain to the whitelist (bypass all filtering)."""
        self._whitelist_domains.add(domain)
        self._unblock_domain(domain)
        self._save()
    
    def remove_from_whitelist(self, domain: str) -> bool:
        """Remove a domain from the whitelist."""
        if domain in self._whitelist_domains:
            self._whitelist_domains.discard(domain)
            self._save()
            return True
        return False
    
    def _unblock_domain(self, domain: str):
        """Internal unblock without save."""
        self._blocked_domains.discard(domain)
        
        if domain in self._server_reputations:
            rep = self._server_reputations[domain]
            rep.is_blocked = False
            rep.blocked_until = None
            rep.blocked_reason = None
    
    def get_server_reputation(self, domain: str) -> Optional[ServerReputation]:
        """Get reputation for a server."""
        return self._server_reputations.get(domain)
    
    def get_blocked_domains(self) -> List[str]:
        """Get list of blocked domains."""
        return list(self._blocked_domains)
    
    def get_stats(self) -> Dict:
        """Get spam filter statistics."""
        total_messages = sum(r.message_count for r in self._server_reputations.values())
        total_spam = sum(r.spam_count for r in self._server_reputations.values())
        
        return {
            "total_servers_tracked": len(self._server_reputations),
            "blocked_domains": len(self._blocked_domains),
            "whitelisted_domains": len(self._whitelist_domains),
            "total_messages": total_messages,
            "total_spam": total_spam,
            "spam_rate": (total_spam / total_messages * 100) if total_messages > 0 else 0
        }


# Global instance
_spam_filter: Optional[SpamFilter] = None


def get_spam_filter() -> SpamFilter:
    """Get the global spam filter."""
    global _spam_filter
    if _spam_filter is None:
        _spam_filter = SpamFilter()
    return _spam_filter
