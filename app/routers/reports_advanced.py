import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_csrf_token, login_required
from app.models import CashSession, PaymentMethodEnum, Sale, StatusEnum, User
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
    operador_id: int | None = Query(default=None),
    forma_pagamento: str | None = Query(default=None),
    status_caixa: str | None = Query(default=None),
):
    """Relatórios com filtros avançados."""
    # Parse datas
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else date.today()
    except Exception:
        dt_inicio = date.today()

    try:
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else dt_inicio
    except Exception:
        dt_fim = dt_inicio

    # Busca caixas no período
    query_caixas = select(CashSession).where(
        CashSession.data >= dt_inicio,
        CashSession.data <= dt_fim
    )

    if status_caixa:
        query_caixas = query_caixas.where(CashSession.status == StatusEnum(status_caixa))

    caixas = session.exec(query_caixas).all()
    caixas_ids = [c.id for c in caixas if c.id]

    # Busca vendas
    vendas: list[Sale] = []
    if caixas_ids:
        # Busca todas as vendas e filtra em memória (simples e funcional para PDV)
        vendas_todas = list(session.exec(select(Sale)).all())
        vendas = [v for v in vendas_todas if v.cash_session_id in caixas_ids]

        if operador_id:
            vendas = [v for v in vendas if v.operator_id == operador_id]

        if forma_pagamento:
            vendas = [v for v in vendas if v.payment_method == PaymentMethodEnum(forma_pagamento)]

    # Totais
    total_geral = sum(v.amount for v in vendas)
    total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO)
    total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX)
    total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO)
    total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO)

    totais = {
        "geral": total_geral,
        "dinheiro": total_din,
        "pix": total_pix,
        "debito": total_deb,
        "credito": total_cred,
        "qtd_vendas": len(vendas),
    }

    # Lista de operadores para filtro
    operadores = session.exec(select(User)).all()

    return templates.TemplateResponse(
        "reports_advanced.html",
        {
            "request": request,
            "user": user,
            "dt_inicio": dt_inicio,
            "dt_fim": dt_fim,
            "vendas": vendas,
            "totais": totais,
            "operadores": operadores,
            "filtro_operador_id": operador_id,
            "filtro_forma": forma_pagamento,
            "filtro_status": status_caixa,
            "fmt_dt": format_brt,
            "fmt_date": format_date_br,
            "payment_label": payment_label,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.get("/exportar/csv")
async def exportar_csv(
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
    data_inicio: str | None = Query(default=None),
    data_fim: str | None = Query(default=None),
    operador_id: int | None = Query(default=None),
    forma_pagamento: str | None = Query(default=None),
):
    """Exporta relatório em CSV."""
    # Parse datas
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else date.today()
    except Exception:
        dt_inicio = date.today()

    try:
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else dt_inicio
    except Exception:
        dt_fim = dt_inicio

    # Busca vendas (mesma lógica do relatório)
    query_caixas = select(CashSession).where(
        CashSession.data >= dt_inicio,
        CashSession.data <= dt_fim
    )
    caixas = session.exec(query_caixas).all()
    caixas_ids = [c.id for c in caixas if c.id]

    vendas: list[Sale] = []
    if caixas_ids:
        vendas_todas = list(session.exec(select(Sale)).all())
        vendas = [v for v in vendas_todas if v.cash_session_id in caixas_ids]

        if operador_id:
            vendas = [v for v in vendas if v.operator_id == operador_id]

        if forma_pagamento:
            vendas = [v for v in vendas if v.payment_method == PaymentMethodEnum(forma_pagamento)]

    # Gera CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Data/Hora", "Código Produto", "Valor", "Forma Pagamento", "Operador ID"])

    for venda in vendas:
        writer.writerow([
            venda.id,
            format_brt(venda.created_at),
            venda.product_code,
            f"{venda.amount:.2f}",
            payment_label(venda.payment_method),
            venda.operator_id,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{dt_inicio}_a_{dt_fim}.csv"}
    )


@router.get("/exportar/pdf")
async def exportar_pdf(
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
    data_inicio: str | None = Query(default=None),
    data_fim: str | None = Query(default=None),
    operador_id: int | None = Query(default=None),
    forma_pagamento: str | None = Query(default=None),
):
    """Exporta relatório em PDF."""
    # Parse datas
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else date.today()
    except Exception:
        dt_inicio = date.today()

    try:
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else dt_inicio
    except Exception:
        dt_fim = dt_inicio

    # Busca vendas
    query_caixas = select(CashSession).where(
        CashSession.data >= dt_inicio,
        CashSession.data <= dt_fim
    )
    caixas = session.exec(query_caixas).all()
    caixas_ids = [c.id for c in caixas if c.id]

    vendas: list[Sale] = []
    if caixas_ids:
        vendas_todas = list(session.exec(select(Sale)).all())
        vendas = [v for v in vendas_todas if v.cash_session_id in caixas_ids]

        if operador_id:
            vendas = [v for v in vendas if v.operator_id == operador_id]

        if forma_pagamento:
            vendas = [v for v in vendas if v.payment_method == PaymentMethodEnum(forma_pagamento)]

    # Totais
    total_geral = sum(v.amount for v in vendas)

    # Gera PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    # Título
    title = Paragraph(f"<b>Relatório de Vendas</b><br/>Período: {format_date_br(dt_inicio)} a {format_date_br(dt_fim)}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.5*cm))

    # Tabela de vendas
    data_table = [["ID", "Data/Hora", "Produto", "Valor", "Pagamento"]]
    for venda in vendas:
        data_table.append([
            str(venda.id),
            format_brt(venda.created_at),
            venda.product_code[:15],
            f"R$ {venda.amount:.2f}",
            payment_label(venda.payment_method),
        ])

    # Total
    data_table.append(["", "", "", f"R$ {total_geral:.2f}", ""])

    table = Table(data_table, colWidths=[1.5*cm, 4*cm, 4*cm, 3*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
    ]))

    story.append(table)
    doc.build(story)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{dt_inicio}_a_{dt_fim}.pdf"}
    )
