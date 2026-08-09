"""Domain verification for DeceMSG federation.

This module provides:
- DNS-based domain ownership verification
- TXT record verification
- Challenge-response verification
- Verified domain registry
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import asyncio

from decemsg.core.config import get_config


class VerificationMethod(Enum):
    """Methods of domain verification."""
    TXT_RECORD = "txt_record"
    CHALLENGE = "challenge"
    WELL_KNOWN = "well_known"


@dataclass
class VerificationChallenge:
    """A domain verification challenge."""
    domain: str
    challenge: str
    expected_response: str
    created_at: datetime
    expires_at: datetime
    verified: bool = False
    verified_at: Optional[datetime] = None


class DomainVerifier:
    """Manages domain verification for federation."""
    
    VERIFICATION_PREFIX = "_decemsg-verification"
    
    def __init__(self, storage_path: str = "./data/verified_domains.json"):
        self._storage_path = storage_path
        self._challenges: Dict[str, VerificationChallenge] = {}
        self._verified_domains: Dict[str, datetime] = {}  # domain -> verified_at
        self._load()
    
    def _load(self):
        """Load verified domains from disk."""
        if not os.path.exists(self._storage_path):
            return
        
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                
            for domain, verified_at in data.get("verified_domains", {}).items():
                self._verified_domains[domain] = datetime.fromisoformat(verified_at)
            
            for challenge_data in data.get("challenges", []):
                challenge = VerificationChallenge(
                    domain=challenge_data["domain"],
                    challenge=challenge_data["challenge"],
                    expected_response=challenge_data["expected_response"],
                    created_at=datetime.fromisoformat(challenge_data["created_at"]),
                    expires_at=datetime.fromisoformat(challenge_data["expires_at"]),
                    verified=challenge_data.get("verified", False),
                    verified_at=datetime.fromisoformat(challenge_data["verified_at"]) if challenge_data.get("verified_at") else None
                )
                self._challenges[challenge_data["domain"]] = challenge
                
        except Exception as e:
            print(f"Error loading domain verification: {e}")
    
    def _save(self):
        """Save verification data to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        
        data = {
            "verified_domains": {
                domain: verified_at.isoformat()
                for domain, verified_at in self._verified_domains.items()
            },
            "challenges": [
                {
                    "domain": c.domain,
                    "challenge": c.challenge,
                    "expected_response": c.expected_response,
                    "created_at": c.created_at.isoformat(),
                    "expires_at": c.expires_at.isoformat(),
                    "verified": c.verified,
                    "verified_at": c.verified_at.isoformat() if c.verified_at else None
                }
                for c in self._challenges.values()
            ]
        }
        
        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_challenge(self, domain: str) -> Dict[str, Any]:
        """Create a verification challenge for a domain.
        
        Returns:
            Challenge details including DNS record to add
        """
        import dns.resolver
        import dns.exception
        
        # Generate challenge tokens
        challenge = secrets.token_urlsafe(32)
        expected_response = hashlib.sha256(
            f"{domain}:{challenge}".encode()
        ).hexdigest()
        
        # Create the challenge
        verification_challenge = VerificationChallenge(
            domain=domain,
            challenge=challenge,
            expected_response=expected_response,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self._challenges[domain] = verification_challenge
        self._save()
        
        # DNS record to add
        txt_record = f"{self.VERIFICATION_PREFIX}={challenge}"
        
        return {
            "domain": domain,
            "challenge": challenge,
            "txt_record": txt_record,
            "dns_type": "TXT",
            "instructions": f"Add a TXT record to {domain} with the value: {txt_record}",
            "expires_at": verification_challenge.expires_at.isoformat()
        }
    
    async def verify_domain(self, domain: str) -> bool:
        """Verify a domain by checking its DNS records.
        
        Returns:
            True if verification was successful
        """
        import dns.resolver
        import dns.exception
        
        if domain not in self._challenges:
            return False
        
        challenge = self._challenges[domain]
        
        # Check if expired
        if datetime.utcnow() > challenge.expires_at:
            return False
        
        # Check if already verified
        if challenge.verified:
            return True
        
        try:
            # Look up TXT records
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5.0
            
            answers = resolver.resolve(domain, 'TXT')
            
            expected_txt = f"{self.VERIFICATION_PREFIX}={challenge.challenge}"
            
            for rdata in answers:
                for txt in rdata.strings:
                    if txt.decode() == expected_txt:
                        # Verification successful
                        challenge.verified = True
                        challenge.verified_at = datetime.utcnow()
                        self._verified_domains[domain] = challenge.verified_at
                        self._save()
                        return True
            
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            pass
        except Exception as e:
            print(f"DNS verification error for {domain}: {e}")
        
        return False
    
    def is_verified(self, domain: str) -> bool:
        """Check if a domain is verified."""
        # Check memory first
        if domain in self._verified_domains:
            return True
        
        # Check challenges
        if domain in self._challenges:
            return self._challenges[domain].verified
        
        return False
    
    def get_verified_domains(self) -> List[str]:
        """Get list of all verified domains."""
        return list(self._verified_domains.keys())
    
    def revoke_verification(self, domain: str) -> bool:
        """Revoke verification for a domain."""
        if domain in self._verified_domains:
            del self._verified_domains[domain]
        
        if domain in self._challenges:
            del self._challenges[domain]
        
        self._save()
        return True
    
    def cleanup_expired(self) -> int:
        """Remove expired challenges."""
        now = datetime.utcnow()
        expired = [
            domain for domain, challenge in self._challenges.items()
            if now > challenge.expires_at and not challenge.verified
        ]
        
        for domain in expired:
            del self._challenges[domain]
        
        if expired:
            self._save()
        
        return len(expired)


# Federation verification helpers
async def verify_remote_domain(domain: str) -> bool:
    """Verify a remote domain for federation.
    
    This asks the remote server to prove ownership of its domain.
    
    Returns:
        True if domain is verified
    """
    from decemsg.federation.discovery import get_federation_client
    
    verifier = get_domain_verifier()
    
    # First check if already verified
    if verifier.is_verified(domain):
        return True
    
    try:
        client = get_federation_client()
        server_info = await client.discover_server(domain)
        
        if not server_info:
            return False
        
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            # Get verification challenge
            response = await http_client.get(
                f"{server_info.api_url}/federation/verify/challenge"
            )
            
            if response.status_code != 200:
                return False
            
            challenge_data = response.json()
            
            # Verify via DNS
            return await verifier.verify_domain(domain)
            
    except Exception as e:
        print(f"Error verifying domain {domain}: {e}")
        return False


# Global instance
_domain_verifier: Optional[DomainVerifier] = None


def get_domain_verifier() -> DomainVerifier:
    """Get the global domain verifier."""
    global _domain_verifier
    if _domain_verifier is None:
        _domain_verifier = DomainVerifier()
    return _domain_verifier
