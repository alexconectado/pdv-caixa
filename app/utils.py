from datetime import date, datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

BRT_TZNAME = "America/Sao_Paulo"


def format_brt(dt: datetime | None) -> str:
    if not dt:
        return ""
    # Se zoneinfo ou tzdata não estiverem disponíveis, faz fallback seguro
    try:
        if ZoneInfo is None:
            raise RuntimeError("zoneinfo indisponível")
        tz = ZoneInfo(BRT_TZNAME)  # pode lançar ZoneInfoNotFoundError sem tzdata
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt.strftime("%d/%m/%Y %H:%M")


def payment_label(method: object) -> str:
    """Converte PaymentMethodEnum/str para rótulo amigável em pt-BR.

    Aceita tanto PaymentMethodEnum quanto string.
    """
    value: str
    try:
        # Enum str -> usa .value
        value = str(getattr(method, "value", method))
    except Exception:
        value = str(method)
    key = value.upper()
    mapping = {
        "DINHEIRO": "Dinheiro",
        "PIX": "PIX",
        "DEBITO": "Débito",
        "CREDITO": "Crédito",
    }
    return mapping.get(key, value.title())


def format_date_br(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")
