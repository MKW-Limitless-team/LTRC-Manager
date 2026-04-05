from secrets import token_urlsafe
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.models import SessionState, SessionUser
from app.core.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


def _build_avatar_url(user_payload: dict) -> str | None:
    avatar = user_payload.get("avatar")
    user_id = user_payload.get("id")
    if not avatar or not user_id:
        return None
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"


def _frontend_redirect(path: str) -> str:
    settings = get_settings()
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}{path}"


@router.get("/login")
async def login(request: Request):
    settings = get_settings()
    settings.require_discord_oauth()

    state = token_urlsafe(32)
    request.session["oauth_state"] = state

    query = urlencode(
        {
            "client_id": settings.discord_client_id,
            "redirect_uri": settings.discord_redirect_uri,
            "response_type": "code",
            "scope": "identify",
            "state": state,
        }
    )
    return RedirectResponse(url=f"{DISCORD_AUTHORIZE_URL}?{query}", status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    settings = get_settings()
    settings.require_discord_oauth()

    if error:
        logger.warning("Discord OAuth returned an error: %s", error)
        return RedirectResponse(url=_frontend_redirect(f"/login?error={error}"), status_code=status.HTTP_302_FOUND)

    if not code or not state or request.session.get("oauth_state") != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    try:
        token_response = requests.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        user_response = requests.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        user_response.raise_for_status()
        user_payload = user_response.json()
    except requests.RequestException as exc:
        logger.error("Discord OAuth request failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Discord OAuth failed") from exc

    authorized = user_payload["id"] in settings.allowed_user_ids
    session_user = SessionUser(
        id=user_payload["id"],
        display_name=user_payload.get("global_name") or user_payload.get("username") or "Discord User",
        avatar_url=_build_avatar_url(user_payload),
        authorized=authorized,
    )

    request.session.pop("oauth_state", None)
    request.session["user"] = session_user.model_dump()

    destination = "/app" if authorized else "/login?error=not_allowed"
    return RedirectResponse(url=_frontend_redirect(destination), status_code=status.HTTP_302_FOUND)


@router.get("/me", response_model=SessionState)
async def me(request: Request):
    user_data = request.session.get("user")
    if not user_data:
        return SessionState(authenticated=False, user=None)
    return SessionState(authenticated=True, user=SessionUser(**user_data))


@router.post("/logout")
async def logout(request: Request):
    settings = get_settings()
    request.session.clear()
    response = JSONResponse({"success": True})
    response.delete_cookie(settings.session_cookie_name)
    return response
