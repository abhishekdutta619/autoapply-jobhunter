from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_session


def get_db() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Reads the signed session cookie set by app/api/routes/auth.py's
    OAuth callback and loads the matching User row. Raises 401 if there's
    no session or it no longer resolves to a real user - every job-related
    route depends on this, so an unauthenticated request can never see or
    modify anyone's data.
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Stricter gate for actions that affect the owner's data specifically
    - e.g. triggering a Hunter run. Any authenticated account can view its
    own dashboard (empty, if it isn't the owner), but only the owner
    should be able to kick off a scrape that writes into their account."""
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="Only the account owner can do this")
    return user
