"""FinancialService — registros financeiros legacy."""
from ..models.financial import FinancialRecord, AccountReceivable
from ..extensions import db


class FinancialService:

    @staticmethod
    def create_for_booking(booking, quote):
        """Cria registro de receita + conta a receber ao confirmar booking."""
        rev = FinancialRecord(
            company_id  = booking.company_id,
            booking_id  = booking.id,
            quote_id    = quote.id,
            type        = "revenue",
            category    = "receita_servico",
            description = f"Receita – {booking.number} / {quote.number}",
            amount      = quote.total_amount,
            status      = "pendente",
        )
        db.session.add(rev)

        ar = AccountReceivable(
            company_id = booking.company_id,
            booking_id = booking.id,
            quote_id   = quote.id,
            client_id  = quote.client_id,
            amount     = quote.total_amount,
            status     = "pendente",
        )
        db.session.add(ar)
        db.session.flush()
