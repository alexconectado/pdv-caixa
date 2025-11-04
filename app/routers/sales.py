from datetime import date, datetime
import pytz

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.deps import admin_required, csrf_protect, get_csrf_token, login_required
from passlib.hash import pbkdf2_sha256
from app.models import AuditLog, CashSession, PaymentMethodEnum, Sale, SaleCancellation, StatusEnum, User
from app.utils import format_brt, payment_label

router = APIRouter(prefix="/vendas")
templates = Jinja2Templates(directory="app/templates")


@router.get("/nova", response_class=HTMLResponse)
async def nova_venda_get(request: Request, user: User = Depends(login_required), session: Session = Depends(get_session)):
    tz = pytz.timezone("America/Sao_Paulo")
    hoje = datetime.now(tz).date()
    caixa = session.exec(select(CashSession).where(CashSession.data == hoje, CashSession.status == StatusEnum.open)).first()
    vendas: list[Sale] = []
    totais = None
    cancelados_ids: set[int] = set()
    if caixa:
        vendas = list(session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all())
        # cancelar: obter ids cancelados e filtrar totais
        cancelamentos = list(session.exec(select(SaleCancellation)).all())
        cancelados_ids = {c.sale_id for c in cancelamentos}
        total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO)
        total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX)
        total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO)
        total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO)
        # Excluir canceladas dos totais
        total_din -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.DINHEIRO)
        total_pix -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.PIX)
        total_deb -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.DEBITO)
        total_cred -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.CREDITO)
        totais = {"dinheiro": total_din, "pix": total_pix, "debito": total_deb, "credito": total_cred}
    return templates.TemplateResponse(
        "add_sale.html",
        {
            "request": request,
            "user": user,
            "caixa": caixa,
            "vendas": vendas,
            "totais": totais,
            "fmt_dt": format_brt,
            "payment_label": payment_label,
            "cancelados_ids": cancelados_ids,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/nova", response_class=HTMLResponse)
async def nova_venda_post(
    request: Request,
    product_code: str = Form(...),
    amount: str = Form(...),
    payment_method: str = Form(...),
    csrf_token: str = Form(alias="_csrf"),
    user: User = Depends(login_required),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    tz = pytz.timezone("America/Sao_Paulo")
    hoje = datetime.now(tz).date()
    caixa = session.exec(select(CashSession).where(CashSession.data == hoje, CashSession.status == StatusEnum.open)).first()
    if not caixa:
        # sem caixa aberto hoje
        return RedirectResponse("/caixa/status", status_code=302)

    # converte valor, aceitando vírgula ou ponto
    try:
        amount_val = round(float(str(amount).replace(',', '.').strip()), 2)
    except Exception:
        amount_val = None

    if not amount_val or amount_val <= 0:
        # retorna tela com erro
        vendas = session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all() if caixa else []
        total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO)
        total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX)
        total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO)
        total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO)
        totais = {"dinheiro": total_din, "pix": total_pix, "debito": total_deb, "credito": total_cred}
        return templates.TemplateResponse(
            "add_sale.html",
            {
                "request": request,
                "user": user,
                "caixa": caixa,
                "vendas": vendas,
                "totais": totais,
                "fmt_dt": format_brt,
                "payment_label": payment_label,
                "error": "Valor inválido. Use ponto ou vírgula como separador decimal.",
                "csrf_token": get_csrf_token(request),
            },
            status_code=400,
        )

    assert user.id is not None
    assert caixa.id is not None
    venda = Sale(
        product_code=product_code.strip(),
        amount=amount_val,
        payment_method=PaymentMethodEnum(payment_method),
        operator_id=int(user.id),
        cash_session_id=int(caixa.id),
    )
    session.add(venda)
    session.commit()

    # Se HTMX, devolve atualização de totais (target) + OOB para lista e aciona modal de impressão
    if request.headers.get("HX-Request"):
        vendas = session.exec(select(Sale).where(Sale.cash_session_id == caixa.id)).all()
        cancelamentos = list(session.exec(select(SaleCancellation)).all())
        cancelados_ids = {c.sale_id for c in cancelamentos}
        total_din = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DINHEIRO)
        total_pix = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.PIX)
        total_deb = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.DEBITO)
        total_cred = sum(v.amount for v in vendas if v.payment_method == PaymentMethodEnum.CREDITO)
        total_din -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.DINHEIRO)
        total_pix -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.PIX)
        total_deb -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.DEBITO)
        total_cred -= sum(v.amount for v in vendas if v.id in cancelados_ids and v.payment_method == PaymentMethodEnum.CREDITO)
        return templates.TemplateResponse(
            "partials/after_sale_updates.html",
            {
                "request": request,
                "totais": {"dinheiro": total_din, "pix": total_pix, "debito": total_deb, "credito": total_cred},
                "vendas": vendas,
                "recibo_url": f"/vendas/recibo/{venda.id}",
                "fmt_dt": format_brt,
                "payment_label": payment_label,
                "cancelados_ids": cancelados_ids,
            },
        )
    # Fallback sem HTMX: volta para lançar venda (mantém fluxo)
    return RedirectResponse("/vendas/nova", status_code=302)


@router.get("/cancelar/{venda_id}", response_class=HTMLResponse)
async def cancelar_venda_get(
    venda_id: int,
    request: Request,
    user: User = Depends(admin_required),
    session: Session = Depends(get_session),
):
    venda = session.get(Sale, venda_id)
    if not venda:
        return RedirectResponse("/vendas/nova", status_code=302)
    # Verifica se já foi cancelada
    existente = session.exec(select(SaleCancellation).where(SaleCancellation.sale_id == venda_id)).first()
    if existente:
        return RedirectResponse("/vendas/nova", status_code=302)
    return templates.TemplateResponse(
        "cancel_sale.html",
        {
            "request": request,
            "user": user,
            "venda": venda,
            "payment_label": payment_label,
            "fmt_dt": format_brt,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/cancelar/{venda_id}")
async def cancelar_venda_post(
    venda_id: int,
    request: Request,
    motivo: str = Form(...),
    senha: str = Form(...),
    csrf_token: str = Form(alias="_csrf"),
    user: User = Depends(admin_required),
    session: Session = Depends(get_session),
):
    csrf_protect(request, csrf_token)
    venda = session.get(Sale, venda_id)
    if not venda:
        return RedirectResponse("/vendas/nova", status_code=302)
    # Impede duplicidade
    existente = session.exec(select(SaleCancellation).where(SaleCancellation.sale_id == venda_id)).first()
    if existente:
        return RedirectResponse("/vendas/nova", status_code=302)
    # Confirma senha do admin logado
    usuario = session.get(User, user.id) if user.id else None
    if not usuario or not pbkdf2_sha256.verify(senha, usuario.password_hash):
        return templates.TemplateResponse(
            "cancel_sale.html",
            {
                "request": request,
                "user": user,
                "venda": venda,
                "payment_label": payment_label,
                "fmt_dt": format_brt,
                "error": "Senha inválida",
                "csrf_token": get_csrf_token(request),
            },
            status_code=400,
        )
    # Registra cancelamento
    assert user.id is not None
    cancel = SaleCancellation(sale_id=venda_id, reason=motivo.strip(), canceled_by_id=int(user.id))
    session.add(cancel)
    # Auditoria
    import json
    session.add(
        AuditLog(
            action="cancel_sale",
            entity_type="sale",
            entity_id=venda_id,
            user_id=int(user.id),
            details=json.dumps({
                "reason": motivo.strip(),
                "product_code": venda.product_code,
                "amount": venda.amount,
                "payment_method": str(venda.payment_method),
                "operator_id": venda.operator_id,
            }),
        )
    )
    session.commit()
    return RedirectResponse("/vendas/nova", status_code=302)


@router.get("/recibo/{venda_id}", response_class=HTMLResponse)
async def recibo_venda(venda_id: int, request: Request, user: User = Depends(login_required), session: Session = Depends(get_session)):
    venda = session.get(Sale, venda_id)
    if not venda:
        return RedirectResponse("/vendas/nova", status_code=302)
    # Caixa e responsáveis
    caixa = session.get(CashSession, venda.cash_session_id) if venda.cash_session_id else None
    opened_by_name = None
    if caixa:
        opened_user = session.get(User, caixa.opened_by_id) if caixa.opened_by_id else None
        opened_by_name = opened_user.full_name if opened_user else str(caixa.opened_by_id)
    return templates.TemplateResponse(
        "receipt_sale.html",
        {
            "request": request,
            "user": user,
            "venda": venda,
            "opened_by_name": opened_by_name,
            "payment_label": payment_label,
            "fmt_dt": format_brt,
            "csrf_token": get_csrf_token(request),
        },
    )


@router.post("/excluir/{venda_id}")
async def excluir_venda(venda_id: int, request: Request, user: User = Depends(admin_required), session: Session = Depends(get_session), csrf_token: str = Form(alias="_csrf")):
    csrf_protect(request, csrf_token)
    venda = session.get(Sale, venda_id)
    if venda:
        # Registra auditoria antes de excluir
        import json
        audit = AuditLog(
            action="delete_sale",
            entity_type="sale",
            entity_id=venda_id,
            user_id=int(user.id) if user.id else 0,
            details=json.dumps({
                "product_code": venda.product_code,
                "amount": venda.amount,
                "payment_method": str(venda.payment_method),
                "operator_id": venda.operator_id,
            })
        )
        session.add(audit)
        session.delete(venda)
        session.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse(status_code=200)
    return RedirectResponse("/vendas/nova", status_code=302)
