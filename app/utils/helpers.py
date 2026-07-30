"""Template helpers — filtros Jinja2 e funções de formatação."""
from datetime import date, datetime
import re


def parse_brl(value) -> float:
    """Converte string monetária para float.

    Lida com todos os formatos comuns:
    - "1.500,50"  (BR com separador de milhar) → 1500.5
    - "1500,50"   (BR sem milhar)              → 1500.5
    - "1500.50"   (internacional)              → 1500.5
    - 1500.50     (float/int nativo)           → 1500.5
    - "R$ 1.500,50" (com símbolo)             → 1500.5
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return 0.0

    # Remove símbolos comuns (R$, espaços)
    s = s.replace("R$", "").replace(" ", "")

    # Detecta padrão pelo último separador
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")

    if last_comma > last_dot:
        # Padrão brasileiro: último separador é vírgula (decimal)
        # Remove pontos (milhar) e troca vírgula por ponto
        s = s.replace(".", "").replace(",", ".")
    elif last_dot >= 0:
        # Padrão internacional ou digitado com ponto decimal
        # Se tiver mais de um ponto, assume que o último é decimal
        dot_count = s.count(".")
        if dot_count > 1:
            # Ex: "21.600.00" → último ponto é decimal, anteriores são milhar
            parts = s.rsplit(".", 1)
            s = parts[0].replace(".", "") + "." + parts[1]
        # Remove vírgulas (milhar)
        s = s.replace(",", "")

    # Remove caracteres não numéricos restantes (exceto . e -)
    s = re.sub(r'[^\d.\-]', '', s)

    if not s or s in (".", "-", "-."):
        return 0.0

    return float(s)


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
        "excluido":            "bg-slate-100 text-slate-500",
    }
    return classes.get(status, "bg-gray-100 text-gray-700")


# Professional status badge — (bg, text, border, dot)
_STATUS_BADGE_PALETTE: dict[str, tuple[str, str, str, str]] = {
    "pendente":            ("#fef9c3", "#854d0e", "#fde047", "#ca8a04"),
    "aprovado":            ("#dcfce7", "#14532d", "#4ade80", "#16a34a"),
    "reprovado":           ("#fee2e2", "#7f1d1d", "#f87171", "#dc2626"),
    "pago":                ("#d1fae5", "#064e3b", "#34d399", "#059669"),
    "novo":                ("#e0f2fe", "#0c4a6e", "#38bdf8", "#0284c7"),
    "aberto":              ("#dbeafe", "#1e3a8a", "#60a5fa", "#2563eb"),
    "enviado":             ("#dbeafe", "#1e3a8a", "#60a5fa", "#2563eb"),
    "faturado":            ("#ffedd5", "#7c2d12", "#fb923c", "#ea580c"),
    "fechado":             ("#d1fae5", "#064e3b", "#34d399", "#059669"),
    "cancelado":           ("#fee2e2", "#7f1d1d", "#f87171", "#dc2626"),
    "excluido":            ("#f1f5f9", "#64748b", "#cbd5e1", "#94a3b8"),
    "criado":              ("#f1f5f9", "#334155", "#94a3b8", "#64748b"),
    "agendado":            ("#dbeafe", "#1e3a8a", "#60a5fa", "#2563eb"),
    "atribuido":           ("#ede9fe", "#4c1d95", "#a78bfa", "#7c3aed"),
    "confirmado_cliente":  ("#cffafe", "#164e63", "#22d3ee", "#0891b2"),
    "em_execucao":         ("#fef3c7", "#78350f", "#fcd34d", "#d97706"),
    "finalizado":          ("#dcfce7", "#14532d", "#4ade80", "#16a34a"),
    "concluido":           ("#d1fae5", "#064e3b", "#34d399", "#059669"),
    "reserva_confirmada":  ("#ccfbf1", "#134e4a", "#2dd4bf", "#0d9488"),
    "rascunho":            ("#f8fafc", "#475569", "#e2e8f0", "#94a3b8"),
}
_STATUS_BADGE_DEFAULT = ("#f1f5f9", "#334155", "#cbd5e1", "#64748b")


def status_badge_style(status: str) -> str:
    """Retorna inline CSS para badge de status profissional."""
    bg, color, border, _ = _STATUS_BADGE_PALETTE.get(status, _STATUS_BADGE_DEFAULT)
    return (
        f"display:inline-flex;align-items:center;gap:5px;"
        f"padding:3px 10px 3px 8px;border-radius:20px;"
        f"font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;"
        f"border:1.5px solid {border};background:{bg};color:{color};"
        f"box-shadow:0 1px 3px rgba(0,0,0,.08);white-space:nowrap;vertical-align:middle;"
    )


def status_dot_color(status: str) -> str:
    """Retorna cor hex do indicador dot para o status."""
    _, _, _, dot = _STATUS_BADGE_PALETTE.get(status, _STATUS_BADGE_DEFAULT)
    return dot
