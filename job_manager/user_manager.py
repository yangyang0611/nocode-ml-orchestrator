"""
Lightweight user registry backed by Redis.

Demo-grade only: username-based login, no password. A user record is
auto-created on first login and referenced by every submitted job.
"""
import re
from datetime import datetime, timezone
import redis
from config import REDIS_URL

_redis = redis.from_url(REDIS_URL, decode_responses=True)

USERS_SET = "users"
USER_KEY_PREFIX = "user:"

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


def _user_key(username: str) -> str:
    return f"{USER_KEY_PREFIX}{username}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_username(raw: str) -> str:
    return (raw or "").strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(_USERNAME_RE.fullmatch(username or ""))


def ensure_user(raw_username: str) -> dict:
    """
    Create-on-first-login. Returns the user record.
    Raises ValueError if username is invalid.
    """
    username = normalize_username(raw_username)
    if not is_valid_username(username):
        raise ValueError(
            "Username must start with a letter/digit and contain only "
            "lowercase letters, digits, '_' or '-' (2-32 chars)."
        )

    key = _user_key(username)
    now = _now()
    if not _redis.exists(key):
        _redis.hset(key, mapping={
            "username":    username,
            "created_at":  now,
            "last_active": now,
        })
        _redis.sadd(USERS_SET, username)
    else:
        _redis.hset(key, "last_active", now)
    return _redis.hgetall(key)


def get_user(username: str) -> dict | None:
    if not username:
        return None
    data = _redis.hgetall(_user_key(username))
    return data or None


def list_users() -> list[dict]:
    usernames = sorted(_redis.smembers(USERS_SET))
    return [u for u in (get_user(n) for n in usernames) if u]
