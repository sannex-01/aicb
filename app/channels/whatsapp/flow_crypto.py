import base64
import json
from typing import Tuple, Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from app.core.config import settings
from app.core.logger import logger


class WhatsAppFlowCrypto:
    """Decrypts and encrypts WhatsApp interactive flow payloads using RSA & AES-GCM."""

    def __init__(self, private_key_pem: Optional[str] = None, passphrase: Optional[str] = None):
        self.private_key_pem = private_key_pem or settings.WHATSAPP_FLOW_PRIVATE_KEY
        self.passphrase = passphrase or settings.WHATSAPP_FLOW_PRIVATE_KEY_PASSPHRASE
        self._private_key = None
        if self.private_key_pem:
            try:
                pass_bytes = self.passphrase.encode("utf-8") if self.passphrase else None
                self._private_key = serialization.load_pem_private_key(
                    self.private_key_pem.encode("utf-8"),
                    password=pass_bytes,
                    backend=default_backend(),
                )
            except Exception as e:
                logger.error(f"Failed to load WhatsApp Flow RSA private key: {e}")

    def decrypt_request(self, encrypted_aes_key_b64: str, encrypted_flow_data_b64: str, initial_vector_b64: str) -> Tuple[Dict[str, Any], bytes, bytes]:
        if not self._private_key:
            raise ValueError("WhatsApp Flow private key is not configured.")

        encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
        encrypted_flow_data = base64.b64decode(encrypted_flow_data_b64)
        iv = base64.b64decode(initial_vector_b64)

        # 1. Decrypt AES Key with RSA OAEP
        aes_key = self._private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # 2. Decrypt flow data with AES-GCM (tag is the last 16 bytes)
        tag = encrypted_flow_data[-16:]
        ciphertext = encrypted_flow_data[:-16]

        decryptor = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv, tag),
            backend=default_backend(),
        ).decryptor()

        decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        decrypted_json = json.loads(decrypted_bytes.decode("utf-8"))

        return decrypted_json, aes_key, iv

    def encrypt_response(self, response_payload: Dict[str, Any], aes_key: bytes, initial_vector: bytes) -> str:
        # Invert IV for response encryption as per Meta specification
        flipped_iv = bytes([b ^ 0xFF for b in initial_vector])
        plaintext = json.dumps(response_payload).encode("utf-8")

        encryptor = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(flipped_iv),
            backend=default_backend(),
        ).encryptor()

        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        tag = encryptor.tag

        return base64.b64encode(ciphertext + tag).decode("utf-8")
