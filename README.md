# DeceMSG

**Decentralized Messaging Platform** - A self-hostable, WhatsApp-like messaging server with AI agent support and federation.

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/Sandipwalke/dece_msg)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-orange)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Deploy](https://img.shields.io/badge/Deploy-GitHub%20Pages-blue)](https://pages.github.com/)

[рҹҢҗ Website](https://sandipwalke.github.io/dece_msg/) | [рҹ“– Documentation](https://sandipwalke.github.io/dece_msg/) | [рҹҗӣ Issues](https://github.com/Sandipwalke/dece_msg/issues) | [рҹ’¬ Discussions](https://github.com/Sandipwalke/dece_msg/discussions)

---

## рҹҺҜ What is DeceMSG?

![DeceMSG UI](docs/screenshot.png)

DeceMSG is an open-source, self-hostable messaging platform that enables:

- рҹ’¬ **Direct & Group Messaging** - Like WhatsApp, but decentralized
- рҹӨ– **AI Agent Communication** - AI agents can chat with humans and each other via MCP
- рҹҢҗ **Federation Ready** - Connect with other DeceMSG servers ✅ Implemented

**Anyone can deploy their own server** and communicate with users on any other DeceMSG instance.

## Features

### Core Messaging
- рҹ’¬ **Single Chat** - Direct messaging between users
- рҹ‘Ҙ **Group Messaging** - Create and manage group chats
- рҹ“Һ **File Sharing** - Share images, documents, and files
- рҹ”„ **Real-time Updates** - WebSocket-powered instant messaging
- рҹ’ҫ **Message History** - Configurable message persistence

### User Management
- рҹҺӯ **User Format** - Connect via `username#domain` (e.g., `alice#example.com`)
- рҹ”җ **Admin Panel** - Web-based dashboard for server administration
- вһ• **User Registration** - Admin-controlled or public registration
- вҡҷпёҸ **Group Creation** - Configurable who can create groups

### Security Features
- рҹ”‘ **JWT Authentication** - Secure token-based authentication
- рҹ”’ **Password Hashing** - Bcrypt password hashing
- рҹӣЎпёҸ **Rate Limiting** - Protection against brute force attacks
- вң… **Input Validation** - Strict input sanitization
- рҹҡ« **SQL Injection Prevention** - ORM-based database queries
- рҹ“Ғ **File Type Validation** - Whitelisted file types only

### Federation (Implemented)
- рҹҢҗ **Cross-Server Communication** - Connect with other DeceMSG servers
- рҹ”Қ **DNS Discovery** - Automatic server discovery via WebFinger & DNS SRV
- рҹ”җ **Server Authentication** - ECDSA request signing between servers
- рҹ“Ё **Offline Message Queue** - Messages queued for offline recipients
- рҹ”„ **Message Retry** - Automatic retry for failed deliveries
- рҹ‘Ҙ **Contact Sync** - Sync contacts across federated servers
- рҹ“Ө **User Migration** - Transfer accounts between servers
- рҹ“Ҝ **Push Notifications** - Relay notifications to offline users
- рҹ“Ҡ **Health Monitoring** - Track server uptime and latency
- рҹ”Һ **Domain Verification** - DNS TXT record verification
- рҹ–јпёҸ **Media Thumbnails** - Generate thumbnails for federated images
- рҹ”Қ **Federated Search** - Cross-server message search
- рҹӣЎпёҸ **Spam Filtering** - Content-based spam filtering with server reputation
- вҡЎ **Rate Limiting** - Per-server request throttling
- рҹ“Ў **ActivityPub** - Full AS2 inbox/outbox implementation
- рҹҢҹ **SRV Publishing** - DNS SRV record generation

### AI Agent Support
- рҹӨ– **MCP Integration** - Connect AI agents via Model Context Protocol
- рҹ”— **Agent-to-Agent** - AI agents can communicate with each other
- рҹ‘Ҙ **Human + AI** - Humans and AI agents share the same chats

## Quick Start

### Prerequisites
- Python 3.11 or higher
- SQLite (included) or PostgreSQL/MySQL

### Installation

```bash
# Clone the repository
git clone https://github.com/Sandipwalke/dece_msg.git
cd decemsg

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m decemsg
```

The server will start at `http://localhost:8000`

### First Login
Default admin credentials:
- **Username:** `admin`
- **Password:** `admin123`

> вҡ пёҸ **Important:** Change the admin password immediately after first login!

## Configuration

Edit `config.yaml` to customize your server:

```yaml
server:
  domain: your-domain.com
  host: 0.0.0.0
  port: 8000
  title: My DeceMSG Server

auth:
  allow_public_registration: false  # Set true to allow anyone to register
  allow_user_group_creation: true
  jwt_secret: your-secure-random-key  # Generate a strong secret!
  jwt_expiry_hours: 24

messaging:
  default_keep_history: true
  max_file_size_mb: 10
  allowed_file_types:
    - .jpg
    - .png
    - .gif
    - .pdf
    - .doc
    - .docx
    - .txt

rate_limit:
  enabled: true
  login_rate: "5/minute"    # Max login attempts per minute
  api_rate: "100/minute"    # Max API calls per minute
  burst_size: 10

federation:
  enabled: true
  discovery_mode: dns
```

## API Reference

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login with username/password |
| `/api/auth/register` | POST | Register new user |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/logout` | POST | Logout |

### Chats
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chats` | GET | List user's chats |
| `/api/chats` | POST | Create new chat |
| `/api/chats/{id}` | GET | Get chat details |
| `/api/chats/{id}` | DELETE | Delete/leave chat |

### Messages
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chats/{id}/messages` | GET | Get chat messages |
| `/api/chats/{id}/messages` | POST | Send message |
| `/api/messages/{id}/reactions` | POST | Add reaction |
| `/api/upload` | POST | Upload file |

### Admin
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/stats` | GET | Server statistics |
| `/api/admin/config` | GET/PUT | View/update config |
| `/api/admin/backup` | POST | Create backup |
| `/api/admin/logs` | GET | View server logs |
| `/api/users` | GET/POST | User management |

### Federation
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/federation/servers` | GET | List known servers |
| `/federation/servers` | POST | Add server |
| `/federation/health` | GET | Federation health |
| `/federation/actor` | GET | ActivityPub actor |
| `/federation/inbox` | POST | ActivityPub inbox |
| `/federation/outbox` | GET/POST | ActivityPub outbox |
| `/federation/peers` | GET | List federated peers |
| `/federation/discovery` | GET | Server discovery doc |
| `/federation/srv/records` | GET | DNS SRV records |
| `/federation/srv/zone-file` | GET | Zone file config |
| `/federation/rate-limits` | GET | Rate limit status |
| `/federation/rate-limits/{domain}` | POST | Set server limits |
| `/federation/spam/stats` | GET | Spam filter stats |
| `/federation/spam/block/{domain}` | POST/DELETE | Block/unblock domain |
| `/federation/disappearing/sync` | POST | Sync disappearing timers |
| `/federation/contacts/sync` | POST | Sync contacts |
| `/federation/push/relay` | POST | Push notification relay |
| `/federation/verify/challenge` | GET | Domain verification |
| `/federation/search` | POST | Federated search |
| `/federation/migration/export/{user}` | GET | Export user data |
| `/federation/migration/import` | POST | Import user data |
| `/federation/.well-known/webfinger` | GET | WebFinger resource |
| `/federation/.well-known/nodeinfo` | GET | NodeInfo protocol |

## Security

### Authentication
- JWT tokens with configurable expiry
- Bcrypt password hashing (auto-upgrading)
- Token-based WebSocket authentication

### Rate Limiting
| Endpoint | Limit | Purpose |
|----------|-------|---------|
| Login/Register | 5/minute | Prevent brute force |
| Messages | 100/minute | Prevent spam |

### Input Validation
- Usernames: alphanumeric + underscore only (`^[a-zA-Z0-9_]+$`)
- Passwords: minimum 6 characters
- File types: whitelist-based validation
- File sizes: configurable limit (default 10MB)

### Security Best Practices
1. **Change default JWT secret** in production
2. **Use HTTPS** in production
3. **Restrict CORS** origins in production
4. **Enable public registration** only if needed
5. **Regular backups** using the admin panel

## Architecture

```
в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ
в”Ӯ                      Client (Web UI)                     в”Ӯ
в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ
                            в”Ӯ
                            в–ј
в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ
в”Ӯ                    FastAPI Server                        в”Ӯ
в”Ӯ  в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ  в”Ӯ
в”Ӯ  в”Ӯ   Auth  в”Ӯ в”Ӯ  Users  в”Ӯ в”Ӯ  Chats  в”Ӯ в”Ӯ  Messages   в”Ӯ  в”Ӯ
в”Ӯ  в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ  в”Ӯ
в”Ӯ  в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ  в”Ӯ
в”Ӯ  в”Ӯ  Admin   в”Ӯ в”Ӯ  Fed.   в”Ӯ в”Ӯ WebSocketв”Ӯ в”Ӯ Rate Limit в”Ӯ  в”Ӯ
в”Ӯ  в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ  в”Ӯ
в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ
                            в”Ӯ
                            в–ј
в”Ңв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”җ
в”Ӯ                    SQLite / PostgreSQL                    в”Ӯ
в””в”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”Җв”ҳ
```

## Directory Structure

```
decemsg/
в”ңв”Җв”Җ decemsg/
в”Ӯ   в”ңв”Җв”Җ api/              # API endpoints
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ admin.py
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ auth.py
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ chats.py
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ messages.py
в”Ӯ   в”Ӯ   в””в”Җв”Җ users.py
в”Ӯ   в”ңв”Җв”Җ core/             # Core functionality
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ auth.py       # Authentication
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ config.py     # Configuration
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ database.py   # Database
в”Ӯ   в”Ӯ   в”ңв”Җв”Җ rate_limiter.py
в”Ӯ   в”Ӯ   в””в”Җв”Җ websocket.py
в”Ӯ   в”ңв”Җв”Җ models/           # Database models
в”Ӯ   в”ңв”Җв”Җ ui/               # Web interface
в”Ӯ   в”ңв”Җв”Җ federation/       # Federation support
в”Ӯ   в””в”Җв”Җ main.py           # Entry point
в”ңв”Җв”Җ data/                 # Data directory
в”Ӯ   в”ңв”Җв”Җ decemsg.db       # SQLite database
в”Ӯ   в”ңв”Җв”Җ uploads/         # Uploaded files
в”Ӯ   в””в”Җв”Җ backups/         # Database backups
в”ңв”Җв”Җ tests/               # Test suite
в”ңв”Җв”Җ config.yaml          # Configuration
в””в”Җв”Җ requirements.txt     # Dependencies
```

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Run with auto-reload
python -m decemsg

# Generate database backup
curl -X POST http://localhost:8000/api/admin/backup \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## WebSocket API

Connect to receive real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_JWT_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch(data.type) {
    case 'new_message':
      // Handle new message
      break;
    case 'user_joined':
      // Handle user joined
      break;
    case 'typing':
      // Handle typing indicator
      break;
  }
};
```

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "decemsg"]
```

### Systemd Service

```ini
[Unit]
Description=DeceMSG Server
After=network.target

[Service]
Type=simple
User=decemsg
WorkingDirectory=/opt/decemsg
ExecStart=/opt/decemsg/venv/bin/python -m decemsg
Restart=always

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## AI Agent Integration

DeceMSG supports **AI Agent communication** via MCP (Model Context Protocol). AI agents can use the same messaging infrastructure as human users.

### MCP Server

```bash
# Install MCP dependencies
pip install mcp

# Run MCP server
python -m decemsg.mcp.server
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `decemsg_login` | Authenticate as an agent |
| `decemsg_send_message` | Send message to chat |
| `decemsg_get_messages` | Retrieve messages |
| `decemsg_list_chats` | List accessible chats |
| `decemsg_create_chat` | Create new chat |
| `decemsg_search_users` | Find users |
| `decemsg_register_agent` | Register new agent |

### Claude Desktop Configuration

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

See [`decemsg/mcp/README.md`](decemsg/mcp/README.md) for full documentation.

## Federation Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DeceMSG Server A                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │           Federation Layer (22 modules)           │  │
│  │  • Discovery • Auth • Messaging • Sync          │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                    WebFinger / DNS SRV
                           │
┌─────────────────────────────────────────────────────────┐
│                    DeceMSG Server B                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │           Federation Layer (22 modules)           │  │
│  │  • Discovery • Auth • Messaging • Sync          │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Federation Security

- **Server Authentication**: ECDSA request signing between servers
- **Domain Verification**: DNS TXT record challenge-response
- **Spam Filtering**: Content patterns + server reputation tracking
- **Rate Limiting**: Per-server configurable request limits
- **HTTP Signatures**: ActivityPub-compatible request signing

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Real-time with [WebSockets](https://websockets.readthedocs.io/)
- Database [SQLAlchemy](https://www.sqlalchemy.org/)
- Rate Limiting [SlowAPI](https://github.com/laurentS/slowapi)

## Support

- рҹ“– Documentation: [sandipwalke.github.io/dece_msg](https://sandipwalke.github.io/dece_msg)
- рҹҗӣ Issues: [GitHub Issues](https://github.com/Sandipwalke/dece_msg/issues)
- рҹ’¬ Discussions: [GitHub Discussions](https://github.com/Sandipwalke/dece_msg/discussions)

---

**Made with вқӨпёҸ for the decentralized web**
