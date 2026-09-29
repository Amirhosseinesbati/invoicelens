import base64
import binascii
import hashlib
import hmac
import json
import time

from argon2 import PasswordHasher
from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User, Workspace

password_hash = PasswordHasher()
TOKEN_MAX_AGE = 60 * 60 * 12


def create_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "workspace_id": user.workspace_id,
        "exp": int(time.time()) + TOKEN_MAX_AGE,
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(
        get_settings().secret_key.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def decode_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(
            get_settings().secret_key.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
            raise ValueError("expired")
        return payload
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Session expired or invalid") from None


def current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    session: str | None = Cookie(default=None, alias="invoicelens_session"),
) -> User:
    token = (
        authorization[7:]
        if authorization and authorization.lower().startswith("bearer ")
        else session
    )
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    payload = decode_token(token)
    user = db.scalar(select(User).where(User.id == payload.get("user_id")))
    if not user or user.workspace_id != payload.get("workspace_id"):
        raise HTTPException(status_code=401, detail="Session no longer valid")
    return user


def operator(user: User = Depends(current_user)) -> User:
    if user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Operator role required")
    return user


def seed_demo_users(db: Session) -> None:
    if get_settings().mode != "DEMO":
        return
    seed = [
        ("harbor-demo-a", "Harbor Industrial · Demo A", "admin@example.com", "admin"),
        ("harbor-demo-a", "Harbor Industrial · Demo A", "operator@example.com", "operator"),
        ("harbor-demo-a", "Harbor Industrial · Demo A", "viewer@example.com", "viewer"),
        ("harbor-demo-b", "Harbor Industrial · Demo B", "operator2@example.com", "operator"),
    ]
    for workspace_id, name, email, role in seed:
        if not db.get(Workspace, workspace_id):
            db.add(Workspace(id=workspace_id, name=name, is_demo=True))
            db.flush()
        if not db.scalar(select(User).where(User.email == email)):
            db.add(
                User(
                    workspace_id=workspace_id,
                    email=email,
                    role=role,
                    password_hash=password_hash.hash("DemoPass123!"),
                )
            )
    db.commit()
