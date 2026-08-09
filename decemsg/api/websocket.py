"""DeceMSG WebSocket API endpoint."""
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from decemsg.core.database import get_db, get_session_factory
from decemsg.core.auth import decode_token
from decemsg.core.websocket import manager
from decemsg.core.config import get_config
from decemsg.models.user import User
from decemsg.models.chat import Chat, ChatMember

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time messaging."""
    # Authenticate via token in query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    # Verify user exists and is active
    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found or inactive")
            return
        
        # Update last seen
        user.last_seen = datetime.utcnow()
        await db.commit()
    
    # Connect to manager
    await manager.connect(websocket, user_id)
    
    # Load user's chats and subscribe to their chat rooms
    async with session_factory() as db:
        result = await db.execute(
            select(ChatMember).where(ChatMember.user_id == user_id)
        )
        memberships = result.scalars().all()
        for membership in memberships:
            manager.join_chat_room(user_id, membership.chat_id)
    
    # Broadcast online status
    await manager.broadcast_online_status(user_id, True)
    
    # Deliver any pending offline messages
    try:
        from decemsg.federation.offline_queue import notify_user_online
        await notify_user_online(user_id)
    except Exception as e:
        print(f"Error delivering offline messages: {e}")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                continue
            
            # Handle different message types
            message_type = message.get("type")
            
            if message_type == "ping":
                # Respond to ping with pong
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif message_type == "join_chat":
                # Join a specific chat room
                chat_id = message.get("chat_id")
                if chat_id:
                    # Verify user is a member
                    async with session_factory() as db:
                        result = await db.execute(
                            select(ChatMember).where(
                                ChatMember.chat_id == chat_id,
                                ChatMember.user_id == user_id
                            )
                        )
                        if result.scalar_one_or_none():
                            manager.join_chat_room(user_id, chat_id)
                            await websocket.send_json({
                                "type": "joined_chat",
                                "chat_id": chat_id
                            })
            
            elif message_type == "leave_chat":
                # Leave a specific chat room
                chat_id = message.get("chat_id")
                if chat_id:
                    manager.leave_chat_room(user_id, chat_id)
                    await websocket.send_json({
                        "type": "left_chat",
                        "chat_id": chat_id
                    })
            
            elif message_type == "typing":
                # Broadcast typing indicator
                chat_id = message.get("chat_id")
                is_typing = message.get("is_typing", True)
                if chat_id:
                    typing_message = {
                        "type": "typing",
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "is_typing": is_typing,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await manager.broadcast_to_chat(typing_message, chat_id, exclude_user=user_id)
                    
                    # Also send to federated users
                    try:
                        from decemsg.federation.federation_client import send_typing_indicator
                        await send_typing_indicator(chat_id, user_id, is_typing)
                    except Exception:
                        pass
            
            elif message_type == "read":
                # Mark messages as read
                chat_id = message.get("chat_id")
                message_id = message.get("message_id")
                if chat_id:
                    async with session_factory() as db:
                        result = await db.execute(
                            select(ChatMember).where(
                                ChatMember.chat_id == chat_id,
                                ChatMember.user_id == user_id
                            )
                        )
                        membership = result.scalar_one_or_none()
                        if membership:
                            membership.last_read_message_id = message_id
                            await db.commit()
                            
                            # Broadcast read receipt
                            read_receipt = {
                                "type": "read_receipt",
                                "chat_id": chat_id,
                                "user_id": user_id,
                                "message_id": message_id,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            await manager.broadcast_to_chat(read_receipt, chat_id, exclude_user=user_id)
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        pass
    
    finally:
        # Cleanup on disconnect
        manager.disconnect(websocket, user_id)
        
        # Leave all chat rooms
        async with session_factory() as db:
            result = await db.execute(
                select(ChatMember).where(ChatMember.user_id == user_id)
            )
            memberships = result.scalars().all()
            for membership in memberships:
                manager.leave_chat_room(user_id, membership.chat_id)
        
        # Broadcast offline status
        await manager.broadcast_online_status(user_id, False)


@router.get("/api/presence")
async def get_presence(
    user_ids: str,  # comma-separated list of user IDs
):
    """Get online status for a list of users."""
    ids = [uid.strip() for uid in user_ids.split(",")]
    presence = {}
    
    for uid in ids:
        presence[uid] = manager.is_user_online(uid)
    
    return presence
