"""
DeceMSG MCP Server
Model Context Protocol server for AI agent communication via DeceMSG.
"""
import os
import json
import asyncio
from typing import Optional, List, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)
from mcp.server.callback_manager import ServerCallbackManager

# Create MCP Server
server = Server("decemsg-mcp", callback_manager=ServerCallbackManager())

# Server state
AGENTS = {}  # agent_id -> {"token": ..., "user_id": ..., "headers": ...}


# ============== MCP TOOLS ==============

@server.list_tools()
async def list_tools() -> ListToolsResult:
    """List available MCP tools."""
    return ListToolsResult(
        tools=[
            Tool(
                name="decemsg_login",
                description="Login to DeceMSG and get authentication token for an agent",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "Agent username (format: name#domain)"},
                        "password": {"type": "string", "description": "Agent password"},
                        "server_url": {"type": "string", "description": "DeceMSG server URL", "default": "http://localhost:8000"}
                    },
                    "required": ["username", "password"]
                }
            ),
            Tool(
                name="decemsg_send_message",
                description="Send a message to a chat",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"},
                        "chat_id": {"type": "string", "description": "Chat ID to send message to"},
                        "content": {"type": "string", "description": "Message content"},
                        "message_type": {"type": "string", "description": "Message type", "default": "TEXT"}
                    },
                    "required": ["agent_id", "chat_id", "content"]
                }
            ),
            Tool(
                name="decemsg_get_messages",
                description="Get messages from a chat",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"},
                        "chat_id": {"type": "string", "description": "Chat ID to get messages from"},
                        "limit": {"type": "integer", "description": "Max messages to retrieve", "default": 50}
                    },
                    "required": ["agent_id", "chat_id"]
                }
            ),
            Tool(
                name="decemsg_list_chats",
                description="List all chats the agent is a member of",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"}
                    },
                    "required": ["agent_id"]
                }
            ),
            Tool(
                name="decemsg_create_chat",
                description="Create a new chat (direct or group)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"},
                        "name": {"type": "string", "description": "Chat name (for groups)"},
                        "is_group": {"type": "boolean", "description": "Create as group chat", "default": False},
                        "members": {"type": "array", "items": {"type": "string"}, "description": "Username#domain of members to add"}
                    },
                    "required": ["agent_id"]
                }
            ),
            Tool(
                name="decemsg_search_users",
                description="Search for users on the server",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"},
                        "query": {"type": "string", "description": "Search query (username or display name)"}
                    },
                    "required": ["agent_id", "query"]
                }
            ),
            Tool(
                name="decemsg_add_reaction",
                description="Add a reaction emoji to a message",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID from login"},
                        "message_id": {"type": "string", "description": "Message ID to react to"},
                        "emoji": {"type": "string", "description": "Emoji reaction (e.g., 👍, 🎉)"}
                    },
                    "required": ["agent_id", "message_id", "emoji"]
                }
            ),
            Tool(
                name="decemsg_register_agent",
                description="Register a new agent/account on the server",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Unique agent identifier (e.g., 'weather-bot')"},
                        "display_name": {"type": "string", "description": "Display name for the agent"},
                        "password": {"type": "string", "description": "Agent password"},
                        "domain": {"type": "string", "description": "Server domain", "default": "localhost"},
                        "server_url": {"type": "string", "description": "DeceMSG server URL", "default": "http://localhost:8000"}
                    },
                    "required": ["agent_id", "display_name", "password"]
                }
            )
        ]
    )


# ============== TOOL HANDLERS ==============

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle tool calls from MCP clients."""
    
    try:
        if name == "decemsg_login":
            return await decemsg_login(
                arguments.get("username"),
                arguments.get("password"),
                arguments.get("server_url", "http://localhost:8000")
            )
        
        elif name == "decemsg_send_message":
            return await decemsg_send_message(
                arguments.get("agent_id"),
                arguments.get("chat_id"),
                arguments.get("content"),
                arguments.get("message_type", "TEXT")
            )
        
        elif name == "decemsg_get_messages":
            return await decemsg_get_messages(
                arguments.get("agent_id"),
                arguments.get("chat_id"),
                arguments.get("limit", 50)
            )
        
        elif name == "decemsg_list_chats":
            return await decemsg_list_chats(arguments.get("agent_id"))
        
        elif name == "decemsg_create_chat":
            return await decemsg_create_chat(
                arguments.get("agent_id"),
                arguments.get("name"),
                arguments.get("is_group", False),
                arguments.get("members", [])
            )
        
        elif name == "decemsg_search_users":
            return await decemsg_search_users(
                arguments.get("agent_id"),
                arguments.get("query")
            )
        
        elif name == "decemsg_add_reaction":
            return await decemsg_add_reaction(
                arguments.get("agent_id"),
                arguments.get("message_id"),
                arguments.get("emoji")
            )
        
        elif name == "decemsg_register_agent":
            return await decemsg_register_agent(
                arguments.get("agent_id"),
                arguments.get("display_name"),
                arguments.get("password"),
                arguments.get("domain", "localhost"),
                arguments.get("server_url", "http://localhost:8000")
            )
        
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True
            )
    
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True
        )


# ============== IMPLEMENTATIONS ==============

async def decemsg_login(username: str, password: str, server_url: str) -> CallToolResult:
    """Login to DeceMSG."""
    import httpx
    
    async with httpx.AsyncClient(base_url=server_url) as client:
        try:
            response = await client.post(
                "/api/auth/login",
                data={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data["access_token"]
                
                # Generate agent ID
                import uuid
                agent_id = f"agent_{uuid.uuid4().hex[:8]}"
                
                # Get user info
                user_response = await client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                user_data = user_response.json()
                
                # Store agent
                AGENTS[agent_id] = {
                    "token": token,
                    "user_id": user_data["id"],
                    "username": username,
                    "server_url": server_url,
                    "headers": {"Authorization": f"Bearer {token}"}
                }
                
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "agent_id": agent_id,
                            "username": user_data["username"],
                            "display_name": user_data["display_name"],
                            "message": f"Logged in as {username}. Use agent_id '{agent_id}' for subsequent calls."
                        }, indent=2)
                    )]
                )
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Login failed: {response.json().get('detail', 'Unknown error')}")],
                    isError=True
                )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Connection error: {str(e)}")],
                isError=True
            )


async def decemsg_send_message(agent_id: str, chat_id: str, content: str, message_type: str = "TEXT") -> CallToolResult:
    """Send a message to a chat."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.post(
            f"/api/chats/{chat_id}/messages",
            json={"content": content, "message_type": message_type},
            headers=agent["headers"]
        )
        
        if response.status_code == 201:
            data = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "success": True,
                    "message_id": data["id"],
                    "chat_id": chat_id,
                    "content": content,
                    "sent_at": data["created_at"]
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to send: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_get_messages(agent_id: str, chat_id: str, limit: int = 50) -> CallToolResult:
    """Get messages from a chat."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.get(
            f"/api/chats/{chat_id}/messages",
            params={"limit": limit},
            headers=agent["headers"]
        )
        
        if response.status_code == 200:
            messages = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "chat_id": chat_id,
                    "count": len(messages),
                    "messages": messages
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to get messages: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_list_chats(agent_id: str) -> CallToolResult:
    """List all chats for an agent."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.get("/api/chats", headers=agent["headers"])
        
        if response.status_code == 200:
            chats = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "chats": chats
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to list chats: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_create_chat(agent_id: str, name: str = None, is_group: bool = False, members: list = []) -> CallToolResult:
    """Create a new chat."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    payload = {
        "is_group": is_group,
        "member_usernames": members
    }
    if name:
        payload["name"] = name
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.post("/api/chats", json=payload, headers=agent["headers"])
        
        if response.status_code in [200, 201]:
            data = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "success": True,
                    "chat_id": data["id"],
                    "name": data.get("name"),
                    "is_group": data.get("is_group", False)
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to create chat: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_search_users(agent_id: str, query: str) -> CallToolResult:
    """Search for users."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.get("/api/users/search", params={"q": query}, headers=agent["headers"])
        
        if response.status_code == 200:
            users = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "query": query,
                    "count": len(users),
                    "users": users
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Search failed: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_add_reaction(agent_id: str, message_id: str, emoji: str) -> CallToolResult:
    """Add reaction to a message."""
    agent = AGENTS.get(agent_id)
    if not agent:
        return CallToolResult(content=[TextContent(type="text", text="Invalid agent_id. Login first.")], isError=True)
    
    import httpx
    
    async with httpx.AsyncClient(base_url=agent["server_url"]) as client:
        response = await client.post(
            f"/api/messages/{message_id}/reactions",
            json={"emoji": emoji},
            headers=agent["headers"]
        )
        
        if response.status_code == 200:
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "success": True,
                    "message_id": message_id,
                    "emoji": emoji
                }, indent=2))]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to add reaction: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


async def decemsg_register_agent(agent_id: str, display_name: str, password: str, domain: str, server_url: str) -> CallToolResult:
    """Register a new agent on the server."""
    import httpx
    
    async with httpx.AsyncClient(base_url=server_url) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "username": agent_id,
                "display_name": display_name,
                "password": password,
                "domain": domain
            }
        )
        
        if response.status_code == 201:
            user_data = response.json()
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({
                    "success": True,
                    "username": user_data["username"],
                    "display_name": user_data["display_name"],
                    "message": "Agent registered. Now login with decemsg_login."
                }, indent=2))]
            )
        elif response.status_code == 403:
            return CallToolResult(
                content=[TextContent(type="text", text="Public registration disabled. Ask admin to create agent account.")],
                isError=True
            )
        elif response.status_code == 400:
            return CallToolResult(
                content=[TextContent(type="text", text="Username already taken. Try a different agent_id.")],
                isError=True
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Registration failed: {response.json().get('detail', 'Unknown error')}")],
                isError=True
            )


# ============== MAIN ==============

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
