from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User, UserInvite
from app.services import invite_email_service
from app.utils.helpers import new_uuid

settings = get_settings()
PASSWORD_HASH_ITERATIONS = 390_000
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"


@dataclass(frozen=True)
class UserInviteCreateResult:
    invite: UserInvite
    invite_code: str
    email_delivery_status: str
    email_delivery_detail: str | None
    reissued_existing: bool


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _normalize_identifier(value: str | None) -> str:
    return _clean(value).casefold()


def _normalize_email(value: str | None) -> str:
    return _normalize_identifier(value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    cleaned_password = _clean(password)
    if len(cleaned_password) < 8:
        raise ValueError("Password must be at least 8 characters")

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        cleaned_password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt, expected_digest = hashed_password.split("$", 3)
    except ValueError:
        return False

    if algorithm != PASSWORD_HASH_PREFIX:
        return False

    computed_digest = hashlib.pbkdf2_hmac(
        "sha256",
        _clean(password).encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(computed_digest, expected_digest)


def make_invite_token() -> tuple[str, str]:
    invite_code = secrets.token_urlsafe(24)
    invite_token_hash = hashlib.sha256(invite_code.encode("utf-8")).hexdigest()
    return invite_code, invite_token_hash


def _resolve_admin_email() -> str:
    if _clean(settings.admin_email):
        return _clean(settings.admin_email)
    if "@" in settings.admin_username:
        return _clean(settings.admin_username)
    return f"{_clean(settings.admin_username) or 'admin'}@lecrown.local"


def _find_user_by_identifier(db: Session, identifier: str) -> User | None:
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return None

    statement = select(User).where(
        or_(
            func.lower(User.username) == normalized_identifier,
            func.lower(User.email) == normalized_identifier,
        )
    )
    return db.scalars(statement).first()


def _find_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return None

    statement = select(User).where(func.lower(User.email) == normalized_email)
    return db.scalars(statement).first()


def _find_user_by_username(db: Session, username: str) -> User | None:
    normalized_username = _normalize_identifier(username)
    if not normalized_username:
        return None

    statement = select(User).where(func.lower(User.username) == normalized_username)
    return db.scalars(statement).first()


def ensure_bootstrap_admin_user(db: Session) -> User:
    existing_user = db.scalars(select(User).limit(1)).first()
    if existing_user is not None:
        return existing_user

    admin_user = User(
        id=new_uuid(),
        username=_clean(settings.admin_username) or "admin",
        email=_resolve_admin_email(),
        hashed_password=hash_password(settings.admin_password),
        is_active=True,
        is_admin=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user


def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    ensure_bootstrap_admin_user(db)
    user = _find_user_by_identifier(db, identifier)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def list_user_invites(db: Session) -> list[UserInvite]:
    statement = select(UserInvite).order_by(UserInvite.created_at.desc())
    return list(db.scalars(statement).all())


def create_user_invite(
    db: Session,
    *,
    current_user: User,
    email: str,
) -> UserInviteCreateResult:
    cleaned_email = _normalize_email(email)
    if not cleaned_email or "@" not in cleaned_email:
        raise ValueError("A valid email is required")
    if _find_user_by_email(db, cleaned_email) is not None:
        raise ValueError("A user with that email already exists")

    existing_pending_invite = db.scalars(
        select(UserInvite).where(
            func.lower(UserInvite.email) == cleaned_email,
            UserInvite.accepted_at.is_(None),
            UserInvite.revoked_at.is_(None),
            UserInvite.expires_at >= _utc_now(),
        )
    ).first()
    reissued_existing = existing_pending_invite is not None
    if existing_pending_invite is not None:
        existing_pending_invite.revoked_at = _utc_now()
        db.add(existing_pending_invite)

    invite_code, invite_token_hash = make_invite_token()
    invite = UserInvite(
        id=new_uuid(),
        email=cleaned_email,
        invite_token_hash=invite_token_hash,
        created_by_user_id=current_user.id,
        expires_at=_utc_now() + timedelta(days=max(1, settings.user_invite_expire_days)),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    email_delivery_status = "manual"
    email_delivery_detail: str | None = None
    try:
        delivery_result = invite_email_service.send_user_invite_email(
            recipient_email=invite.email,
            invite_code=invite_code,
            expires_at=invite.expires_at,
            invited_by_email=current_user.email,
        )
        email_delivery_status = "sent"
        email_delivery_detail = (
            f"Invite email sent from {delivery_result.sender_email}."
        )
    except invite_email_service.InviteEmailConfigurationError as exc:
        email_delivery_detail = str(exc)
    except invite_email_service.InviteEmailDeliveryError as exc:
        email_delivery_detail = f"{exc} Copy the invite code manually."

    return UserInviteCreateResult(
        invite=invite,
        invite_code=invite_code,
        email_delivery_status=email_delivery_status,
        email_delivery_detail=email_delivery_detail,
        reissued_existing=reissued_existing,
    )


def revoke_user_invite(db: Session, *, invite_id: str) -> UserInvite:
    invite = db.get(UserInvite, invite_id)
    if invite is None:
        raise LookupError("Invite not found")
    if invite.accepted_at is not None:
        raise ValueError("Accepted invites cannot be revoked")
    if invite.revoked_at is None:
        invite.revoked_at = _utc_now()
        db.add(invite)
        db.commit()
        db.refresh(invite)
    return invite


def accept_user_invite(
    db: Session,
    *,
    invite_code: str,
    username: str,
    password: str,
) -> User:
    cleaned_code = _clean(invite_code)
    cleaned_username = _clean(username)
    if len(cleaned_username) < 3:
        raise ValueError("Username must be at least 3 characters")

    invite_token_hash = hashlib.sha256(cleaned_code.encode("utf-8")).hexdigest()
    invite = db.scalars(
        select(UserInvite).where(UserInvite.invite_token_hash == invite_token_hash)
    ).first()
    if invite is None:
        raise LookupError("Invite not found")
    if invite.revoked_at is not None:
        raise ValueError("Invite has been revoked")
    if invite.accepted_at is not None:
        raise ValueError("Invite has already been used")
    expires_at = _coerce_utc(invite.expires_at)
    if expires_at is not None and expires_at < _utc_now():
        raise ValueError("Invite has expired")
    if _find_user_by_email(db, invite.email) is not None:
        raise ValueError("A user with that email already exists")
    if _find_user_by_username(db, cleaned_username) is not None:
        raise ValueError("That username is already taken")

    user = User(
        id=new_uuid(),
        username=cleaned_username,
        email=invite.email,
        hashed_password=hash_password(password),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.flush()

    invite.accepted_by_user_id = user.id
    invite.accepted_at = _utc_now()
    db.add(invite)
    db.commit()
    db.refresh(user)
    return user


def change_user_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> User:
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")

    user.hashed_password = hash_password(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
