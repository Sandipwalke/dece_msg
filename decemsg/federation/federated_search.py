"""Federated search for DeceMSG.

This module provides:
- Search messages across federated servers
- Federated search coordination
- Result aggregation and ranking
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import re

from decemsg.core.config import get_config
from decemsg.core.database import get_db


@dataclass
class SearchResult:
    """A search result from a message."""
    message_id: str
    chat_id: str
    sender_id: str
    sender_username: str
    content: str
    message_type: str
    created_at: datetime
    relevance_score: float
    server_domain: str
    
    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "sender_username": self.sender_username,
            "content": self.content[:200],  # Truncate for display
            "message_type": self.message_type,
            "created_at": self.created_at.isoformat(),
            "relevance_score": self.relevance_score,
            "server_domain": self.server_domain
        }


@dataclass
class SearchResponse:
    """Aggregated search response from multiple servers."""
    query: str
    total_results: int
    results: List[SearchResult]
    searched_servers: List[str]
    search_time_ms: float
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total_results": self.total_results,
            "results": [r.to_dict() for r in self.results],
            "searched_servers": self.searched_servers,
            "search_time_ms": self.search_time_ms,
            "errors": self.errors
        }


class FederatedSearchEngine:
    """Search engine that coordinates searches across federated servers."""
    
    def __init__(self):
        self._search_history: List[Dict] = []
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """Calculate relevance score for a search result.
        
        Simple scoring based on:
        - Exact match bonus
        - Word frequency
        - Position (earlier = higher)
        """
        query_lower = query.lower()
        content_lower = content.lower()
        
        score = 0.0
        
        # Exact match bonus
        if query_lower in content_lower:
            score += 10.0
        
        # Word matches
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        matching_words = query_words & content_words
        
        if query_words:
            score += (len(matching_words) / len(query_words)) * 5.0
        
        # Position bonus (earlier = higher)
        first_match = content_lower.find(query_lower)
        if first_match >= 0:
            score += max(0, 5 - (first_match / 50))
        
        return min(score, 20.0)  # Cap at 20
    
    async def search_local(
        self,
        query: str,
        user_id: str,
        limit: int = 50,
        message_types: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """Search local messages.
        
        Args:
            query: Search query string
            user_id: User performing the search (for access control)
            limit: Maximum results to return
            message_types: Filter by message types
        
        Returns:
            List of matching SearchResult objects
        """
        from sqlalchemy import select, or_
        from sqlalchemy.orm import selectinload
        from decemsg.models.message import Message
        from decemsg.models.chat import Chat, ChatMember
        from decemsg.models.user import User
        
        results = []
        
        async for db in get_db():
            # Get user's accessible chats
            result = await db.execute(
                select(ChatMember.chat_id).where(ChatMember.user_id == user_id)
            )
            accessible_chats = [row[0] for row in result.fetchall()]
            
            # Build search query
            search_query = select(Message).options(
                selectinload(Message.sender)
            ).where(
                Message.chat_id.in_(accessible_chats),
                Message.is_deleted == False,
                Message.content.ilike(f"%{query}%")
            )
            
            if message_types:
                search_query = search_query.where(
                    Message.message_type.in_(message_types)
                )
            
            search_query = search_query.order_by(Message.created_at.desc()).limit(limit * 2)
            
            result = await db.execute(search_query)
            messages = result.scalars().all()
            
            # Score and rank results
            scored_results = []
            for msg in messages:
                relevance = self._calculate_relevance(query, msg.content)
                sender_name = msg.sender.username if msg.sender else "Unknown"
                
                result = SearchResult(
                    message_id=msg.id,
                    chat_id=msg.chat_id,
                    sender_id=msg.sender_id,
                    sender_username=sender_name,
                    content=msg.content,
                    message_type=msg.message_type.value if hasattr(msg.message_type, 'value') else str(msg.message_type),
                    created_at=msg.created_at,
                    relevance_score=relevance,
                    server_domain=get_config().server.domain
                )
                scored_results.append(result)
            
            # Sort by relevance
            scored_results.sort(key=lambda x: -x.relevance_score)
            results = scored_results[:limit]
            
            break
        
        return results
    
    async def search_federated(
        self,
        query: str,
        user_id: str,
        domains: List[str],
        limit_per_server: int = 20
    ) -> List[SearchResult]:
        """Search messages on federated servers.
        
        Args:
            query: Search query
            user_id: User performing search
            domains: List of domains to search
            limit_per_server: Max results per server
        
        Returns:
            Aggregated results from all servers
        """
        from decemsg.federation.discovery import get_federation_client
        
        config = get_config()
        all_results = []
        errors = []
        
        async def search_server(domain: str) -> List[SearchResult]:
            if domain == config.server.domain:
                return []  # Already searched locally
            
            try:
                client = get_federation_client()
                server_info = await client.discover_server(domain)
                
                if not server_info:
                    return []
                
                import httpx
                async with httpx.AsyncClient(timeout=15.0) as http_client:
                    response = await http_client.post(
                        f"{server_info.api_url}/federation/search",
                        json={
                            "query": query,
                            "user_id": user_id,
                            "limit": limit_per_server
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = []
                        
                        for msg_data in data.get("results", []):
                            result = SearchResult(
                                message_id=msg_data["message_id"],
                                chat_id=msg_data["chat_id"],
                                sender_id=msg_data["sender_id"],
                                sender_username=msg_data.get("sender_username", "Unknown"),
                                content=msg_data["content"],
                                message_type=msg_data["message_type"],
                                created_at=datetime.fromisoformat(msg_data["created_at"]),
                                relevance_score=msg_data.get("relevance_score", 1.0),
                                server_domain=domain
                            )
                            results.append(result)
                        
                        return results
                    else:
                        errors.append(f"{domain}: HTTP {response.status_code}")
                        
            except Exception as e:
                errors.append(f"{domain}: {str(e)}")
            
            return []
        
        # Search all servers in parallel
        tasks = [search_server(d) for d in domains]
        server_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for results in server_results:
            if isinstance(results, list):
                all_results.extend(results)
        
        # Sort by relevance
        all_results.sort(key=lambda x: -x.relevance_score)
        
        return all_results
    
    async def search(
        self,
        query: str,
        user_id: str,
        include_federated: bool = True,
        limit: int = 50
    ) -> SearchResponse:
        """Perform a federated search.
        
        Args:
            query: Search query string
            user_id: User performing the search
            include_federated: Whether to search federated servers
            limit: Maximum total results
        
        Returns:
            SearchResponse with aggregated results
        """
        import time
        start_time = time.time()
        
        errors = []
        all_results = []
        searched_servers = [get_config().server.domain]
        
        # Search local first
        local_results = await self.search_local(query, user_id, limit)
        all_results.extend(local_results)
        
        # Get federated domains if needed
        federated_domains = []
        if include_federated:
            # Get domains from user's federated chats
            async for db in get_db():
                from sqlalchemy import select
                from decemsg.models.chat import ChatMember
                
                result = await db.execute(
                    select(ChatMember).where(ChatMember.user_id == user_id)
                )
                members = result.scalars().all()
                
                for member in members:
                    if "#" in member.user_id:
                        domain = member.user_id.split("#")[1]
                        if domain not in federated_domains:
                            federated_domains.append(domain)
                
                break
        
        # Search federated servers
        if federated_domains:
            federated_results = await self.search_federated(
                query, user_id, federated_domains, limit_per_server=20
            )
            all_results.extend(federated_results)
            searched_servers.extend(federated_domains)
        
        # Sort and limit
        all_results.sort(key=lambda x: -x.relevance_score)
        final_results = all_results[:limit]
        
        search_time_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=query,
            total_results=len(final_results),
            results=final_results,
            searched_servers=searched_servers,
            search_time_ms=search_time_ms,
            errors=errors
        )


# Global instance
_search_engine: Optional[FederatedSearchEngine] = None


def get_search_engine() -> FederatedSearchEngine:
    """Get the global search engine."""
    global _search_engine
    if _search_engine is None:
        _search_engine = FederatedSearchEngine()
    return _search_engine
