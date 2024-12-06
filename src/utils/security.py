import secrets
import jwt
from datetime import datetime, timedelta, timezone


class SecurityUtils:
    def __init__(self, client_id):
        self.client_id = client_id
        self._jwt_secret = secrets.token_urlsafe(64)
        self.api_key = secrets.token_urlsafe(32)

    @property
    def jwt_secret(self):
        return self._jwt_secret

    def get_env_vars(self):
        """Return security-related environment variables"""
        return {
            "CLIENT_ID": self.client_id,
            "API_KEY": self.api_key,
            "JWT_SECRET": self._jwt_secret,
        }

    def generate_access_token(self, expiration_minutes=60):
        """Generate JWT access token using stored secret"""
        payload = {
            "client_id": self.client_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes),
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_hex(16),
        }
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")
