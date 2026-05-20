"""Template helpers — filtros Jinja2 e funções de formatação."""
from datetime import date, datetime


def format_currency(value, symbol="R$") -> str:
    """Formata valor numérico como moeda brasileira."""
    try:
        return f"{symbol} {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return f"{symbol} 0,00"


def format_date(value, fmt="%d/%m/%Y") -> str:
    """Formata date/datetime para string BR."""
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime(fmt)
    return str(value)


def format_datetime(value, fmt="%d/%m/%Y %H:%M") -> str:
    return format_date(value, fmt)


def billing_label(billing_type: str) -> str:
    labels = {
        "recibo":    "Recibo",
        "nf":        "Nota Fiscal",
        "cartao":    "Cartão",
        "nf_cartao": "NF + Cartão",
    }
    return labels.get(billing_type, billing_type or "")


def status_badge_class(status: str) -> str:
    """Retorna classes Tailwind para badges de status de OS."""
    classes = {
        "criado":             "bg-slate-100 text-slate-700",
        "agendado":           "bg-blue-100 text-blue-700",
        "atribuido":          "bg-violet-100 text-violet-700",
        "confirmado_cliente": "bg-cyan-100 text-cyan-700",
        "em_execucao":        "bg-amber-100 text-amber-700",
        "finalizado":         "bg-green-100 text-green-700",
        "cancelado":          "bg-red-100 text-red-700",
        # quote/booking statuses
        "pendente":            "bg-yellow-100 text-yellow-700",
        "aprovado":            "bg-green-100 text-green-700",
        "reprovado":           "bg-red-100 text-red-700",
        "pago":                "bg-emerald-100 text-emerald-700",
        "reserva_confirmada":  "bg-teal-100 text-teal-700",
        "concluido":           "bg-green-200 text-green-800",
        # Order statuses
        "novo":                "bg-sky-100 text-sky-700",
        "aberto":              "bg-blue-100 text-blue-700",
        "faturado":            "bg-amber-100 text-amber-700",
        "fechado":             "bg-emerald-100 text-emerald-700",
    }
    return classes.get(status, "bg-gray-100 text-gray-700")
