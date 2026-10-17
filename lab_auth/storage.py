"""Password-encrypted local token vault. Password is never stored on disk."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import tempfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .oauth import AuthError

class EncryptedVault:
    def __init__(self, directory: Path, passphrase: str):
        if not isinstance(passphrase, str) or len(passphrase) < 12:
            raise AuthError('Vault passphrase must be at least 12 characters')
        self.directory = Path(directory)
        self.passphrase = passphrase

    def _key(self, salt: bytes) -> bytes:
        return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(self.passphrase.encode('utf-8'))

    def save(self, client_id: str, subject: str, credentials: dict) -> Path:
        if not client_id.startswith('oaiapp_') or not subject or not credentials.get('access_token'):
            raise AuthError('Credentials require verified client identity and access token')
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        salt, nonce = os.urandom(16), os.urandom(12)
        data = json.dumps({'client_id': client_id, 'subject': subject, 'credentials': credentials}, sort_keys=True).encode()
        encrypted = AESGCM(self._key(salt)).encrypt(nonce, data, (client_id + ':' + subject).encode())
        blob = json.dumps({'v': 1, 'salt': base64.b64encode(salt).decode(), 'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(encrypted).decode()}).encode()
        import hashlib
        name = hashlib.sha256((client_id + ':' + subject).encode()).hexdigest() + '.vault'
        target = self.directory / name
        fd, temp = tempfile.mkstemp(prefix='.vault-', dir=self.directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, target)
            os.chmod(target, 0o600)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return target

    def load(self, client_id: str, subject: str) -> dict:
        import hashlib
        name = hashlib.sha256((client_id + ':' + subject).encode()).hexdigest() + '.vault'
        path = self.directory / name
        obj = json.loads(path.read_text())
        if obj.get('v') != 1:
            raise AuthError('Unsupported vault version')
        salt, nonce, ciphertext = (base64.b64decode(obj[k]) for k in ('salt', 'nonce', 'ciphertext'))
        plain = AESGCM(self._key(salt)).decrypt(nonce, ciphertext, (client_id + ':' + subject).encode())
        record = json.loads(plain)
        if record['client_id'] != client_id or record['subject'] != subject:
            raise AuthError('Vault identity mismatch')
        return record['credentials']
