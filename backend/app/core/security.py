import hashlib
import hmac
import secrets

from app.core.errors import ForbiddenError


def new_session_id() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sign_csrf_token(*, session_id: str, raw_token: str, secret: str) -> str:
    signature = _csrf_signature(session_id=session_id, raw_token=raw_token, secret=secret)
    return f"{raw_token}.{signature}"


def verify_csrf_token(
    *,
    session_id: str,
    signed_token: str | None,
    header_token: str | None,
    secret: str,
) -> None:
    if not signed_token or not header_token:
        raise ForbiddenError("invalid csrf token")

    raw_token, separator, signature = signed_token.partition(".")
    if not raw_token or not separator or not signature:
        raise ForbiddenError("invalid csrf token")

    expected_signature = _csrf_signature(session_id=session_id, raw_token=raw_token, secret=secret)
    if not hmac.compare_digest(raw_token, header_token):
        raise ForbiddenError("invalid csrf token")
    if not hmac.compare_digest(signature, expected_signature):
        raise ForbiddenError("invalid csrf token")


def unsigned_csrf_token(signed_token: str | None) -> str:
    if not signed_token:
        return ""
    raw_token, separator, _signature = signed_token.partition(".")
    if not separator:
        return ""
    return raw_token


def hash_ip(ip_address: str | None, secret: str) -> str | None:
    if not ip_address:
        return None
    return hashlib.sha256(f"{secret}:{ip_address}".encode()).hexdigest()


def _csrf_signature(*, session_id: str, raw_token: str, secret: str) -> str:
    payload = f"{session_id}:{raw_token}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
