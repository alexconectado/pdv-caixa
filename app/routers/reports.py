from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_csrf_token, login_required
from app.models import CashSession, PaymentMethodEnum, Sale, SaleCancellation, StatusEnum, User
from app.utils import format_brt, format_date_br, payment_label

router = APIRouter(prefix="/relatorios")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def relatorios_index(
    request: Request,
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
    data_inicio: str | None = Query(default=None),
    data_fim: str | None = Query(default=None),
):
    # período no formato YYYY-MM-DD; default hoje->hoje
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else date.today()
    except Exception:
        dt_inicio = date.today()
    try:
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else dt_inicio
    except Exception:
        dt_fim = dt_inicio

    # Recupera caixas no período (inclusive)
    caixas = list(session.exec(select(CashSession).where(CashSession.data >= dt_inicio, CashSession.data <= dt_fim)).all())
    caixa_unico = caixas[0] if len(caixas) == 1 else None

    # Vendas do período
    vendas: list[Sale] = []
    if caixas:
        ids = [c.id for c in caixas if c.id]
        if ids:
            # Busca todas e filtra em memória (simples e suficiente para este PDV)
            vendas_todas = list(session.exec(select(Sale)).all())
            vendas = [v for v in vendas_todas if v.cash_session_id in ids]

    # Cancelamentos
    cancelamentos = list(session.exec(select(SaleCancellation)).all())
    cancelados_ids: set[int] = {c.sale_id for c in cancelamentos}

    # KPIs do período
    vendas_validas = [v for v in vendas if v.id not in cancelados_ids]
    total_geral = sum(v.amount for v in vendas_validas)
    qtd_vendas = len(vendas_validas)
    dias = (dt_fim - dt_inicio).days + 1
    media_diaria = (total_geral / dias) if dias > 0 else 0.0
    ticket_medio = (total_geral / qtd_vendas) if qtd_vendas > 0 else 0.0

    total_din = sum(v.amount for v in vendas_validas if v.payment_method == PaymentMethodEnum.DINHEIRO)
    total_pix = sum(v.amount for v in vendas_validas if v.payment_method == PaymentMethodEnum.PIX)
    total_deb = sum(v.amount for v in vendas_validas if v.payment_method == PaymentMethodEnum.DEBITO)
    total_cred = sum(v.amount for v in vendas_validas if v.payment_method == PaymentMethodEnum.CREDITO)

    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "user": user,
            "dt_inicio": dt_inicio,
            "dt_fim": dt_fim,
            "caixa": caixa_unico,
            "caixas": caixas,
            "vendas": vendas,
            "totais": {
                "geral": total_geral,
                "qtd": qtd_vendas,
                "media_diaria": media_diaria,
                "ticket_medio": ticket_medio,
                "dinheiro": total_din,
                "pix": total_pix,
                "debito": total_deb,
                "credito": total_cred,
            },
            "fmt_dt": format_brt,
            "fmt_date": format_date_br,
            "payment_label": payment_label,
            "cancelados_ids": cancelados_ids,
            "csrf_token": get_csrf_token(request),
        },
    )
