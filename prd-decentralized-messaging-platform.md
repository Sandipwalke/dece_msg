# PRD: Decentralized Messaging Platform (DeceMSG)

## 1. Introduction/Overview

A federated, self-hosted messaging platform inspired by WhatsApp that enables cross-server communication. Users identify each other by `username#domain` format (e.g., `alice#example.com`), allowing seamless messaging across independent servers like email works.

**Core Philosophy:** Anyone can deploy their own server, control their domain, and communicate with users on other federated servers without dependence on a single provider.

---

## 2. Architecture Overview

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        SERVER A (example.com)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Admin UI  │  │  Python API  │  │   SQLite/PostgreSQL   │  │
│  │  (Flet/Reflex) │  │  (FastAPI)  │  │      Database         │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    WebSocket + REST API
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SERVER B (chat.org)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Admin UI  │  │  Python API  │  │   SQLite/PostgreSQL   │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend | Python + FastAPI | High performance, easy deployment |
| Real-time | WebSockets | Live messaging, presence |
| Database | SQLite (default) / PostgreSQL | Single-file deploy, scalable option |
| User Interface | Reflex (Python-React framework) | Bundled Python UI, WhatsApp-like experience |
| File Storage | Local filesystem (default) | Simple deployment |
| Authentication | JWT tokens | Stateless, works across federated servers |

### 2.3 Federated Communication Protocol

**Discovery:** Servers discover each other through shared server registry or direct `.well-known/messaging` endpoints.

**Message Routing:**
- `user#domain` → Resolve domain → Find server → Deliver message
- Cross-server messages authenticated via shared secrets or certificate verification

---

## 3. Goals

- **G1:** Enable users to communicate across independent servers using `username#domain` addressing
- **G2:** Provide WhatsApp-like chat experience (conversations list, chat view, online status)
- **G3:** Allow single-click server deployment for non-technical users
- **G4:** Give server administrators full control over their domain (users, permissions, configuration)
- **G5:** Support both single-user chats and group conversations
- **G6:** Store message history with per-chat configurable persistence

---

## 4. User Stories

### 4.1 Authentication & User Management

#### US-001: Server Registration
**Description:** As a server owner, I want to set up my messaging server with a single command so I can quickly deploy my domain.

**Acceptance Criteria:**
- [ ] `python -m decemsg deploy` creates running server
- [ ] Admin account created during setup (username/password)
- [ ] Server accessible at `http://localhost:8000` by default
- [ ] Configuration file generated for customization

---

#### US-002: User Registration (Admin-Created)
**Description:** As an admin, I want to create user accounts so I can manage who joins my server.

**Acceptance Criteria:**
- [ ] Admin can create users with username, display name, password
- [ ] User receives initial credentials
- [ ] Admin can deactivate/delete users
- [ ] User address format: `username#domain.com`

---

#### US-003: User Registration (Self-Registration Toggle)
**Description:** As an admin, I want to toggle whether anyone can register or only admins can create users.

**Acceptance Criteria:**
- [ ] Admin panel has "Allow Public Registration" toggle
- [ ] When enabled, `/register` page available to anyone
- [ ] When disabled, only admin can create users
- [ ] Setting persists across server restarts

---

#### US-004: User Login
**Description:** As a user, I want to log in with my credentials so I can access my conversations.

**Acceptance Criteria:**
- [ ] Login page with username and password fields
- [ ] JWT token issued on successful login
- [ ] Token stored in local storage for session persistence
- [ ] Logout clears token and redirects to login

---

### 4.2 Messaging Features

#### US-005: Send Direct Message
**Description:** As a user, I want to send a message to another user by their `username#domain` so I can communicate with anyone in the federation.

**Acceptance Criteria:**
- [ ] Search/enter recipient as `user#domain`
- [ ] Message delivered in real-time via WebSocket
- [ ] Message appears in both sender's and recipient's chat
- [ ] Timestamp shown for each message
- [ ] Message persists if chat has history enabled

---

#### US-006: Receive Real-time Messages
**Description:** As a user, I want to receive messages instantly without refreshing so communication feels natural.

**Acceptance Criteria:**
- [ ] Messages appear within 1 second of being sent
- [ ] Notification badge shows unread count on chat list
- [ ] "Online" indicator for active recipients
- [ ] Graceful handling when recipient is offline (queued delivery)

---

#### US-007: Message Reactions
**Description:** As a user, I want to react to messages with emojis so I can respond quickly without typing.

**Acceptance Criteria:**
- [ ] Long-press or hover reveals reaction button
- [ ] Reaction picker shows common emojis (👍 ❤️ 😂 😮 😢 🎉)
- [ ] Multiple reactions per message allowed
- [ ] Reactions visible below message with user count
- [ ] Users can add/remove their reaction

---

#### US-008: File Sharing
**Description:** As a user, I want to share images and documents so I can exchange files in chat.

**Acceptance Criteria:**
- [ ] Attachment button in message input
- [ ] Support for images (jpg, png, gif) with preview
- [ ] Support for documents (pdf, doc, txt) with icon preview
- [ ] Max file size: 10MB (configurable by admin)
- [ ] Files downloadable by recipient

---

#### US-009: Message History Toggle
**Description:** As a user, I want to configure whether messages persist in a chat so I can control my privacy/storage.

**Acceptance Criteria:**
- [ ] Per-chat setting: "Keep History" toggle
- [ ] New chats default based on server setting
- [ ] Ephemeral messages deleted from server after 24 hours
- [ ] History status visible in chat info

---

### 4.3 Group Messaging

#### US-010: Create Group Chat
**Description:** As a user, I want to create group conversations so I can chat with multiple people.

**Acceptance Criteria:**
- [ ] "New Group" option in chat list
- [ ] Select participants from contacts or enter `user#domain`
- [ ] Set group name and optional avatar
- [ ] Creator becomes group admin

---

#### US-011: Group Management (Admin-Controlled)
**Description:** As a server admin, I want to control whether users can create groups or if it's admin-only.

**Acceptance Criteria:**
- [ ] Server setting: "Users Can Create Groups" toggle
- [ ] When disabled, only admins can create groups
- [ ] Existing groups remain but no new ones can be created by users
- [ ] Setting change affects future group creation only

---

#### US-012: Group Administration
**Description:** As a group admin, I want to manage members and group settings.

**Acceptance Criteria:**
- [ ] Add/remove members (by `user#domain`)
- [ ] Change group name and avatar
- [ ] Transfer admin role to another member
- [ ] Delete group (removes for all members)

---

### 4.4 Admin Panel

#### US-013: Server Configuration
**Description:** As an admin, I want to configure my server settings from a dashboard.

**Acceptance Criteria:**
- [ ] Web-based admin panel at `/admin`
- [ ] Settings grouped logically (General, Users, Security, Federation)
- [ ] Changes saved with one click
- [ ] Server restarts automatically after config change

---

#### US-014: User Management Dashboard
**Description:** As an admin, I want to see and manage all users on my server.

**Acceptance Criteria:**
- [ ] List of all users with status (online/offline/active)
- [ ] Search and filter users
- [ ] Actions: Create, Edit, Deactivate, Delete
- [ ] View user's conversation list (admin only)

---

#### US-015: Server Statistics
**Description:** As an admin, I want to see server usage stats so I can monitor health.

**Acceptance Criteria:**
- [ ] Active users count (24h, 7d, 30d)
- [ ] Message count statistics
- [ ] Storage usage
- [ ] Uptime and system health

---

### 4.5 Federation

#### US-016: Cross-Server Messaging
**Description:** As a user, I want to message anyone on any federated server.

**Acceptance Criteria:**
- [ ] Send to `user#external-domain.com` seamlessly
- [ ] Server discovers external domain via DNS or registry
- [ ] Messages routed through both servers
- [ ] Works transparently like local messaging

---

## 5. Functional Requirements

### 5.1 Core Backend (FastAPI)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | REST API for user CRUD operations | P0 |
| FR-2 | REST API for chat/group management | P0 |
| FR-3 | WebSocket endpoint for real-time messaging | P0 |
| FR-4 | JWT-based authentication middleware | P0 |
| FR-5 | File upload/download endpoints | P0 |
| FR-6 | Cross-server federation protocol endpoints | P0 |
| FR-7 | Admin configuration endpoints | P0 |
| FR-8 | Message search endpoint | P1 |
| FR-9 | Server discovery endpoint (`.well-known`) | P1 |

### 5.2 Frontend (Reflex/Python)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-10 | Login/Register pages | P0 |
| FR-11 | Chat list sidebar (WhatsApp-style) | P0 |
| FR-12 | Chat view with message bubbles | P0 |
| FR-13 | Message input with attachment support | P0 |
| FR-14 | User search by `user#domain` | P0 |
| FR-15 | Group creation and management UI | P0 |
| FR-16 | Message reactions UI | P0 |
| FR-17 | Admin panel dashboard | P0 |
| FR-18 | Admin user management UI | P0 |
| FR-19 | Admin server settings UI | P0 |
| FR-20 | Online/offline presence indicators | P1 |
| FR-21 | Unread message badges | P1 |
| FR-22 | Message timestamps and read receipts | P1 |

### 5.3 Database Schema

```
Users
├── id (UUID, PK)
├── username (string, unique)
├── display_name (string)
├── password_hash (string)
├── domain (string)
├── created_at (datetime)
├── last_seen (datetime)
├── is_admin (boolean)
└── is_active (boolean)

Chats
├── id (UUID, PK)
├── type (enum: direct, group)
├── name (string, nullable for direct)
├── avatar_url (string, nullable)
├── created_at (datetime)
├── created_by (FK → Users)
├── keep_history (boolean, default: true)
└── server_setting (FK → ServerConfig)

ChatMembers
├── chat_id (FK → Chats)
├── user_id (FK → Users)
├── role (enum: member, admin)
├── joined_at (datetime)
└── last_read_message (FK → Messages)

Messages
├── id (UUID, PK)
├── chat_id (FK → Chats)
├── sender_id (FK → Users)
├── content (text)
├── message_type (enum: text, image, file)
├── file_url (string, nullable)
├── created_at (datetime)
├── expires_at (datetime, nullable)
└── is_deleted (boolean)

MessageReactions
├── id (UUID, PK)
├── message_id (FK → Messages)
├── user_id (FK → Users)
├── emoji (string)
└── created_at (datetime)

ServerConfig
├── domain (string, PK)
├── allow_public_registration (boolean)
├── allow_user_group_creation (boolean)
├── default_keep_history (boolean)
├── max_file_size_mb (integer)
├── federation_enabled (boolean)
└── shared_secret (string, for cross-server auth)
```

### 5.4 API Endpoints

#### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration (if enabled)
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user

#### Users
- `GET /api/users` - List users (admin)
- `POST /api/users` - Create user (admin)
- `GET /api/users/{id}` - Get user details
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Deactivate user (admin)

#### Chats
- `GET /api/chats` - List user's chats
- `POST /api/chats` - Create chat (direct or group)
- `GET /api/chats/{id}` - Get chat details
- `PUT /api/chats/{id}` - Update chat
- `DELETE /api/chats/{id}` - Delete chat
- `POST /api/chats/{id}/members` - Add member
- `DELETE /api/chats/{id}/members/{user_id}` - Remove member

#### Messages
- `GET /api/chats/{id}/messages` - Get messages (paginated)
- `POST /api/chats/{id}/messages` - Send message
- `POST /api/messages/{id}/reactions` - Add reaction
- `DELETE /api/messages/{id}/reactions/{emoji}` - Remove reaction

#### Files
- `POST /api/upload` - Upload file
- `GET /api/files/{id}` - Download file

#### Admin
- `GET /api/admin/stats` - Server statistics
- `GET /api/admin/config` - Get server config
- `PUT /api/admin/config` - Update server config

#### Federation
- `GET /.well-known/messaging` - Server info for federation
- `POST /api/federation/messages` - Receive cross-server message
- `GET /api/federation/users/{domain}` - Discover users on domain

#### WebSocket
- `WS /ws/{token}` - Real-time messaging connection

---

## 6. Non-Goals (Out of Scope)

- **Voice/Video Calls:** Out of scope for v1; can be added later via WebRTC
- **End-to-End Encryption:** Planned for v2; v1 uses server-side encryption at rest
- **Message Editing/Deletion:** "Delete for everyone" feature not in v1
- **Typing Indicators:** Nice-to-have, not essential
- **Channel Broadcasting:** One-to-many announcements not in scope
- **Multi-Device Sync:** Single session per user in v1
- **Server-to-Server Federation Discovery Registry:** V1 assumes direct DNS lookup or manual configuration
- **Mobile Apps:** Web-based PWA only for v1
- **Email Integration:** No email notifications in v1

---

## 7. Design Considerations

### 7.1 WhatsApp-Inspired UI

**Color Palette:**
| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Primary | `#128C7E` (Teal) | `#00D9A5` |
| Secondary | `#25D366` (Green) | `#25D366` |
| Background | `#FFFFFF` | `#111B21` |
| Chat Bubble (Sent) | `#DCF8C6` | `#005C4B` |
| Chat Bubble (Received) | `#FFFFFF` | `#1F2C34` |
| Text Primary | `#111B21` | `#E9EDEF` |
| Text Secondary | `#667781` | `#8696A0` |

**Typography:**
- Font: System fonts (San Francisco, Segoe UI, Roboto)
- Headings: 16-20px semibold
- Body: 14-15px regular
- Captions: 12px regular

**Layout (Desktop):**
```
┌────────────────────────────────────────────────────────┐
│ ┌──────────┬───────────────────────────────────────┐  │
│ │          │  Chat Header                           │  │
│ │  Chat    │  ─────────────────────────────────────│  │
│ │  List    │                                        │  │
│ │          │  Message Area                          │  │
│ │  280px   │  (scrollable)                          │  │
│ │          │                                        │  │
│ │          │  ─────────────────────────────────────│  │
│ │          │  Input Area                           │  │
│ └──────────┴───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

**Layout (Mobile):**
- Single column, chat list → chat view navigation
- Bottom navigation bar: Chats, Status, Settings

### 7.2 Admin Panel Design

- Clean, form-based configuration
- Toggle switches for boolean settings
- Tables for user management with action buttons
- Server stats as cards with icons

---

## 8. Technical Considerations

### 8.1 Deployment

**Single-Command Setup:**
```bash
# Option 1: pip install
pip install decemsg
python -m decemsg deploy

# Option 2: Docker
docker run -p 8000:8000 decemsg/deploy
```

**Configuration File (`config.yaml`):**
```yaml
server:
  domain: "example.com"
  host: "0.0.0.0"
  port: 8000
  
database:
  type: "sqlite"  # or "postgresql"
  path: "./data/decemsg.db"

auth:
  allow_public_registration: false
  allow_user_group_creation: true
  jwt_secret: "change-me-in-production"
  jwt_expiry_hours: 24

messaging:
  default_keep_history: true
  max_file_size_mb: 10
  allowed_file_types:
    - ".jpg"
    - ".png"
    - ".gif"
    - ".pdf"
    - ".doc"
    - ".docx"
    - ".txt"

federation:
  enabled: true
  discovery_mode: "dns"  # or "registry"
```

### 8.2 Performance Targets

| Metric | Target |
|--------|--------|
| Message delivery (same server) | < 100ms |
| Message delivery (cross-server) | < 2s |
| Chat list load time | < 500ms |
| File upload (10MB) | < 5s |
| Concurrent WebSocket connections | 1000+ |

### 8.3 Security

- Passwords hashed with bcrypt (cost factor 12)
- JWT tokens signed with HS256
- File uploads validated and virus-scanned (optional)
- Rate limiting on auth endpoints
- CORS configured for same-origin only
- Admin endpoints require admin JWT

### 8.4 Database Migrations

- Use Alembic for schema migrations
- Auto-run migrations on startup
- Backup before migration

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Server startup time | < 30 seconds | Fresh install benchmark |
| Cross-server message success rate | > 99% | Automated federation tests |
| Concurrent users per server | 500+ | Load test |
| Message delivery latency (P95) | < 500ms | APM metrics |
| User registration completion rate | > 90% | Analytics |
| Admin task completion (create user) | < 5 seconds | UI interaction |

---

## 10. Open Questions

| Question | Options | Recommendation |
|----------|---------|----------------|
| Database for default deploy? | SQLite / PostgreSQL | SQLite default, PostgreSQL as option |
| How do servers discover each other? | DNS lookup / Central registry | DNS via SRV records |
| File storage location? | Local filesystem / S3-compatible | Local by default |
| Default admin password? | Random / Set during setup | Random, shown once |
| SSL/TLS handling? | Built-in / External proxy | Built-in with Let's Encrypt option |
| Logs location? | File / Stdout / Syslog | File + configurable |
| Backup mechanism? | Manual / Scheduled | Manual export in v1 |
| Update mechanism? | pip update / In-app | pip update |

---

## 11. Project Structure

```
decemsg/
├── decemsg/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── deploy.py            # Deployment command
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py          # Auth endpoints
│   │   ├── users.py         # User CRUD
│   │   ├── chats.py         # Chat management
│   │   ├── messages.py      # Messaging
│   │   ├── files.py         # File handling
│   │   ├── admin.py         # Admin endpoints
│   │   └── federation.py    # Cross-server
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── chat.py
│   │   ├── message.py
│   │   └── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── websocket.py
│   │   └── config.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── pages/
│   │   │   ├── login.py
│   │   │   ├── chat.py
│   │   │   ├── group.py
│   │   │   └── admin.py
│   │   └── components/
│   │       ├── chat_list.py
│   │       ├── message_bubble.py
│   │       └── ...
│   └── utils/
│       ├── __init__.py
│       └── federation.py
├── tests/
│   ├── test_auth.py
│   ├── test_messages.py
│   ├── test_federation.py
│   └── test_ui.py
├── config.example.yaml
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 12. Development Phases

### Phase 1: Foundation (MVP)
- User auth (login, register, JWT)
- Direct messaging (send, receive, history)
- Basic UI (chat list, chat view)
- Admin user management
- SQLite database

### Phase 2: Enhanced Messaging
- File sharing (images, documents)
- Message reactions
- Group chats
- Online status

### Phase 3: Admin & Configuration
- Full admin panel
- Server configuration
- Server statistics

### Phase 4: Federation
- Cross-server discovery
- Inter-server messaging
- Federation security

### Phase 5: Polish
- Dark mode
- Mobile responsiveness
- Performance optimization
- Documentation

---

*Document Version: 1.0*
*Created: 2026-08-05*
