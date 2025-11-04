import os
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.db import create_default_admin, init_db
from app.routers import admin, audit, auth, cash, dashboard, reports, sales

app = FastAPI(title="PDV Caixa Diário")

# Session - usa SECRET_KEY do ambiente (gera chave efêmera se ausente)
secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    session_cookie="pdv_session",
    same_site="lax",
    https_only=False,
)

# Static
# Resolve o caminho da pasta 'static' relativo a este arquivo e não falha se ausente
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="static")

# Routers
app.include_router(auth.router)
app.include_router(cash.router)
app.include_router(sales.router)
app.include_router(admin.router)
app.include_router(reports.router)  # Relatórios simples (compatibilidade)
app.include_router(dashboard.router)
app.include_router(audit.router)


@app.on_event("startup")
async def startup_event():
    init_db()
    create_default_admin()


@app.get("/")
async def root(request: Request):
    # Redireciona para painel (que exige login)
    return RedirectResponse(url="/painel")
