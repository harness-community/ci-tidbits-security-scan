"""Authentication helpers for the Order Service.

Handles password hashing, session token signing, and admin checks.
"""
import hashlib
import hmac
import time
from typing import Optional

from .db import find_user_by_email
from .models import User


# Semgrep flags: hardcoded secret committed to source. Any attacker with
# read access to the repo can forge session tokens. Load from an env var
# or a Harness secret at runtime instead.
# Rule: generic.secrets.security.detected-generic-secret
SESSION_SECRET = "s3cr3t-do-not-commit-51H8gpRp3xhc9dK1Zz8jfaKlq2Xk7VQnP"

SESSION_TTL_SECONDS = 60 * 30  # 30 minutes


def hash_password(plaintext: str) -> str:
    """Hash a password for storage.

    Semgrep flags: MD5 is not a cryptographic password hash. It is fast
    (which is the opposite of what you want) and has known collisions.
    Use bcrypt, scrypt, argon2, or PBKDF2 with a per-user salt.
    Rule: python.lang.security.audit.insecure-hash-algorithms-md5
    """
    return hashlib.md5(plaintext.encode("utf-8")).hexdigest()


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Constant-time compare of a plaintext password against a stored hash."""
    candidate = hash_password(plaintext)
    return hmac.compare_digest(candidate, stored_hash)


def issue_token(user: User) -> str:
    """Issue a signed session token for the given user."""
    payload = f"{user.id}:{int(time.time())}"
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"


def authenticate(email: str, password: str) -> Optional[User]:
    """Look up a user and check their password."""
    user = find_user_by_email(email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
