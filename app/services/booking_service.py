"""BookingService — criação de bookings a partir de orçamentos aprovados.

V4: create_from_quote() TAMBÉM cria a OS automaticamente via ServiceOrderService.
"""
from ..models.booking  import Booking
from ..models.quote    import Quote
from ..extensions      import db
from .financial_service import FinancialService
from ..utils import now_br


def _next_booking_number(company_id: int) -> str:
    year = now_br().year
    last = (Booking.query
            .filter_by(company_id=company_id)
            .filter(Booking.number.like(f"RES-{year}-%"))
            .order_by(Booking.id.desc())
            .first())
    seq = 1
    if last:
        try:
            seq = int(last.number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            pass
    return f"RES-{year}-{seq:04d}"


class BookingService:

    @staticmethod
    def create_from_quote(quote: Quote, user_id: int = None) -> Booking:
        """Cria Booking de orçamento aprovado e gera OS operacional automaticamente."""
        from . import service_order_service as sos  # import lazy para evitar circular

        booking = Booking(
            company_id   = quote.company_id,
            quote_id     = quote.id,
            client_id    = quote.client_id,
            number       = _next_booking_number(quote.company_id),
            status       = "confirmado",
            confirmed_at = now_br(),
        )
        db.session.add(booking)
        db.session.flush()

        # Atualiza status do orçamento
        quote.status = "reserva_confirmada"

        # Registros financeiros legacy
        FinancialService.create_for_booking(booking, quote)

        # ── V4: Gera OS operacional automaticamente ──────────────────────────
        os = sos.create_from_booking(booking, quote, user_id=user_id)

        db.session.commit()
        return booking
