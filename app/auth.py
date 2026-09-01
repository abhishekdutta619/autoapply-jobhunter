from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User


def _matches_owner(email: str | None, provider: str | None, github_username: str | None) -> bool:
    if settings.owner_email and email and email.strip().lower() == settings.owner_email.strip().lower():
        return True
    if (
        provider == "github"
        and github_username
        and settings.owner_github_username
        and github_username.strip().lower() == settings.owner_github_username.strip().lower()
    ):
        return True
    return False


def get_or_create_user(
    session: Session,
    *,
    email: str | None,
    name: str | None = None,
    avatar_url: str | None = None,
    provider: str | None = None,
    provider_id: str | None = None,
    github_username: str | None = None,
) -> User:
    """Resolves the User row for a login, keyed primarily on whether this
    login matches "owner" criteria (OWNER_EMAIL or, for GitHub,
    OWNER_GITHUB_USERNAME) rather than on email alone.

    This distinction matters: there must only ever be ONE row with
    is_owner=True, because app/hunter.py attributes every scraped job to
    that row's id specifically, not to "whichever row happens to have
    is_owner=True right now." If OWNER_EMAIL doesn't exactly match the
    email a provider actually hands back (very possible with GitHub,
    where many accounts hide their email), matching by email alone would
    create a *second* owner-flagged row that your existing jobs were
    never attributed to - technically "the owner," but pointing at an
    empty dataset. Matching on owner criteria first and reusing whatever
    row is_owner already points to avoids that split.

    Non-owner logins are still keyed on email as the stable cross-provider
    identity (Google today, GitHub tomorrow, same email = same account).
    """
    if _matches_owner(email, provider, github_username):
        user = session.scalar(select(User).where(User.is_owner.is_(True)))
        if user is None and email:
            # First-ever login for an owner previously only bootstrapped
            # by app/hunter.py's get_or_create_owner (which creates the
            # row under OWNER_EMAIL before anyone's actually logged in) -
            # reuse that placeholder row rather than creating a second one.
            user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(is_owner=True)
            session.add(user)
        user.is_owner = True
        if email:
            user.email = email
    else:
        user = session.scalar(select(User).where(User.email == email)) if email else None
        if user is None:
            user = User(email=email, is_owner=False)
            session.add(user)
        else:
            # Re-check on every login, not just at creation - if OWNER_EMAIL
            # or OWNER_GITHUB_USERNAME changes in .env later, the account
            # that no longer matches shouldn't stay flagged as owner.
            user.is_owner = False

    if name:
        user.name = name
    if avatar_url:
        user.avatar_url = avatar_url
    if provider:
        user.provider = provider
        user.provider_id = provider_id

    session.commit()
    session.refresh(user)
    return user


def get_or_create_owner(session: Session) -> User:
    """Bootstraps or reuses the single owner row - app/hunter.py needs a
    real user_id to attribute newly-scraped jobs to, and the hunter can
    run (e.g. on a cron) long before anyone opens a browser and logs in.

    Reuses an existing is_owner=True row if one already exists (e.g. the
    owner already logged in for real via GitHub) instead of always
    creating a fresh row under OWNER_EMAIL - see get_or_create_user's
    docstring for why having two different "owner" rows would be a bug.
    """
    owner = session.scalar(select(User).where(User.is_owner.is_(True)))
    if owner is not None:
        return owner

    if not settings.owner_email:
        raise RuntimeError(
            "OWNER_EMAIL is not set in .env - the hunter needs to know which "
            "account to attribute scraped jobs to. See .env.example."
        )
    return get_or_create_user(session, email=settings.owner_email, name="Owner")
