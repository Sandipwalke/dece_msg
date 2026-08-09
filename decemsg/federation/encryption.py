"""End-to-end encryption for federated messages.

This module provides:
- Key pair generation for users
- Public key exchange via federation protocol
- Message encryption/decryption using ECIES (Elliptic Curve Integrated Encryption Scheme)
"""
import os
import base64
import hashlib
import json
from typing import Optional, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


@dataclass
class KeyPair:
    """User's encryption key pair."""
    private_key: bytes  # Base64 encoded private key
    public_key: bytes   # Base64 encoded public key
    
    @classmethod
    def generate(cls) -> "KeyPair":
        """Generate a new elliptic curve key pair."""
        private_key_obj = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key_obj = private_key_obj.public_key()
        
        private_bytes = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return cls(
            private_key=base64.b64encode(private_bytes).decode(),
            public_key=base64.b64encode(public_bytes).decode()
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "private_key": self.private_key,
            "public_key": self.public_key
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "KeyPair":
        """Load from dictionary."""
        return cls(
            private_key=data["private_key"],
            public_key=data["public_key"]
        )


class ECIESEncryptor:
    """ECIES (Elliptic Curve Integrated Encryption Scheme) implementation.
    
    Uses:
    - ECDH for key exchange
    - HKDF for key derivation
    - AES-256-GCM for symmetric encryption
    """
    
    def __init__(self, recipient_public_key: bytes):
        """Initialize with recipient's public key (base64 encoded)."""
        self.recipient_public_key = base64.b64decode(recipient_public_key)
    
    def encrypt(self, plaintext: str) -> Tuple[bytes, bytes, bytes]:
        """Encrypt plaintext using ECIES.
        
        Returns:
            Tuple of (ephemeral_public_key, nonce, ciphertext) - all base64 encoded
        """
        # Load recipient's public key
        recipient_pub = serialization.load_pem_public_key(
            self.recipient_public_key,
            backend=default_backend()
        )
        
        # Generate ephemeral key pair
        ephemeral_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        ephemeral_public = ephemeral_private.public_key()
        
        # Derive shared secret using ECDH
        shared_secret = ephemeral_private.exchange(ec.ECDH(), recipient_pub)
        
        # Derive encryption key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=b'decemsg-ecies-salt',
            info=b'decemsg-message-encryption',
        ).derive(shared_secret)
        
        # Encrypt with AES-256-GCM
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(derived_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Encode for transmission
        ephem_pub_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return (
            base64.b64encode(ephem_pub_bytes).decode(),
            base64.b64encode(nonce).decode(),
            base64.b64encode(ciphertext).decode()
        )


class ECIESDecryptor:
    """ECIES decryptor using user's private key."""
    
    def __init__(self, private_key: bytes):
        """Initialize with user's private key (base64 encoded)."""
        self.private_key = base64.b64decode(private_key)
    
    def decrypt(self, ephemeral_public_key: str, nonce: str, ciphertext: str) -> str:
        """Decrypt ciphertext using ECIES.
        
        Args:
            ephemeral_public_key: Base64 encoded ephemeral public key from sender
            nonce: Base64 encoded nonce used for encryption
            ciphertext: Base64 encoded ciphertext
            
        Returns:
            Decrypted plaintext string
        """
        # Load keys
        private_key_obj = serialization.load_pem_private_key(
            self.private_key,
            password=None,
            backend=default_backend()
        )
        
        ephem_pub_bytes = base64.b64decode(ephemeral_public_key)
        ephem_pub = serialization.load_pem_public_key(
            ephem_pub_bytes,
            backend=default_backend()
        )
        
        # Derive shared secret using ECDH
        shared_secret = private_key_obj.exchange(ec.ECDH(), ephem_pub)
        
        # Derive decryption key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'decemsg-ecies-salt',
            info=b'decemsg-message-encryption',
        ).derive(shared_secret)
        
        # Decrypt with AES-256-GCM
        nonce_bytes = base64.b64decode(nonce)
        ciphertext_bytes = base64.b64decode(ciphertext)
        
        aesgcm = AESGCM(derived_key)
        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext_bytes, None)
        
        return plaintext.decode('utf-8')


class EncryptedMessage:
    """Wrapper for encrypted message data."""
    
    def __init__(self, ephemeral_public_key: str, nonce: str, ciphertext: str):
        self.ephemeral_public_key = ephemeral_public_key
        self.nonce = nonce
        self.ciphertext = ciphertext
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ephem_pub_key": self.ephemeral_public_key,
            "nonce": self.nonce,
            "ciphertext": self.ciphertext
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedMessage":
        """Load from dictionary."""
        return cls(
            ephemeral_public_key=data["ephem_pub_key"],
            nonce=data["nonce"],
            ciphertext=data["ciphertext"]
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "EncryptedMessage":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


def encrypt_message(plaintext: str, recipient_public_key: str) -> EncryptedMessage:
    """Encrypt a message for a recipient.
    
    Args:
        plaintext: The message text to encrypt
        recipient_public_key: Base64 encoded recipient's public key
        
    Returns:
        EncryptedMessage object containing encrypted data
    """
    encryptor = ECIESEncryptor(recipient_public_key)
    ephem_key, nonce, ciphertext = encryptor.encrypt(plaintext)
    return EncryptedMessage(ephem_key, nonce, ciphertext)


def decrypt_message(
    encrypted: EncryptedMessage,
    private_key: str
) -> str:
    """Decrypt a message using private key.
    
    Args:
        encrypted: EncryptedMessage object containing encrypted data
        private_key: Base64 encoded user's private key
        
    Returns:
        Decrypted plaintext string
    """
    decryptor = ECIESDecryptor(private_key)
    return decryptor.decrypt(
        encrypted.ephemeral_public_key,
        encrypted.nonce,
        encrypted.ciphertext
    )


# User key storage (in production, use a secure database)
_user_keys: dict[str, KeyPair] = {}


def get_user_key_pair(user_id: str) -> Optional[KeyPair]:
    """Get a user's key pair, or None if not generated."""
    return _user_keys.get(user_id)


def generate_user_keys(user_id: str) -> KeyPair:
    """Generate and store a new key pair for a user."""
    key_pair = KeyPair.generate()
    _user_keys[user_id] = key_pair
    return key_pair


def set_user_keys(user_id: str, key_pair: KeyPair):
    """Store a user's key pair."""
    _user_keys[user_id] = key_pair


# Federation public key cache
_federated_keys: dict[str, str] = {}  # user_id -> public_key


def cache_federated_key(user_id: str, public_key: str):
    """Cache a federated user's public key."""
    _federated_keys[user_id] = public_key


def get_federated_key(user_id: str) -> Optional[str]:
    """Get cached federated user's public key."""
    return _federated_keys.get(user_id)


def clear_federated_key(user_id: str):
    """Remove a federated user's public key from cache."""
    if user_id in _federated_keys:
        del _federated_keys[user_id]
