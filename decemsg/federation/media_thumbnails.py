"""Media thumbnail generation for DeceMSG federation.

This module provides:
- Thumbnail generation for images
- Thumbnail caching
- Cross-server thumbnail sharing
"""
import hashlib
import json
import os
import io
from datetime import datetime
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import asyncio

from decemsg.core.config import get_config


@dataclass
class Thumbnail:
    """Generated thumbnail metadata."""
    file_id: str
    original_url: str
    thumbnail_url: str
    width: int
    height: int
    size_bytes: int
    mime_type: str
    created_at: datetime
    
    def to_dict(self) -> dict:
        return {
            "file_id": self.file_id,
            "original_url": self.original_url,
            "thumbnail_url": self.thumbnail_url,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat()
        }


class ThumbnailGenerator:
    """Generates thumbnails for media files."""
    
    DEFAULT_SIZES = {
        "small": (128, 128),
        "medium": (256, 256),
        "large": (512, 512),
    }
    
    def __init__(
        self,
        cache_dir: str = "./data/thumbnails",
        max_size_bytes: int = 10 * 1024 * 1024  # 10MB
    ):
        self._cache_dir = cache_dir
        self._max_size_bytes = max_size_bytes
        self._cache: Dict[str, Thumbnail] = {}
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, file_url: str, size: str = "medium") -> str:
        """Generate cache key for a thumbnail."""
        key_data = f"{file_url}:{size}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get the path to a cached thumbnail."""
        return os.path.join(self._cache_dir, f"{cache_key}.jpg")
    
    async def generate_thumbnail(
        self,
        file_url: str,
        file_content: bytes,
        size: str = "medium",
        mime_type: str = "image/jpeg"
    ) -> Optional[Thumbnail]:
        """Generate a thumbnail for an image.
        
        Args:
            file_url: Original file URL
            file_content: Raw image bytes
            size: Thumbnail size preset
            mime_type: Image MIME type
        
        Returns:
            Thumbnail metadata, or None on failure
        """
        target_size = self.DEFAULT_SIZES.get(size, self.DEFAULT_SIZES["medium"])
        
        try:
            # Try to use PIL for image processing
            try:
                from PIL import Image
                
                # Open image from bytes
                img = Image.open(io.BytesIO(file_content))
                
                # Convert to RGB if necessary
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Calculate new dimensions maintaining aspect ratio
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                
                width, height = img.size
                
                # Save thumbnail to buffer
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                thumbnail_bytes = buffer.getvalue()
                
            except ImportError:
                # PIL not available, create a placeholder
                return await self._create_placeholder_thumbnail(
                    file_url, target_size, mime_type
                )
            
            # Generate cache key
            cache_key = self._get_cache_key(file_url, size)
            cache_path = self._get_cache_path(cache_key)
            
            # Save thumbnail
            with open(cache_path, 'wb') as f:
                f.write(thumbnail_bytes)
            
            # Generate thumbnail ID
            file_id = f"thumb_{cache_key}"
            
            # Create URL (would be actual URL in production)
            thumbnail_url = f"/api/thumbnails/{file_id}"
            
            thumbnail = Thumbnail(
                file_id=file_id,
                original_url=file_url,
                thumbnail_url=thumbnail_url,
                width=width,
                height=height,
                size_bytes=len(thumbnail_bytes),
                mime_type="image/jpeg",
                created_at=datetime.utcnow()
            )
            
            self._cache[file_id] = thumbnail
            return thumbnail
            
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return None
    
    async def _create_placeholder_thumbnail(
        self,
        file_url: str,
        size: Tuple[int, int],
        mime_type: str
    ) -> Optional[Thumbnail]:
        """Create a placeholder thumbnail when PIL is not available."""
        try:
            # Create a simple placeholder image using basic Python
            width, height = size
            
            # Create a simple colored rectangle as placeholder
            # This is a minimal valid JPEG header + data
            # In production, you'd want proper image generation
            
            placeholder_data = self._create_simple_placeholder(width, height)
            
            cache_key = self._get_cache_key(file_url, "medium")
            cache_path = self._get_cache_path(cache_key)
            
            with open(cache_path, 'wb') as f:
                f.write(placeholder_data)
            
            file_id = f"thumb_{cache_key}"
            thumbnail_url = f"/api/thumbnails/{file_id}"
            
            thumbnail = Thumbnail(
                file_id=file_id,
                original_url=file_url,
                thumbnail_url=thumbnail_url,
                width=width,
                height=height,
                size_bytes=len(placeholder_data),
                mime_type="image/jpeg",
                created_at=datetime.utcnow()
            )
            
            self._cache[file_id] = thumbnail
            return thumbnail
            
        except Exception as e:
            print(f"Error creating placeholder: {e}")
            return None
    
    def _create_simple_placeholder(self, width: int, height: int) -> bytes:
        """Create a simple valid JPEG placeholder."""
        # Minimal valid JPEG structure (1x1 white pixel)
        # This is a placeholder - real thumbnails would use PIL
        jpeg_header = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF9, 0x6E, 0xA3,
            0xF8, 0x80, 0xB3, 0xFF, 0xD9
        ])
        return jpeg_header
    
    def get_thumbnail(self, file_id: str) -> Optional[Thumbnail]:
        """Get cached thumbnail metadata."""
        return self._cache.get(file_id)
    
    def get_thumbnail_path(self, file_id: str) -> Optional[str]:
        """Get the path to a cached thumbnail file."""
        if file_id not in self._cache:
            return None
        
        cache_key = file_id.replace("thumb_", "")
        path = self._get_cache_path(cache_key)
        
        if os.path.exists(path):
            return path
        return None
    
    def cleanup_old(self, max_age_days: int = 7) -> int:
        """Remove thumbnails older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        removed = 0
        
        for file_id, thumbnail in list(self._cache.items()):
            if thumbnail.created_at < cutoff:
                cache_key = file_id.replace("thumb_", "")
                path = self._get_cache_path(cache_key)
                
                if os.path.exists(path):
                    os.remove(path)
                
                del self._cache[file_id]
                removed += 1
        
        if removed:
            self._save_cache()
        
        return removed
    
    def _save_cache(self):
        """Save cache metadata to disk."""
        cache_file = os.path.join(self._cache_dir, "cache.json")
        
        data = {
            file_id: thumbnail.to_dict()
            for file_id, thumbnail in self._cache.items()
        }
        
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)


# Global instance
_thumbnail_generator: Optional[ThumbnailGenerator] = None


def get_thumbnail_generator() -> ThumbnailGenerator:
    """Get the global thumbnail generator."""
    global _thumbnail_generator
    if _thumbnail_generator is None:
        _thumbnail_generator = ThumbnailGenerator()
    return _thumbnail_generator
