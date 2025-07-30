"""
Simple Dynamic Authentication Service
====================================

This module implements a simplified session-based authentication mechanism
for the VHM24R system. Instead of issuing long‑lived personal links that
persist for a year, the `SimpleDynamicAuth` service issues short‑lived
session tokens that can be redeemed exactly once within a limited time window.

When a user requests access from the Telegram bot, any existing active
sessions are invalidated and a new session token is generated. The token is
embedded into a URL pointing to the frontend, which then exchanges the
session for a JWT. After the token is redeemed the session is marked
inactive so it cannot be reused.

The default lifetime for a user session is two hours. Administrators can
request special admin sessions with longer lifetimes via dedicated
functions.
"""

import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import TelegramSession


class SimpleDynamicAuth:
    """Service for managing short‑lived session tokens."""

    def __init__(self) -> None:
        # Lifetime for regular user sessions (two hours by default)
        self.session_lifetime: timedelta = timedelta(hours=2)
        # Lifetime for admin sessions (extended to eight hours)
        self.admin_session_lifetime: timedelta = timedelta(hours=8)

    async def create_access_link(self, user_id: int, db: Session) -> str:
        """
        Generate a one‑time access link for a user.

        All existing active sessions for the given ``user_id`` are marked
        inactive. A new session token is generated and stored in the
        ``telegram_sessions`` table. The returned URL embeds the session
        token.

        :param user_id: Telegram identifier of the user
        :param db: SQLAlchemy session
        :returns: Absolute URL containing the session token
        """
        # Invalidate any existing sessions for this user
        old_sessions = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == user_id,
            TelegramSession.is_active.is_(True),
        ).all()
        for session in old_sessions:
            session.is_active = False

        # Create a new session token
        session_token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + self.session_lifetime

        new_session = TelegramSession(
            telegram_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(new_session)
        db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "https://vhm24r1-production.up.railway.app")
        return f"{frontend_url}/auth/session/{session_token}"

    async def validate_session_token(self, session_token: str, db: Session) -> int | None:
        """
        Validate a one‑time session token and return the associated user ID.

        If the token has expired or has already been redeemed the method
        returns ``None``. Otherwise the session is marked inactive and the
        Telegram user ID is returned.

        :param session_token: Raw session token extracted from the URL
        :param db: SQLAlchemy session
        :returns: Telegram user ID or ``None`` on failure
        """
        session = db.query(TelegramSession).filter(
            TelegramSession.session_token == session_token,
            TelegramSession.is_active.is_(True),
            TelegramSession.expires_at > datetime.utcnow(),
        ).first()
        if not session:
            return None

        # Deactivate the session after a successful validation (one‑time)
        session.is_active = False
        db.commit()
        return session.telegram_id

    async def create_admin_access_link(self, admin_telegram_id: int, db: Session) -> str:
        """
        Create an extended admin session and return a link for administrator access.

        Old admin sessions are deactivated, then a new session token prefixed
        with ``admin_`` is generated. Admin sessions can be reused multiple
        times until they expire.
        """
        # Deactivate any existing admin sessions
        old_sessions = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == admin_telegram_id,
            TelegramSession.session_token.like('admin_%'),
            TelegramSession.is_active.is_(True),
        ).all()
        for session in old_sessions:
            session.is_active = False

        admin_token = secrets.token_urlsafe(64)
        expires_at = datetime.utcnow() + self.admin_session_lifetime

        new_session = TelegramSession(
            telegram_id=admin_telegram_id,
            session_token=f"admin_{admin_token}",
            expires_at=expires_at,
            is_active=True,
        )
        db.add(new_session)
        db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "https://vhm24r1-production.up.railway.app")
        return f"{frontend_url}/auth/admin/{admin_token}"

    async def validate_admin_session(self, admin_token: str, db: Session) -> int | None:
        """
        Validate an administrator session token.

        Admin sessions are prefixed with ``admin_`` and are not marked
        inactive upon validation; they can be reused until expiration. This
        method returns the Telegram user ID if the session is valid and
        belongs to an admin user.
        """
        full_token = f"admin_{admin_token}"
        session = db.query(TelegramSession).filter(
            TelegramSession.session_token == full_token,
            TelegramSession.is_active.is_(True),
            TelegramSession.expires_at > datetime.utcnow(),
        ).first()
        if not session:
            return None
        return session.telegram_id