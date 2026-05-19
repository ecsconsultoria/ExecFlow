"""models/__init__.py — importa todos os modelos para que o SQLAlchemy os registre."""

from .base         import TimestampMixin, SoftDeleteMixin
from .audit        import AuditLog
from .company      import Company
from .user         import User
from .client       import Client
from .supplier     import Supplier
from .driver       import Driver
from .vehicle      import VehicleCategory, Vehicle
from .service      import State, Service, ServicePricing
from .quote        import Quote, QuoteItem, BILLING_TYPES, QUOTE_STATUSES
from .booking      import Booking, BOOKING_STATUSES
from .financial    import FinancialRecord, AccountReceivable

# V4 — novos modelos operacionais
from .service_order            import ServiceOrder, OS_STATUSES
from .service_order_assignment import ServiceOrderAssignment, ASSIGNMENT_TYPES
from .service_order_event      import ServiceOrderEvent, EVENT_TYPES
from .operation_cost           import OperationCost, COST_TYPES, COST_TYPE_LABELS
from .revenue_entry            import RevenueEntry, REVENUE_STATUSES
from .supplier_payment         import SupplierPayment, PAYMENT_STATUSES
from .financial_entry          import FinancialEntry, ENTRY_TYPES

__all__ = [
    "TimestampMixin", "SoftDeleteMixin",
    "AuditLog",
    "Company",
    "User",
    "Client",
    "Supplier",
    "Driver",
    "VehicleCategory", "Vehicle",
    "State", "Service", "ServicePricing",
    "Quote", "QuoteItem", "BILLING_TYPES", "QUOTE_STATUSES",
    "Booking", "BOOKING_STATUSES",
    "FinancialRecord", "AccountReceivable",
    # V4 operational
    "ServiceOrder", "OS_STATUSES",
    "ServiceOrderAssignment", "ASSIGNMENT_TYPES",
    "ServiceOrderEvent", "EVENT_TYPES",
    "OperationCost", "COST_TYPES", "COST_TYPE_LABELS",
    "RevenueEntry", "REVENUE_STATUSES",
    "SupplierPayment", "PAYMENT_STATUSES",
    "FinancialEntry", "ENTRY_TYPES",
]
