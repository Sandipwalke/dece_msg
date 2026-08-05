"""DeceMSG WebSocket connection manager."""
import json
from typing import Dict, Set, Optional
from datetime import datetime

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for real-time messaging."""
    
    def __init__(self):
        # user_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # chat_id -> set of user_ids (for chat room subscriptions)
        self.chat_rooms: Dict[str, Set[str]] = {}
        # user_id -> last seen timestamp
        self.last_seen: Dict[str, datetime] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.last_seen[user_id] = datetime.utcnow()
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send a message to a specific user."""
        if user_id in self.active_connections:
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass  # Connection might be closed
    
    async def send_to_users(self, message: dict, user_ids: list[str]):
        """Send a message to multiple users."""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
    
    def join_chat_room(self, user_id: str, chat_id: str):
        """Add a user to a chat room."""
        if chat_id not in self.chat_rooms:
            self.chat_rooms[chat_id] = set()
        self.chat_rooms[chat_id].add(user_id)
    
    def leave_chat_room(self, user_id: str, chat_id: str):
        """Remove a user from a chat room."""
        if chat_id in self.chat_rooms:
            self.chat_rooms[chat_id].discard(user_id)
            if not self.chat_rooms[chat_id]:
                del self.chat_rooms[chat_id]
    
    async def broadcast_to_chat(self, message: dict, chat_id: str, exclude_user: str = None):
        """Broadcast a message to all users in a chat room."""
        if chat_id in self.chat_rooms:
            for user_id in self.chat_rooms[chat_id]:
                if user_id != exclude_user:
                    await self.send_personal_message(message, user_id)
    
    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is currently online."""
        return user_id in self.active_connections
    
    def get_online_users(self) -> list[str]:
        """Get list of all online user IDs."""
        return list(self.active_connections.keys())
    
    async def broadcast_online_status(self, user_id: str, is_online: bool):
        """Broadcast user online/offline status to their contacts."""
        status_message = {
            "type": "presence",
            "user_id": user_id,
            "is_online": is_online,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all connected users
        for uid in self.active_connections:
            if uid != user_id:
                await self.send_personal_message(status_message, uid)


# Global connection manager instance
manager = ConnectionManager()
