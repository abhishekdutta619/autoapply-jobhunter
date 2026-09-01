from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User


def get_or_create_user(
    session: Session,
    *,
    email: str,
    name: str | None = None,
    avatar_url: str | None = None,
    provider: str | None = None,
    provider_id: str | None = None,
) -> User:
    """Looks a user up by email - the stable identity across providers,
    so logging in with Google today and GitHub tomorrow using the same
    address is treated as one account, not two - and creates one if it
    doesn't exist yet. Whoever's email matches OWNER_EMAIL is flagged
    is_owner=True; see that setting's comment in .env.example for why
    that matters (it's who scraped jobs get attributed to).
    """
    user = session.scalar(select(User).where(User.email == email))
    is_owner = bool(settings.owner_email) and email.strip().lower() == settings.owner_email.strip().lower()

    if user is None:
        user = User(
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider=provider,
            provider_id=provider_id,
            is_owner=is_owner,
        )
        session.add(user)
    else:
        if name:
            user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        if provider:
            user.provider = provider
            user.provider_id = provider_id
        user.is_owner = is_owner

    session.commit()
    session.refresh(user)
    return user


def get_or_create_owner(session: Session) -> User:
    """Bootstraps the owner's account row from OWNER_EMAIL even before
    they've ever actually logged into the dashboard - app/hunter.py needs
    a real user_id to attribute newly-scraped jobs to, and the hunter can
    run (e.g. on a cron) long before anyone opens a browser."""
    if not settings.owner_email:
        raise RuntimeError(
            "OWNER_EMAIL is not set in .env - the hunter needs to know which "
            "account to attribute scraped jobs to. See .env.example."
        )
    return get_or_create_user(session, email=settings.owner_email, name="Owner")
