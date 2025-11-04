import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.db import get_session
from app.models import User


def get_current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = session.exec(select(User).where(User.id == user_id)).first()
    return user


def login_required(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/entrar"})
    if not user.active:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    return user


def admin_required(user: User = Depends(login_required)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return user


def get_csrf_token(request: Request) -> str:
    token = request.session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["_csrf"] = token
    return token


def csrf_protect(request: Request, token: str) -> None:
    session_token = request.session.get("_csrf")
    if not session_token or not token or not secrets.compare_digest(session_token, token):
        raise HTTPException(status_code=400, detail="Falha de verificação CSRF")
