from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.deps import admin_required, get_csrf_token
from app.models import AuditLog, User
from app.utils import format_brt

router = APIRouter(prefix="/auditoria", tags=["audit"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def auditoria_index(
    request: Request,
    user: User = Depends(admin_required),
    session: Session = Depends(get_session),
    usuario_id: int | None = Query(default=None),
    data_inicio: str | None = Query(default=None),
    data_fim: str | None = Query(default=None),
):
    """Página de auditoria - apenas para admins"""
    # Parse de datas
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
    except Exception:
        dt_inicio = None

    try:
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else None
    except Exception:
        dt_fim = None

    # Query base (sem ordenação aqui; ordenaremos em memória para evitar problemas de compatibilidade)
    query = select(AuditLog)

    # Aplica filtros
    if usuario_id:
        query = query.where(AuditLog.user_id == usuario_id)

    if dt_inicio:
        query = query.where(AuditLog.created_at >= datetime.combine(dt_inicio, datetime.min.time()))

    if dt_fim:
        query = query.where(AuditLog.created_at <= datetime.combine(dt_fim, datetime.max.time()))

    # Busca e ordena em memória por created_at desc
    logs = list(session.exec(query).all())
    logs.sort(key=lambda l: l.created_at, reverse=True)
    logs = logs[:100]

    # Lista de usuários para filtro
    usuarios = list(session.exec(select(User)).all())

    # Enriquecer logs com nomes de usuários
    logs_enriched = []
    for log in logs:
        usuario = session.get(User, log.user_id)
        logs_enriched.append({
            "log": log,
            "usuario_nome": usuario.full_name if usuario else f"ID {log.user_id}"
        })

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "user": user,
            "logs": logs_enriched,
            "usuarios": usuarios,
            "usuario_id": usuario_id,
            "data_inicio": data_inicio or "",
            "data_fim": data_fim or "",
            "fmt_dt": format_brt,
            "csrf_token": get_csrf_token(request),
        },
    )
