"""File/media federation for DeceMSG.

This module provides:
- File proxying for federated users
- File metadata exchange
- Secure file URLs with authentication
"""
import hashlib
import os
import time
import base64
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from decemsg.core.config import get_config
from decemsg.federation.server_auth import create_authenticated_request


@dataclass
class FederatedFile:
    """Metadata for a file shared via federation."""
    file_id: str
    original_url: str
    filename: str
    mime_type: str
    size: int
    checksum: str
    uploaded_by: str
    uploaded_at: datetime
    expires_at: Optional[datetime] = None


class FileProxyCache:
    """Cache for proxied files from federated servers."""
    
    def __init__(self, cache_dir: str = "./data/federated_files"):
        self._cache_dir = cache_dir
        self._metadata: Dict[str, FederatedFile] = {}
        os.makedirs(cache_dir, exist_ok=True)
    
    def add_file(self, file: FederatedFile, local_path: str):
        """Add a proxied file to the cache."""
        self._metadata[file.file_id] = file
        
        # Save metadata
        import json
        meta_file = os.path.join(self._cache_dir, f"{file.file_id}.meta.json")
        with open(meta_file, 'w') as f:
            json.dump({
                "file_id": file.file_id,
                "original_url": file.original_url,
                "filename": file.filename,
                "mime_type": file.mime_type,
                "size": file.size,
                "checksum": file.checksum,
                "uploaded_by": file.uploaded_by,
                "uploaded_at": file.uploaded_at.isoformat(),
                "expires_at": file.expires_at.isoformat() if file.expires_at else None,
                "local_path": local_path
            }, f)
    
    def get_file(self, file_id: str) -> Optional[FederatedFile]:
        """Get file metadata from cache."""
        if file_id in self._metadata:
            return self._metadata[file_id]
        
        # Try to load from disk
        meta_file = os.path.join(self._cache_dir, f"{file_id}.meta.json")
        if os.path.exists(meta_file):
            try:
                import json
                with open(meta_file, 'r') as f:
                    data = json.load(f)
                file = FederatedFile(
                    file_id=data["file_id"],
                    original_url=data["original_url"],
                    filename=data["filename"],
                    mime_type=data["mime_type"],
                    size=data["size"],
                    checksum=data["checksum"],
                    uploaded_by=data["uploaded_by"],
                    uploaded_at=datetime.fromisoformat(data["uploaded_at"]),
                    expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
                )
                self._metadata[file_id] = file
                return file
            except Exception as e:
                print(f"Error loading file metadata: {e}")
        
        return None
    
    def get_local_path(self, file_id: str) -> Optional[str]:
        """Get the local path for a cached file."""
        meta_file = os.path.join(self._cache_dir, f"{file_id}.meta.json")
        if os.path.exists(meta_file):
            try:
                import json
                with open(meta_file, 'r') as f:
                    data = json.load(f)
                local_path = data.get("local_path")
                if local_path and os.path.exists(local_path):
                    return local_path
            except Exception:
                pass
        return None
    
    def file_exists(self, file_id: str) -> bool:
        """Check if a file is cached."""
        return self.get_local_path(file_id) is not None


class FileFederationClient:
    """Client for file operations with federated servers."""
    
    def __init__(self):
        self._cache = FileProxyCache()
        self._timeout = 30.0  # Longer timeout for file transfers
    
    async def upload_file_to_server(
        self,
        file_path: str,
        filename: str,
        mime_type: str,
        target_domain: str,
        uploaded_by: str
    ) -> Optional[FederatedFile]:
        """Upload a file to a federated server.
        
        Args:
            file_path: Local file path
            filename: Original filename
            mime_type: MIME type of file
            target_domain: Target federated server domain
            uploaded_by: User ID who is uploading
            
        Returns:
            FederatedFile metadata if successful
        """
        from decemsg.federation.discovery import get_federation_client
        
        client = get_federation_client()
        server_info = await client.discover_server(target_domain)
        
        if not server_info:
            return None
        
        try:
            # Read file and calculate checksum
            with open(file_path, 'rb') as f:
                content = f.read()
            
            checksum = hashlib.sha256(content).hexdigest()
            file_size = len(content)
            
            # Create multipart upload request
            boundary = "----DeceMSGBoundary" + str(int(time.time()))
            
            # Build multipart body
            body_parts = []
            
            # File metadata
            body_parts.append(f"--{boundary}\r\n")
            body_parts.append(f'Content-Disposition: form-data; name="metadata"\r\n')
            body_parts.append('Content-Type: application/json\r\n\r\n')
            import json
            meta = {
                "filename": filename,
                "mime_type": mime_type,
                "size": file_size,
                "checksum": checksum,
                "uploaded_by": uploaded_by
            }
            body_parts.append(json.dumps(meta))
            body_parts.append('\r\n')
            
            # File content
            body_parts.append(f"--{boundary}\r\n")
            body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n')
            body_parts.append(f'Content-Type: {mime_type}\r\n\r\n')
            body_parts.append(content)
            body_parts.append('\r\n')
            body_parts.append(f"--{boundary}--\r\n")
            
            body = ''.join([
                part if isinstance(part, str) else part.decode('utf-8', errors='replace')
                for part in body_parts
            ])
            
            # Create authenticated headers
            headers = create_authenticated_request(
                "POST",
                "/federation/files",
                body
            )
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                response = await http_client.post(
                    f"{server_info.api_url}/federation/files",
                    content=body.encode() if isinstance(body, str) else body,
                    headers=headers
                )
                
                if response.status_code in (200, 201, 202):
                    data = response.json()
                    return FederatedFile(
                        file_id=data["file_id"],
                        original_url=data["url"],
                        filename=filename,
                        mime_type=mime_type,
                        size=file_size,
                        checksum=checksum,
                        uploaded_by=uploaded_by,
                        uploaded_at=datetime.utcnow()
                    )
                    
        except Exception as e:
            print(f"File upload failed: {e}")
        
        return None
    
    async def download_file_from_server(
        self,
        file_id: str,
        source_domain: str
    ) -> Optional[str]:
        """Download a file from a federated server.
        
        Args:
            file_id: ID of the file to download
            source_domain: Source federated server domain
            
        Returns:
            Local path to downloaded file, or None on failure
        """
        # Check if already cached
        if self._cache.file_exists(file_id):
            return self._cache.get_local_path(file_id)
        
        from decemsg.federation.discovery import get_federation_client
        
        client = get_federation_client()
        server_info = await client.discover_server(source_domain)
        
        if not server_info:
            return None
        
        try:
            # Get file metadata first
            meta_headers = create_authenticated_request(
                "GET",
                f"/federation/files/{file_id}/metadata",
                ""
            )
            
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                # Get metadata
                meta_response = await http_client.get(
                    f"{server_info.api_url}/federation/files/{file_id}/metadata",
                    headers=meta_headers
                )
                
                if meta_response.status_code != 200:
                    return None
                
                meta = meta_response.json()
                
                # Download file content
                file_headers = create_authenticated_request(
                    "GET",
                    f"/federation/files/{file_id}",
                    ""
                )
                
                file_response = await http_client.get(
                    f"{server_info.api_url}/federation/files/{file_id}",
                    headers=file_headers
                )
                
                if file_response.status_code != 200:
                    return None
                
                content = file_response.content
                
                # Verify checksum
                actual_checksum = hashlib.sha256(content).hexdigest()
                if actual_checksum != meta.get("checksum"):
                    print(f"File checksum mismatch for {file_id}")
                    return None
                
                # Save to cache
                local_path = os.path.join(self._cache._cache_dir, file_id)
                with open(local_path, 'wb') as f:
                    f.write(content)
                
                # Add to cache
                file_meta = FederatedFile(
                    file_id=file_id,
                    original_url=f"{server_info.api_url}/federation/files/{file_id}",
                    filename=meta.get("filename", file_id),
                    mime_type=meta.get("mime_type", "application/octet-stream"),
                    size=len(content),
                    checksum=actual_checksum,
                    uploaded_by=meta.get("uploaded_by", ""),
                    uploaded_at=datetime.utcnow()
                )
                self._cache.add_file(file_meta, local_path)
                
                return local_path
                
        except Exception as e:
            print(f"File download failed: {e}")
        
        return None
    
    def get_cached_file(self, file_id: str) -> Optional[str]:
        """Get path to a cached file without downloading."""
        return self._cache.get_local_path(file_id)


# Global instance
_file_client: Optional[FileFederationClient] = None


def get_file_client() -> FileFederationClient:
    """Get the global file federation client."""
    global _file_client
    if _file_client is None:
        _file_client = FileFederationClient()
    return _file_client
