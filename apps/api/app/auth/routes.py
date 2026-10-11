from app.auth.service import (
    DUMMY_HASH,
    Principal,
    audit,
    establish_session,
    passwords,
    rate_limit,
    require_user,
)
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.models import Library, Session, User
from app.schemas import Login, PasswordChange
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession
from starlette.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth = OAuth()
if settings.oidc_issuer:
    oauth.register(
        "oidc",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        server_metadata_url=settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )


@router.get("/options")
def options():
    return {"password": True, "oidc": False}


@router.post("/login")
def login(data: Login, request: Request, response: Response, db: DBSession = Depends(get_db)):
    rate_limit(f"login:{request.client.host}", 10, 300)
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    valid = passwords.verify(data.password, user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not user or not user.password_hash or not valid:
        problem(401, "INVALID_CREDENTIALS", "メールアドレスまたはパスワードを確認してください。")
    establish_session(db, user, response)
    return {"id": user.id, "name": user.name, "email": user.email}


@router.get("/me")
def me(p: Principal = Depends(require_user)):
    return {"id": p.user.id, "name": p.user.name, "email": p.user.email, "library_id": p.library.id}


@router.post("/logout", status_code=204)
def logout(response: Response, p: Principal = Depends(require_user), db: DBSession = Depends(get_db)):
    db.delete(p.session)
    audit(db, p.user.id, "auth.logout")
    db.commit()
    response.delete_cookie("lumvia_session", path="/")
    response.delete_cookie("lumvia_csrf", path="/")


@router.post("/password", status_code=204)
def password(data: PasswordChange, p: Principal = Depends(require_user), db: DBSession = Depends(get_db)):
    rate_limit(f"password:{p.user.id}", 5, 300)
    if not p.user.password_hash or not passwords.verify(data.current_password, p.user.password_hash):
        problem(400, "PASSWORD_INVALID", "現在のパスワードを確認してください。")
    p.user.password_hash = passwords.hash(data.new_password)
    db.execute(delete(Session).where(Session.user_id == p.user.id, Session.id != p.session.id))
    audit(db, p.user.id, "auth.password_changed")
    db.commit()


@router.get("/oidc/login")
async def oidc_login(request: Request):
    if not settings.oidc_issuer:
        problem(404, "OIDC_UNAVAILABLE", "外部ログインは設定されていません。")
    return await oauth.oidc.authorize_redirect(request, settings.app_url + "/api/v1/auth/oidc/callback")


@router.get("/oidc/callback")
async def oidc_callback(request: Request, db: DBSession = Depends(get_db)):
    if not settings.oidc_issuer:
        problem(404, "OIDC_UNAVAILABLE", "外部ログインは設定されていません。")
    try:
        token = await oauth.oidc.authorize_access_token(request)
        info = token["userinfo"]
        email = info.get("email", "").lower()
        allowed = {d.strip().lower() for d in settings.oidc_allowed_domains.split(",") if d.strip()}
        if (
            not info.get("email_verified")
            or "@" not in email
            or not allowed
            or email.split("@")[-1] not in allowed
        ):
            problem(403, "ACCOUNT_NOT_ALLOWED", "このアカウントではログインできません。")
        subject = settings.oidc_issuer + "|" + info["sub"]
        user = db.scalar(select(User).where(User.oidc_subject == subject))
        if not user:
            # Never auto-link a local account merely because its email matches.
            if db.scalar(select(User).where(User.email == email)):
                problem(409, "ACCOUNT_EXISTS", "管理者にアカウントの連携を依頼してください。")
            user = User(email=email, name=info.get("name", email)[:100], oidc_subject=subject)
            db.add(user)
            db.flush()
            db.add(Library(owner_id=user.id))
        response = RedirectResponse("/", status_code=303)
        establish_session(db, user, response)
        return response
    except (KeyError, ValueError):
        problem(400, "OIDC_INVALID", "ログインを完了できませんでした。もう一度お試しください。")
