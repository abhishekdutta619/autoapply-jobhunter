from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.schemas import UserOut
from app.auth import get_or_create_user
from app.config import settings
from app.db.models import User

log = logging.getLogger("api.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()

# Only registered if credentials are actually set, so a half-configured
# .env degrades to "that provider's button 404s with a clear message"
# instead of the whole API failing to start.
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.github_client_id and settings.github_client_secret:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )


def _client_or_404(provider: str):
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{provider} login isn't configured - set "
                f"{provider.upper()}_CLIENT_ID/{provider.upper()}_CLIENT_SECRET in .env"
            ),
        )
    return client


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    client = _client_or_404(provider)
    redirect_uri = str(request.url_for("auth_callback", provider=provider))
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}", name="auth_callback")
async def callback(provider: str, request: Request, db: Session = Depends(get_db)):
    client = _client_or_404(provider)
    try:
        token = await client.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 - send the browser back with a
        # message instead of a raw 500 page; expired/denied OAuth states
        # land here (e.g. the person closed the consent screen).
        log.warning("%s OAuth callback failed: %s", provider, exc)
        return RedirectResponse(f"{settings.frontend_base_url}/login?error=oauth_failed")

    if provider == "google":
        profile = token.get("userinfo") or await client.parse_id_token(request, token)
        email = profile.get("email")
        name = profile.get("name")
        avatar_url = profile.get("picture")
        provider_id = profile.get("sub")
        github_username = None
    elif provider == "github":
        resp = await client.get("user", token=token)
        profile = resp.json()
        email = profile.get("email")
        if not email:
            # GitHub only includes a public email here if the account has
            # one set to public; user:email scope lets us fall back to
            # their primary address via a second call instead.
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
            email = primary["email"] if primary else None
        github_username = profile.get("login")
        name = profile.get("name") or github_username
        avatar_url = profile.get("avatar_url")
        provider_id = str(profile.get("id"))
    else:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    if not email and not github_username:
        return RedirectResponse(f"{settings.frontend_base_url}/login?error=no_email")

    user = get_or_create_user(
        db,
        email=email,
        name=name,
        avatar_url=avatar_url,
        provider=provider,
        provider_id=provider_id,
        github_username=github_username,
    )
    request.session["user_id"] = user.id
    return RedirectResponse(settings.frontend_base_url)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"loggedOut": True}


@router.get("/providers")
def available_providers() -> dict[str, bool]:
    """Lets the login page only render buttons for providers that actually
    have credentials configured, instead of a button that 404s on click."""
    return {
        "google": bool(settings.google_client_id and settings.google_client_secret),
        "github": bool(settings.github_client_id and settings.github_client_secret),
    }
