# DeceMSG

**Decentralized Messaging Platform** - A self-hostable, WhatsApp-like messaging server with federation support.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-orange)

## Features

### Core Messaging
- 💬 **Single Chat** - Direct messaging between users
- 👥 **Group Messaging** - Create and manage group chats
- 📎 **File Sharing** - Share images, documents, and files
- 🔄 **Real-time Updates** - WebSocket-powered instant messaging
- 💾 **Message History** - Configurable message persistence

### User Management
- 🎭 **User Format** - Connect via `username#domain` (e.g., `alice#example.com`)
- 🔐 **Admin Panel** - Web-based dashboard for server administration
- ➕ **User Registration** - Admin-controlled or public registration
- ⚙️ **Group Creation** - Configurable who can create groups

### Security Features
- 🔑 **JWT Authentication** - Secure token-based authentication
- 🔒 **Password Hashing** - Bcrypt password hashing
- 🛡️ **Rate Limiting** - Protection against brute force attacks
- ✅ **Input Validation** - Strict input sanitization
- 🚫 **SQL Injection Prevention** - ORM-based database queries
- 📁 **File Type Validation** - Whitelisted file types only

### Federation (Planned)
- 🌐 **Cross-Server Communication** - Connect with other DeceMSG servers
- 🔍 **DNS Discovery** - Automatic server discovery

## Quick Start

### Prerequisites
- Python 3.11 or higher
- SQLite (included) or PostgreSQL/MySQL

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/decemsg.git
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

> ⚠️ **Important:** Change the admin password immediately after first login!

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
┌─────────────────────────────────────────────────────────┐
│                      Client (Web UI)                     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Server                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│  │   Auth  │ │  Users  │ │  Chats  │ │  Messages   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│  │  Admin   │ │  Fed.   │ │ WebSocket│ │ Rate Limit │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    SQLite / PostgreSQL                    │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
decemsg/
├── decemsg/
│   ├── api/              # API endpoints
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── chats.py
│   │   ├── messages.py
│   │   └── users.py
│   ├── core/             # Core functionality
│   │   ├── auth.py       # Authentication
│   │   ├── config.py     # Configuration
│   │   ├── database.py   # Database
│   │   ├── rate_limiter.py
│   │   └── websocket.py
│   ├── models/           # Database models
│   ├── ui/               # Web interface
│   ├── federation/       # Federation support
│   └── main.py           # Entry point
├── data/                 # Data directory
│   ├── decemsg.db       # SQLite database
│   ├── uploads/         # Uploaded files
│   └── backups/         # Database backups
├── tests/               # Test suite
├── config.yaml          # Configuration
└── requirements.txt     # Dependencies
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

- 📖 Documentation: [docs.example.com](https://docs.example.com)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/decemsg/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/decemsg/discussions)

---

**Made with ❤️ for the decentralized web**
