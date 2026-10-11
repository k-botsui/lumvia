import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from app.config import settings
from app.context import request_id as current_request_id
from app.db import get_db
from app.errors import problem
from app.models import Audit, Library, Session, User, now
from fastapi import Depends, Request, Response
from pwdlib import PasswordHash
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(24))
redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class Principal:
    user: User
    library: Library
    session: Session


def require_user(request: Request, db: DBSession = Depends(get_db)) -> Principal:
    token = request.cookies.get("lumvia_session")
    session = db.scalar(
        select(Session).where(Session.token_hash == digest(token or ""), Session.expires_at > now())
    )
    if not session:
        problem(401, "AUTH_REQUIRED", "ログインしてください。")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(session.csrf_hash, digest(csrf)):
            problem(403, "CSRF_INVALID", "ページを再読み込みして、もう一度お試しください。")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        rate_limit(f"write:{session.user_id}", 300, 60)
    user = db.get(User, session.user_id)
    library = db.scalar(select(Library).where(Library.owner_id == user.id))
    return Principal(user, library, session)


def establish_session(db: DBSession, user: User, response: Response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    session = Session(
        user_id=user.id,
        token_hash=digest(token),
        csrf_hash=digest(csrf),
        expires_at=now() + timedelta(hours=settings.session_hours),
    )
    db.add(session)
    audit(db, user.id, "auth.login", user.id)
    db.commit()
    for name, value, http_only in [("lumvia_session", token, True), ("lumvia_csrf", csrf, False)]:
        response.set_cookie(
            name,
            value,
            httponly=http_only,
            secure=settings.environment == "production",
            samesite="lax",
            max_age=settings.session_hours * 3600,
            path="/",
        )


def audit(db, user_id, action, resource_id=None, request_id=None):
    db.add(
        Audit(
            user_id=user_id,
            action=action,
            resource_id=resource_id,
            request_id=request_id or current_request_id.get(),
        )
    )


def rate_limit(key: str, limit: int, seconds: int):
    try:
        # Atomic increment + expiry; Redis never stores durable application state.
        count = redis.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1,
            key,
            seconds,
        )
        if count > limit:
            problem(429, "RATE_LIMITED", "しばらく待ってから、もう一度お試しください。")
    except RedisError:
        problem(503, "TEMPORARILY_UNAVAILABLE", "現在接続できません。少し待ってからお試しください。")


def owned(db, model, identifier, principal):
    item = db.get(model, identifier)
    if not item or item.library_id != principal.library.id:
        problem(404, "NOT_FOUND", "項目が見つかりません。")
    return item
