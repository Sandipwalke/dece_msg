#!/usr/bin/env python3
"""Test federation between two DeceMSG servers."""
import asyncio
import httpx
import sys
import os
import time
import subprocess
import signal

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL_1 = "http://localhost:8000"
BASE_URL_2 = "http://localhost:8001"

async def wait_for_server(url, timeout=30):
    """Wait for server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{url}/health", timeout=2)
                if resp.status_code == 200:
                    return True
        except:
            pass
        await asyncio.sleep(0.5)
    return False

async def test_user_registration():
    """Test user registration on both servers."""
    print("\n=== Test 1: User Registration ===")
    
    async with httpx.AsyncClient() as client:
        # Register alice on server 1
        resp = await client.post(f"{BASE_URL_1}/api/auth/register", json={
            "username": "alice",
            "display_name": "Alice",
            "password": "password123"
        })
        print(f"Server 1 - Register alice: {resp.status_code}")
        if resp.status_code not in [200, 201]:
            print(f"  Error: {resp.text}")
            return None
        alice_data = resp.json()
        
        # Login alice on server 1
        resp = await client.post(f"{BASE_URL_1}/api/auth/login", json={
            "username": "alice",
            "password": "password123"
        })
        alice_token = resp.json().get("access_token")
        print(f"Server 1 - Login alice: {resp.status_code}, token: {alice_token[:20]}...")
        
        # Register bob on server 2
        resp = await client.post(f"{BASE_URL_2}/api/auth/register", json={
            "username": "bob",
            "display_name": "Bob",
            "password": "password456"
        })
        print(f"Server 2 - Register bob: {resp.status_code}")
        if resp.status_code not in [200, 201]:
            print(f"  Error: {resp.text}")
            return None
        
        # Login bob on server 2
        resp = await client.post(f"{BASE_URL_2}/api/auth/login", json={
            "username": "bob",
            "password": "password456"
        })
        bob_token = resp.json().get("access_token")
        print(f"Server 2 - Login bob: {resp.status_code}, token: {bob_token[:20]}...")
        
        return alice_token, bob_token

async def test_user_search():
    """Test searching for users including federated ones."""
    print("\n=== Test 2: User Search ===")
    
    async with httpx.AsyncClient() as client:
        # Alice searches for bob on server2
        resp = await client.get(
            f"{BASE_URL_1}/api/users/search",
            params={"q": "bob"},
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        print(f"Alice searches 'bob': {resp.status_code}")
        print(f"  Results: {resp.json()}")
        
        # Alice searches for federated user
        resp = await client.get(
            f"{BASE_URL_1}/api/users/search",
            params={"q": "bob#server2.local"},
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        print(f"Alice searches 'bob#server2.local': {resp.status_code}")
        print(f"  Results: {resp.json()}")

async def test_create_federated_chat():
    """Test creating a chat with a federated user."""
    print("\n=== Test 3: Create Federated Chat ===")
    
    async with httpx.AsyncClient() as client:
        # Discover server2 from server1
        resp = await client.post(
            f"{BASE_URL_1}/federation/servers/discover",
            params={"domain": "server2.local"}
        )
        print(f"Discover server2.local: {resp.status_code}")
        print(f"  Response: {resp.json()}")
        
        # Alice looks up bob on server2
        resp = await client.get(
            f"{BASE_URL_1}/federation/lookup/bob@server2.local"
        )
        print(f"Lookup bob@server2.local: {resp.status_code}")
        print(f"  Response: {resp.json()}")

async def test_send_federated_message():
    """Test sending a message to a federated user."""
    print("\n=== Test 4: Send Federated Message ===")
    
    async with httpx.AsyncClient() as client:
        # Create chat with federated user
        resp = await client.post(
            f"{BASE_URL_1}/api/chats",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "type": "direct",
                "member_ids": ["bob#server2.local"]
            }
        )
        print(f"Create chat with bob#server2.local: {resp.status_code}")
        if resp.status_code in [200, 201]:
            chat_data = resp.json()
            chat_id = chat_data.get("id")
            print(f"  Chat created: {chat_id}")
            
            # Send message
            resp = await client.post(
                f"{BASE_URL_1}/api/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {alice_token}"},
                json={
                    "content": "Hello Bob from Alice!",
                    "message_type": "text"
                }
            )
            print(f"Send message: {resp.status_code}")
            print(f"  Response: {resp.json()}")
            
            # Get messages on server1
            resp = await client.get(
                f"{BASE_URL_1}/api/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {alice_token}"}
            )
            print(f"Get messages on server1: {resp.status_code}")
            print(f"  Messages: {resp.json()}")

async def main():
    global alice_token
    alice_token = None
    
    print("=" * 50)
    print("DeceMSG Federation E2E Test")
    print("=" * 50)
    
    # Check if servers are running
    print("\nChecking servers...")
    server1_ready = await wait_for_server(BASE_URL_1)
    server2_ready = await wait_for_server(BASE_URL_2)
    
    if not server1_ready:
        print(f"Server 1 not ready at {BASE_URL_1}")
        return 1
    if not server2_ready:
        print(f"Server 2 not ready at {BASE_URL_2}")
        return 1
    
    print("Both servers are ready!")
    
    # Run tests
    tokens = await test_user_registration()
    if not tokens:
        print("Failed at user registration")
        return 1
    
    global alice_token, bob_token
    alice_token, bob_token = tokens
    
    await test_user_search()
    await test_create_federated_chat()
    await test_send_federated_message()
    
    print("\n" + "=" * 50)
    print("Tests completed!")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
