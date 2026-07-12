from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AdminUser
from app.schemas.auth import PrincipalRead

router = APIRouter(prefix="/auth", tags=["auth"])
oauth = OAuth()

if settings.google_oauth_configured:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "verify": settings.google_oauth_verify_ssl,
        },
    )


@router.get("/me", response_model=PrincipalRead)
def me(principal: Principal = Depends(get_current_principal)) -> PrincipalRead:
    return PrincipalRead(
        email=principal.email,
        is_authenticated=principal.is_authenticated,
        is_super=principal.is_super,
        permissions=sorted(principal.permissions),
        auth_mode=settings.auth_mode,
        oauth_configured=settings.google_oauth_configured,
    )


@router.get("/login/google", include_in_schema=False)
async def google_login(request: Request, next: str = "/#home") -> RedirectResponse:
    _require_google_oauth()
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/#home"
    request.session["oauth_next"] = safe_next
    redirect_uri = settings.google_redirect_uri or str(
        request.url_for("google_callback")
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback/google", name="google_callback", include_in_schema=False)
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_google_oauth()
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google login failed",
        ) from exc

    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.userinfo(token=token)

    email = str(userinfo.get("email") or "").strip().lower()
    if not email or userinfo.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified Google email is required",
        )

    display_name = str(userinfo.get("name") or "").strip() or None
    _sync_oauth_admin_user(db, email, display_name)

    next_url = request.session.get("oauth_next", "/#home")
    request.session.clear()
    request.session["user"] = {
        "email": email,
        "name": display_name,
        "picture": userinfo.get("picture"),
    }
    return RedirectResponse(str(next_url), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout", include_in_schema=False)
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/#home", status_code=status.HTTP_303_SEE_OTHER)


def _require_google_oauth() -> None:
    if settings.auth_mode != "google":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google authentication mode is not active",
        )
    if not settings.google_oauth_configured or oauth.google is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )


def _sync_oauth_admin_user(
    db: Session,
    email: str,
    display_name: str | None,
) -> None:
    is_allowlisted_super = email in settings.google_super_admin_email_set
    admin_user = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if admin_user is None:
        admin_user = AdminUser(
            email=email,
            display_name=display_name,
            is_super=is_allowlisted_super,
        )
        db.add(admin_user)
    else:
        admin_user.display_name = display_name or admin_user.display_name
        if is_allowlisted_super:
            admin_user.is_super = True
            admin_user.disabled_at = None
    db.commit()
