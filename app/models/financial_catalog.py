"""financial_catalog.py — Categorias financeiras e centros de custo (Etapa 3A).

Fundação da nova arquitetura financeira:
  * FinancialCategory — classificação de receitas, custos diretos e despesas,
    com hierarquia (parent_id) e isolamento por company_id.
  * CostCenter — centro de custo por empresa (Operação, Frota, ...).

Não substitui nada existente: SO/PO/FinancialRecord históricos permanecem
intocados; os vínculos (financial_category_id / cost_center_id) são opcionais
e serão usados por lançamentos futuros.
"""
from ..extensions import db
from .base import TimestampMixin

# Tipos de categoria — não confundir DIRECT_COST com EXPENSE:
#   revenue     — receita de serviços / outras receitas
#   direct_cost — custo diretamente ligado à execução de um serviço
#   expense     — gasto geral da empresa, sem vínculo obrigatório com serviço
FINANCIAL_CATEGORY_TYPES = ("revenue", "direct_cost", "expense")

FINANCIAL_CATEGORY_TYPE_LABELS = {
    "revenue":     "Receita",
    "direct_cost": "Custo Direto",
    "expense":     "Despesa",
}


class FinancialCategory(db.Model, TimestampMixin):
    __tablename__ = "financial_categories"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    type        = db.Column(db.String(20), nullable=False, default="expense")  # revenue|direct_cost|expense
    parent_id   = db.Column(db.Integer, db.ForeignKey("financial_categories.id"), nullable=True)
    active      = db.Column(db.Boolean, nullable=False, default=True)

    parent   = db.relationship("FinancialCategory", remote_side=[id], backref="children")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "active": self.active,
        }

    def __repr__(self):
        return f"<FinancialCategory {self.id} {self.name} [{self.type}]>"


class CostCenter(db.Model, TimestampMixin):
    __tablename__ = "cost_centers"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    active      = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "active": self.active,
        }

    def __repr__(self):
        return f"<CostCenter {self.id} {self.name}>"
