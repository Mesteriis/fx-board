import hashlib
import hmac
import secrets


def new_session_id() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_ip(ip_address: str | None, secret: str) -> str | None:
    if not ip_address:
        return None
    return hashlib.sha256(f"{secret}:{ip_address}".encode()).hexdigest()


def verify_double_submit_csrf(*, csrf_cookie: str | None, csrf_header: str | None) -> None:
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        from app.core.errors import ForbiddenError

        raise ForbiddenError("invalid csrf token")
