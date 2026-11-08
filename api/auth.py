import base64
import hashlib
import hmac
import json
import time

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ponytail: hand-rolled HS256 (stdlib) instead of PyJWT; fine for this size.
def jwt_encode(payload: dict, hours: int = 12) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {**payload, "exp": int(time.time()) + hours * 3600}
    h = _b64(json.dumps(header, separators=(",", ":")).encode())
    p = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(settings.SECRET_KEY.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64(sig)}"


def jwt_decode(token: str) -> dict:
    try:
        h, p, sig = token.split(".")
        expected = hmac.new(settings.SECRET_KEY.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, _b64(expected)):
            raise ValueError
        payload = json.loads(_unb64(p))
        if payload.get("exp", 0) < time.time():
            raise ValueError
        return payload
    except Exception:
        raise AuthenticationFailed("Invalid or expired token")


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        payload = jwt_decode(header[7:])
        from .models import User
        user = User.objects.filter(id=payload.get("uid"), is_active=True).first()
        if user is None:
            raise AuthenticationFailed("User not found")
        return (user, None)
