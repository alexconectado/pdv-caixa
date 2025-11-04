from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class PaymentMethodEnum(str, Enum):
    DINHEIRO = "DINHEIRO"
    PIX = "PIX"
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"


class RoleEnum(str, Enum):
    admin = "admin"
    operator = "operator"


class StatusEnum(str, Enum):
    open = "open"
    closed = "closed"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    password_hash: str
    role: RoleEnum = Field(default=RoleEnum.operator, index=True)
    active: bool = Field(default=True)


class CashSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    opened_by_id: int = Field(foreign_key="user.id")
    data: date = Field(index=True)
    opening_amount: float = Field(default=0.0)
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # fechamento
    closed_at: Optional[datetime] = None
    status: StatusEnum = Field(default=StatusEnum.open, index=True)

    # valores informados no fechamento
    reported_cash_drawer: Optional[float] = None
    reported_pix_total: Optional[float] = None
    reported_debit_total: Optional[float] = None
    reported_credit_total: Optional[float] = None

    # diferenças calculadas no fechamento (esperado - informado)
    diff_cash: Optional[float] = None
    diff_pix: Optional[float] = None
    diff_debit: Optional[float] = None
    diff_credit: Optional[float] = None
    diff_overall: Optional[float] = None

    # Relacionamentos removidos para simplificar o mapeamento


class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_code: str
    amount: float
    payment_method: PaymentMethodEnum
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    operator_id: int = Field(foreign_key="user.id")
    cash_session_id: int = Field(foreign_key="cashsession.id")

    # Relacionamentos removidos para simplificar o mapeamento


class AuditLog(SQLModel, table=True):
    """Log de auditoria para rastrear ações importantes no sistema."""
    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(index=True)  # "delete_sale", "close_cash", "create_user", etc
    entity_type: str  # "sale", "cash_session", "user"
    entity_id: Optional[int] = None
    user_id: int = Field(foreign_key="user.id")
    details: Optional[str] = None  # JSON ou texto com detalhes da ação
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class SaleCancellation(SQLModel, table=True):
    """Registro de cancelamento de vendas (mantém venda original, mas marca como cancelada)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: int = Field(foreign_key="sale.id", index=True)
    reason: str
    canceled_by_id: int = Field(foreign_key="user.id")
    canceled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
