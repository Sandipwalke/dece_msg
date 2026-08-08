"""
DeceMSG MCP Client Example
AI Agent communicating via MCP with DeceMSG server.
"""
import asyncio
import json

from mcp.client import ClientSession
from mcp.client.stdio import stdio_client


async def main():
    """Example: AI Agent using MCP to communicate via DeceMSG."""
    
    # MCP server command (starts the DeceMSG MCP server)
    # In production, this would be configured in your AI client's MCP settings
    
    server_command = ["python", "-m", "decemsg.mcp.server"]
    
    async with stdio_client(server_command) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()
            
            # 1. Register a new agent (if needed)
            print("=== Registering AI Agent ===")
            result = await session.call_tool(
                "decemsg_register_agent",
                {
                    "agent_id": "weather-bot",
                    "display_name": "Weather Bot",
                    "password": "secure_password_123",
                    "domain": "localhost"
                }
            )
            print(result.content[0].text)
            
            # 2. Login
            print("\n=== Logging in ===")
            result = await session.call_tool(
                "decemsg_login",
                {
                    "username": "weather-bot",
                    "password": "secure_password_123"
                }
            )
            print(result.content[0].text)
            login_data = json.loads(result.content[0].text)
            agent_id = login_data["agent_id"]
            
            # 3. List chats
            print("\n=== Listing Chats ===")
            result = await session.call_tool(
                "decemsg_list_chats",
                {"agent_id": agent_id}
            )
            print(result.content[0].text)
            
            # 4. Search for users
            print("\n=== Searching Users ===")
            result = await session.call_tool(
                "decemsg_search_users",
                {"agent_id": agent_id, "query": "alice"}
            )
            print(result.content[0].text)
            
            # 5. Send a message (if we have a chat_id)
            # chat_id = "your-chat-id-here"
            # print("\n=== Sending Message ===")
            # result = await session.call_tool(
            #     "decemsg_send_message",
            #     {
            #         "agent_id": agent_id,
            #         "chat_id": chat_id,
            #         "content": "Hello! I'm Weather Bot. Ask me about weather!"
            #     }
            # )
            # print(result.content[0].text)
            
            print("\n✅ AI Agent MCP example complete!")


if __name__ == "__main__":
    asyncio.run(main())
