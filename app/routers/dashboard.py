from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_csrf_token, login_required
from app.models import CashSession, PaymentMethodEnum, Sale, User

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
):
    hoje = date.today()
    inicio_mes = date(hoje.year, hoje.month, 1)

    # KPIs do mês
    vendas_mes = session.exec(
        select(Sale)
        .join(CashSession)
        .where(CashSession.data >= inicio_mes)
    ).all()

    total_vendas_mes = sum(v.amount for v in vendas_mes)
    qtd_vendas_mes = len(vendas_mes)
    dias_mes = (hoje - inicio_mes).days + 1
    media_diaria = total_vendas_mes / dias_mes if dias_mes > 0 else 0
    ticket_medio = total_vendas_mes / qtd_vendas_mes if qtd_vendas_mes > 0 else 0

    # Top 10 produtos
    from collections import Counter
    produtos_counter = Counter(v.product_code for v in vendas_mes)
    top_produtos = [
        {"codigo": k, "qtd": v, "total": sum(venda.amount for venda in vendas_mes if venda.product_code == k)}
        for k, v in produtos_counter.most_common(10)
    ]

    # Ranking operadores
    operadores_stats: dict[int, dict[str, float]] = {}
    for venda in vendas_mes:
        if venda.operator_id not in operadores_stats:
            operadores_stats[venda.operator_id] = {"qtd": 0.0, "total": 0.0}
        operadores_stats[venda.operator_id]["qtd"] += 1
        operadores_stats[venda.operator_id]["total"] += venda.amount

    ranking_operadores: list[dict[str, object]] = []
    for op_id, stats in operadores_stats.items():
        operador = session.get(User, op_id)
        if operador:
            ranking_operadores.append({
                "nome": operador.full_name,
                "qtd": stats["qtd"],
                "total": stats["total"]
            })
    ranking_operadores.sort(key=lambda x: -float(x.get("total", 0)), reverse=False)  # type: ignore[arg-type]

    # Vendas por forma de pagamento
    vendas_por_forma = {
        "DINHEIRO": sum(v.amount for v in vendas_mes if v.payment_method == PaymentMethodEnum.DINHEIRO),
        "PIX": sum(v.amount for v in vendas_mes if v.payment_method == PaymentMethodEnum.PIX),
        "DEBITO": sum(v.amount for v in vendas_mes if v.payment_method == PaymentMethodEnum.DEBITO),
        "CREDITO": sum(v.amount for v in vendas_mes if v.payment_method == PaymentMethodEnum.CREDITO),
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "kpis": {
                "total_mes": total_vendas_mes,
                "qtd_vendas": qtd_vendas_mes,
                "media_diaria": media_diaria,
                "ticket_medio": ticket_medio,
            },
            "top_produtos": top_produtos,
            "ranking_operadores": ranking_operadores[:10],
            "vendas_por_forma": vendas_por_forma,
            "mes_referencia": inicio_mes.strftime("%B/%Y"),
            "csrf_token": get_csrf_token(request),
        },
    )
