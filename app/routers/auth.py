from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.hash import pbkdf2_sha256
from sqlmodel import Session, select

from app.db import get_session
from app.deps import csrf_protect, get_csrf_token, login_required
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/entrar", response_class=HTMLResponse)
async def entrar_get(request: Request):
    csrf = get_csrf_token(request)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "csrf_token": csrf})


@router.post("/entrar")
async def entrar_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(alias="_csrf"),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not pbkdf2_sha256.verify(password, user.password_hash) or not user.active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuário ou senha inválidos", "csrf_token": get_csrf_token(request)},
            status_code=400,
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/painel", status_code=302)


@router.post("/sair")
async def sair(request: Request, csrf_token: str = Form(alias="_csrf")):
    csrf_protect(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/entrar", status_code=302)


@router.get("/painel", response_class=HTMLResponse)
async def painel(request: Request, user: User = Depends(login_required)):
    # Redireciona para Relatórios (página principal após login)
    return RedirectResponse(url="/relatorios/", status_code=302)
