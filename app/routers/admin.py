from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.hash import pbkdf2_sha256
from sqlmodel import Session, select

from app.db import get_session
from app.deps import admin_required, csrf_protect, get_csrf_token
from app.models import RoleEnum, User

router = APIRouter(prefix="/administracao")
templates = Jinja2Templates(directory="app/templates")


@router.get("/usuarios", response_class=HTMLResponse)
async def lista_usuarios(request: Request, user: User = Depends(admin_required), session: Session = Depends(get_session)):
    usuarios = session.exec(select(User)).all()
    return templates.TemplateResponse(
        "admin_users.html", {"request": request, "user": user, "usuarios": usuarios, "csrf_token": get_csrf_token(request)}
    )


@router.post("/usuarios/criar")
async def criar_usuario(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("operator"),
    active: bool = Form(True),
    csrf_token: str = Form(alias="_csrf"),
    user: User = Depends(admin_required),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    exists = session.exec(select(User).where(User.username == username)).first()
    if exists:
        return RedirectResponse("/administracao/usuarios", status_code=302)
    novo = User(
        username=username.strip(),
        full_name=full_name.strip(),
        password_hash=pbkdf2_sha256.hash(password),
        role=RoleEnum(role),
        active=active,
    )
    session.add(novo)
    session.commit()
    return RedirectResponse("/administracao/usuarios", status_code=302)
