import os
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

# Ensure test DB
os.environ["DATABASE_URL"] = "sqlite:///./pdv_test.db"

from app.db import create_default_admin, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    create_default_admin()
    yield


def _get_csrf_token(html: str) -> str:
    m = re.search(r'name="_csrf"\s+value="([^"]+)"', html)
    assert m, "CSRF não encontrado no HTML"
    return m.group(1)


def test_login_open_cash_and_sale_htmx():
    client = TestClient(app)

    # GET login
    r = client.get("/entrar")
    assert r.status_code == 200
    csrf = _get_csrf_token(r.text)

    # POST login
    r = client.post("/entrar", data={"username": "admin", "password": "admin123", "_csrf": csrf}, allow_redirects=False)
    assert r.status_code in (302, 303)

    # Abrir caixa de hoje
    r = client.get("/caixa/abrir")
    assert r.status_code == 200
    csrf = _get_csrf_token(r.text)

    r = client.post(
        "/caixa/abrir",
        data={"troco_inicial": "100", "data": date.today().isoformat(), "_csrf": csrf},
        allow_redirects=False,
    )
    # Pode retornar 400 se já aberto; seguimos
    assert r.status_code in (200, 302, 400)

    # GET vendas nova
    r = client.get("/vendas/nova")
    assert r.status_code == 200
    csrf = _get_csrf_token(r.text)

    # POST venda via HTMX
    headers = {"HX-Request": "true"}
    r = client.post(
        "/vendas/nova",
        data={
            "product_code": "TESTE001",
            "amount": "10,50",
            "payment_method": "DINHEIRO",
            "_csrf": csrf,
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert "Totais" in r.text

    # Ver recibo (redirect via GET normal)
    # Buscar ID da venda na página de relatórios
    rr = client.get("/relatorios")
    assert rr.status_code == 200
    # Deve conter link de recibo ou pelo menos a área "Vendas do Dia"
    assert "Vendas do Dia" in rr.text
