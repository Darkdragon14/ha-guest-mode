import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import asyncio

KEY_FILE_PATH = "/config/custom_components/ha_guest_mode/private_key.pem"

class KeyManager:
    def __init__(self, key_file_path=KEY_FILE_PATH):
        self.key_file_path = key_file_path
        self.private_key = None
        self.public_key = None

    async def load_or_generate_key(self):
        if os.path.exists(self.key_file_path):
            await self._load_key()
        else:
            await self._generate_key()

    async def _generate_key(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        pem_data = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_key_to_file, pem_data)
        self.public_key = self.private_key.public_key()

    def _write_key_to_file(self, pem_data):
        with open(self.key_file_path, "wb") as key_file:
            key_file.write(pem_data)

    async def _load_key(self):
        loop = asyncio.get_running_loop()
        self.private_key = await loop.run_in_executor(None, self._read_key_from_file)
        self.public_key = self.private_key.public_key()

    def _read_key_from_file(self):
        with open(self.key_file_path, "rb") as key_file:
            return serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )

    def get_private_key(self):
        return self.private_key

    def get_public_key(self):
        return self.public_key
