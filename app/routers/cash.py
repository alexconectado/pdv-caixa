from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.deps import csrf_protect, get_csrf_token, login_required
from app.models import CashSession, PaymentMethodEnum, Sale, StatusEnum, User
from app.utils import format_brt

router = APIRouter(prefix="/caixa")
templates = Jinja2Templates(directory="app/templates")


@router.get("/status", response_class=HTMLResponse)
async def caixa_status(request: Request, user: User = Depends(login_required), session: Session = Depends(get_session)):
    today = date.today()
    aberto = session.exec(select(CashSession).where(CashSession.data == today, CashSession.status == StatusEnum.open)).first()
    return templates.TemplateResponse(
        "cash_status.html", {"request": request, "user": user, "aberto": aberto, "csrf_token": get_csrf_token(request)}
    )


@router.get("/abrir", response_class=HTMLResponse)
async def abrir_get(request: Request, user: User = Depends(login_required)):
    from datetime import date as _date
    return templates.TemplateResponse(
        "open_cash.html",
        {
            "request": request,
            "user": user,
            "error": None,
            "today": _date.today().isoformat(),
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/abrir")
async def abrir_post(
    request: Request,
    troco_inicial: float = Form(...),
    data: str = Form(...),
    csrf_token: str = Form(alias="_csrf"),
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    try:
        data_dt = datetime.strptime(data, "%Y-%m-%d").date()
    except Exception:
        return templates.TemplateResponse(
            "open_cash.html",
            {"request": request, "user": user, "error": "Data inválida", "today": data, "csrf_token": get_csrf_token(request)},
            status_code=400,
        )

    existente = session.exec(select(CashSession).where(CashSession.data == data_dt, CashSession.status == StatusEnum.open)).first()
    if existente:
        return templates.TemplateResponse(
            "open_cash.html",
            {
                "request": request,
                "user": user,
                "error": "Já existe um caixa aberto para esta data",
                "today": data,
                "csrf_token": get_csrf_token(request),
            },
            status_code=400,
        )

    assert user.id is not None
    caixa = CashSession(opened_by_id=int(user.id), data=data_dt, opening_amount=troco_inicial)
    session.add(caixa)
    session.commit()
    return RedirectResponse("/caixa/status", status_code=302)


@router.get("/fechar", response_class=HTMLResponse)
async def fechar_get(request: Request, user: User = Depends(login_required), session: Session = Depends(get_session)):
    today = date.today()
    caixa = session.exec(select(CashSession).where(CashSession.data == today, CashSession.status == StatusEnum.open)).first()
    if not caixa:
        return RedirectResponse("/caixa/status", status_code=302)

    # calcula totais esperados por forma de pagamento
    vendas = session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all()
    # Excluir canceladas
    from app.models import SaleCancellation
    cancelados = {c.sale_id for c in session.exec(select(SaleCancellation)).all()}
    total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO and v.id not in cancelados)
    total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX and v.id not in cancelados)
    total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO and v.id not in cancelados)
    total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO and v.id not in cancelados)
    esperado_gaveta = caixa.opening_amount + total_din

    return templates.TemplateResponse(
        "close_cash.html",
        {
            "request": request,
            "user": user,
            "caixa": caixa,
            "totais": {
                "dinheiro": total_din,
                "pix": total_pix,
                "debito": total_deb,
                "credito": total_cred,
                "gaveta": esperado_gaveta,
            },
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/fechar")
async def fechar_post(
    request: Request,
    gaveta: float = Form(...),
    pix: float = Form(...),
    debito: float = Form(...),
    credito: float = Form(...),
    csrf_token: str = Form(alias="_csrf"),
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    today = date.today()
    caixa = session.exec(select(CashSession).where(CashSession.data == today, CashSession.status == StatusEnum.open)).first()
    if not caixa:
        return RedirectResponse("/caixa/status", status_code=302)

    vendas = session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all()
    from app.models import SaleCancellation
    cancelados = {c.sale_id for c in session.exec(select(SaleCancellation)).all()}
    total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO and v.id not in cancelados)
    total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX and v.id not in cancelados)
    total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO and v.id not in cancelados)
    total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO and v.id not in cancelados)
    esperado_gaveta = caixa.opening_amount + total_din

    caixa.reported_cash_drawer = gaveta
    caixa.reported_pix_total = pix
    caixa.reported_debit_total = debito
    caixa.reported_credit_total = credito

    caixa.diff_cash = round(esperado_gaveta - gaveta, 2)
    caixa.diff_pix = round(total_pix - pix, 2)
    caixa.diff_debit = round(total_deb - debito, 2)
    caixa.diff_credit = round(total_cred - credito, 2)
    caixa.diff_overall = round(
        (esperado_gaveta + total_pix + total_deb + total_cred) - (gaveta + pix + debito + credito), 2
    )
    caixa.status = StatusEnum.closed
    caixa.closed_at = datetime.utcnow()

    session.add(caixa)
    session.commit()

    return RedirectResponse(f"/caixa/comprovante-fechamento/{caixa.id}", status_code=302)


@router.get("/comprovante-fechamento/{caixa_id}", response_class=HTMLResponse)
async def comprovante_fechamento(caixa_id: int, request: Request, user: User = Depends(login_required), session: Session = Depends(get_session)):
    caixa = session.get(CashSession, caixa_id)
    if not caixa:
        return RedirectResponse("/caixa/status", status_code=302)

    vendas = session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all()
    from app.models import SaleCancellation
    cancelados = {c.sale_id for c in session.exec(select(SaleCancellation)).all()}
    total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO and v.id not in cancelados)
    total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX and v.id not in cancelados)
    total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO and v.id not in cancelados)
    total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO and v.id not in cancelados)
    esperado_gaveta = caixa.opening_amount + total_din

    # Identifica usuários
    opened_by = session.get(User, caixa.opened_by_id) if caixa.opened_by_id else None
    opened_by_name = opened_by.full_name if opened_by else str(caixa.opened_by_id)
    closed_by_name = user.full_name  # melhor esforço: usuário que está emitindo/fechou

    return templates.TemplateResponse(
        "receipt_close.html",
        {
            "request": request,
            "user": user,
            "caixa": caixa,
            "totais": {
                "dinheiro": total_din,
                "pix": total_pix,
                "debito": total_deb,
                "credito": total_cred,
                "gaveta": esperado_gaveta,
            },
            "opened_by_name": opened_by_name,
            "closed_by_name": closed_by_name,
            "fmt_dt": format_brt,
            "csrf_token": get_csrf_token(request),
        },
    )
