"""Seed das categorias financeiras e centros de custo (Etapa 3A).

Uso:
    python tools/seed_financial_catalog.py            # seed para TODAS as companies
    python tools/seed_financial_catalog.py 1          # seed para a company 1

Idempotente: se a empresa já tiver qualquer categoria financeira, nada é
criado para ela (não duplica e não altera nada existente).
Somente as tabelas novas (financial_categories / cost_centers) recebem linhas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.financial_catalog import FinancialCategory, CostCenter  # noqa: E402

# Hierarquia: (tipo, nome, filhos...) — filhos ficam sob o pai com indentação
_CATALOG = [
    ("revenue", "Receitas", [
        ("Receita de Serviços",),
        ("Outras Receitas",),
    ]),
    ("direct_cost", "Custos Diretos", [
        ("Motoristas",),
        ("Combustível",),
        ("Pedágios",),
        ("Estacionamentos",),
        ("Hospedagem",),
        ("Alimentação",),
        ("Terceirização",),
        ("Locação de Veículos",),
    ]),
    ("expense", "Despesas Operacionais", [
        ("Manutenção de Veículos",),
        ("Lavagem",),
        ("Seguro",),
        ("Rastreamento",),
        ("Licenciamento",),
        ("IPVA",),
        ("Telefonia",),
        ("Sistemas Operacionais",),
        ("Equipamentos",),
        ("Uniformes",),
    ]),
    ("expense", "Despesas Administrativas", [
        ("Aluguel",),
        ("Contabilidade",),
        ("Material de Escritório",),
        ("Internet",),
        ("Telefonia",),
        ("Sistemas Administrativos",),
        ("Serviços Jurídicos",),
    ]),
    ("expense", "Pessoal", [
        ("Salários",),
        ("Pró-labore",),
        ("Encargos",),
        ("Benefícios",),
        ("Férias",),
        ("13º Salário",),
    ]),
    ("expense", "Impostos", [
        ("Simples Nacional",),
        ("ISS",),
        ("Taxas",),
    ]),
    ("expense", "Despesas Financeiras", [
        ("Tarifas Bancárias",),
        ("Juros",),
        ("Multas",),
        ("Taxas de Cartão",),
        ("IOF",),
    ]),
]

_COST_CENTERS = [
    "Operação", "Frota", "Administrativo", "Comercial",
    "Marketing", "Tecnologia", "Financeiro",
]


def seed_company(company_id: int) -> dict:
    created = {"categories": 0, "cost_centers": 0, "skipped": False}
    if FinancialCategory.query.filter_by(company_id=company_id).first() is not None:
        created["skipped"] = True
        return created

    def add(name, ctype, parent=None):
        cat = FinancialCategory(company_id=company_id, name=name, type=ctype,
                                parent=parent, active=True)
        db.session.add(cat)
        db.session.flush()
        created["categories"] += 1
        return cat

    for ctype, root_name, children in _CATALOG:
        root = add(root_name, ctype)
        for (child_name,) in children:
            add(child_name, ctype, parent=root)

    for cc_name in _COST_CENTERS:
        db.session.add(CostCenter(company_id=company_id, name=cc_name, active=True))
        created["cost_centers"] += 1

    db.session.commit()
    return created


def main():
    app = create_app()
    with app.app_context():
        ids = [int(a) for a in sys.argv[1:]] or [c.id for c in Company.query.all()]
        for cid in ids:
            company = db.session.get(Company, cid)
            if company is None:
                print(f"[{cid}] company não encontrada — ignorada")
                continue
            result = seed_company(cid)
            if result["skipped"]:
                print(f"[{cid}] {company.name}: já possui categorias — nada criado (idempotente)")
            else:
                print(f"[{cid}] {company.name}: {result['categories']} categorias + "
                      f"{result['cost_centers']} centros de custo criados")


if __name__ == "__main__":
    main()
