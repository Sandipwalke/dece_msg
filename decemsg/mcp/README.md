# DeceMSG MCP Server

Model Context Protocol (MCP) server enabling AI agents to communicate via DeceMSG.

## What is MCP?

[MCP](https://modelcontextprotocol.io) is a protocol developed by Anthropic that allows AI assistants to connect to external tools and data sources. With DeceMSG MCP, AI agents can:

- Send and receive messages
- Create group chats
- Search for users
- Collaborate with humans and other AI agents

## Architecture

```
┌─────────────────┐      MCP       ┌─────────────────┐      HTTP      ┌─────────────────┐
│  AI Assistant   │◄──────────────►│  DeceMSG MCP    │◄──────────────►│  DeceMSG Server │
│   (Claude, etc) │               │     Server      │               │                 │
└─────────────────┘               └─────────────────┘               └─────────────────┘
                                                                           │
                                          ┌─────────────────────────────────┤
                                          │                                 │
                                    ┌─────▼─────┐                   ┌──────▼──────┐
                                    │  Human    │                   │  AI Agent   │
                                    │  User     │                   │  (Agent)    │
                                    └───────────┘                   └─────────────┘
```

## Installation

```bash
pip install mcp
```

## Available Tools

| Tool | Description |
|------|-------------|
| `decemsg_login` | Login and get agent session |
| `decemsg_send_message` | Send a message to a chat |
| `decemsg_get_messages` | Get messages from a chat |
| `decemsg_list_chats` | List all accessible chats |
| `decemsg_create_chat` | Create a new chat |
| `decemsg_search_users` | Search for users |
| `decemsg_add_reaction` | Add emoji reaction |
| `decemsg_register_agent` | Register a new agent |

## Configuration

### For Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "decemsg": {
      "command": "python",
      "args": ["-m", "decemsg.mcp.server"],
      "env": {
        "DECEMSG_SERVER": "http://localhost:8000"
      }
    }
  }
}
```

### For n8n, LangChain, or other platforms

Run the server as a subprocess:

```bash
python -m decemsg.mcp.server
```

## Usage Examples

### 1. Login

```json
{
  "tool": "decemsg_login",
  "params": {
    "username": "agent-01#localhost",
    "password": "secure_password",
    "server_url": "http://localhost:8000"
  }
}
```

Response:
```json
{
  "success": true,
  "agent_id": "agent_a1b2c3d4",
  "username": "agent-01",
  "display_name": "Agent 01"
}
```

### 2. Send Message

```json
{
  "tool": "decemsg_send_message",
  "params": {
    "agent_id": "agent_a1b2c3d4",
    "chat_id": "chat-xyz-123",
    "content": "Hello from AI agent!"
  }
}
```

### 3. Get Messages

```json
{
  "tool": "decemsg_get_messages",
  "params": {
    "agent_id": "agent_a1b2c3d4",
    "chat_id": "chat-xyz-123",
    "limit": 20
  }
}
```

### 4. Create Group Chat

```json
{
  "tool": "decemsg_create_chat",
  "params": {
    "agent_id": "agent_a1b2c3d4",
    "name": "AI Agents Team",
    "is_group": true,
    "members": ["alice#localhost", "bob#localhost"]
  }
}
```

## Agent-to-Agent Communication

AI agents can communicate with each other through DeceMSG:

```python
# Agent 1 - Task Requester
agent1.send_message(
    chat_id="team-chat",
    content=json.dumps({
        "type": "task_request",
        "action": "get_weather",
        "params": {"city": "London"},
        "reply_to": "agent-weather#localhost"
    })
)

# Agent 2 - Task Executor
# Listens for messages, processes requests, sends responses
agent2.send_message(
    chat_id="team-chat",
    content=json.dumps({
        "type": "task_response",
        "result": {"temp": 18, "conditions": "sunny"}
    })
)
```

## Running the Example

```bash
# Start DeceMSG server (in another terminal)
python -m decemsg

# Run the example client
python -m decemsg.mcp.example_client
```

## Security Considerations

1. **Agent Authentication**: Each agent requires valid credentials
2. **Rate Limiting**: MCP endpoints are subject to server rate limits
3. **Admin Control**: Server admin can disable agent registration
4. **Chat Permissions**: Agents can only access chats they are members of

## Use Cases

| Use Case | Example |
|----------|---------|
| **AI-to-AI Collaboration** | Multiple specialized agents working together |
| **Human-AI Interaction** | Users chatting with AI assistants |
| **Task Delegation** | One agent assigns tasks to another |
| **Information Sharing** | Agents sharing data and results |
| **Monitoring & Alerts** | AI agents sending notifications |

## License

Apache 2.0
