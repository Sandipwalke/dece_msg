"""DeceMSG deployment module."""
import os
import secrets
import sys
from pathlib import Path

import yaml
import uvicorn

from decemsg.core.database import init_db, get_session_factory
from decemsg.core.config import get_config
from decemsg.core.auth import get_password_hash
from decemsg.models.user import User


def create_config(domain: str = "localhost", port: int = 8000):
    """Create initial configuration file."""
    config_path = Path("config.yaml")
    
    if config_path.exists():
        print(f"Configuration file already exists at {config_path}")
        return
    
    # Generate a secure JWT secret
    jwt_secret = secrets.token_urlsafe(32)
    
    config = {
        "server": {
            "domain": domain,
            "host": "0.0.0.0",
            "port": port,
            "title": "DeceMSG Server"
        },
        "database": {
            "type": "sqlite",
            "path": "./data/decemsg.db"
        },
        "auth": {
            "allow_public_registration": False,
            "allow_user_group_creation": True,
            "jwt_secret": jwt_secret,
            "jwt_expiry_hours": 24
        },
        "messaging": {
            "default_keep_history": True,
            "max_file_size_mb": 10,
            "allowed_file_types": [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx", ".txt"]
        },
        "federation": {
            "enabled": True,
            "discovery_mode": "dns"
        }
    }
    
    # Ensure data directory exists
    Path("./data").mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"✅ Configuration created at {config_path}")


def create_admin_user(username: str, display_name: str, password: str):
    """Create the initial admin user."""
    config = get_config()
    
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    
    async def _create_user():
        session_factory = get_session_factory()
        async with session_factory() as db:
            # Check if admin already exists
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.username == username)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"User '{username}' already exists")
                return existing
            
            # Create admin user
            user = User(
                username=username,
                display_name=display_name,
                password_hash=get_password_hash(password),
                domain=config.server.domain,
                is_admin=True,
            )
            
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            print(f"✅ Admin user created: {username}")
            return user
    
    return asyncio.run(_create_user())


async def init_database():
    """Initialize the database and create tables."""
    await init_db()
    print("✅ Database initialized")


def deploy(
    domain: str = "localhost",
    port: int = 8000,
    admin_username: str = "admin",
    admin_password: str = None,
    admin_display_name: str = "Administrator",
    skip_admin: bool = False
):
    """Deploy the DeceMSG server."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    DeceMSG Deployment                        ║
║           Decentralized Messaging Platform                    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Step 1: Create configuration
    print("\n📝 Step 1: Creating configuration...")
    create_config(domain=domain, port=port)
    
    # Step 2: Initialize database
    print("\n📊 Step 2: Initializing database...")
    import asyncio
    asyncio.run(init_database())
    
    # Step 3: Create admin user
    if not skip_admin:
        print("\n👤 Step 3: Creating admin user...")
        password = admin_password or secrets.token_urlsafe(12)
        create_admin_user(
            username=admin_username,
            display_name=admin_display_name,
            password=password
        )
        print(f"\n🔐 Admin credentials:")
        print(f"   Username: {admin_username}")
        print(f"   Password: {password}")
        print("\n⚠️  Please change this password after first login!")
    
    # Step 4: Start server
    print("\n🚀 Step 4: Starting server...")
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    Server Ready!                             ║
╠══════════════════════════════════════════════════════════════╣
║  API:        http://localhost:{port}                            ║
║  WebSocket:  ws://localhost:{port}/ws                          ║
║  Admin UI:   http://localhost:{port}/admin                      ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Start uvicorn server
    uvicorn.run(
        "decemsg.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


def run_server():
    """Run the server with existing configuration."""
    import asyncio
    from decemsg.core.config import get_config
    
    config = get_config()
    
    print(f"Starting DeceMSG Server on port {config.server.port}...")
    
    uvicorn.run(
        "decemsg.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    deploy()
