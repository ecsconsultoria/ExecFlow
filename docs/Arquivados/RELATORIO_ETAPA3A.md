# ETAPA 3A — RELATÓRIO FINAL (Fundação: Categorias + Centros de Custo)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup criado

`backup/DB_V2_pre-etapa3a-20260828.db` — 507.904 bytes
SHA-256: `44175615a12fbae8c55f14dd7fc3da41862808e426b7e0fa56c3be20ae449328`
Criado com a API nativa de backup do SQLite (consistente com WAL), antes de qualquer migration. Backup anterior (`DB_V2_pre-financeiro-20260828.db`) **não sobrescrito**.

## B. Checkpoint Git

Branch `v3`, commit de entrada `1fd1e6c` (Etapa 2), working tree limpo. Verificado antes de iniciar.

## C. Tag

`v3-pre-etapa3a-financeiro-20260828` (anotada, sobre `1fd1e6c`). Checkpoint anterior preservado.

## D. Schema antes

- Alembic head `b5c6d7e8f9a0`; 36 tabelas; sem estrutura de categorias financeiras/centros de custo (somente `vehicle_categories`, de itens de frota — reutilização descartada por propósito diferente).
- `financial_records` com 19 colunas, sem vínculo com catálogo.
- 0 duplicidades de `reference` (ativas e deletadas) — verificado antes do UNIQUE.

## E. Schema depois

- Alembic head `a3c1f8d2e6b4`; 38 tabelas.
- `financial_records` com 21 colunas (`financial_category_id`, `cost_center_id` — todas NULL nos 55 registros históricos).

## F. Migrations criadas

`migrations/versions/a3c1f8d2e6b4_add_financial_categories_and_cost_centers.py` — pequena, documentada, idempotente (guardas de tabela/coluna/índice existentes), sem alteração de dados. DOWN remove somente estruturas novas.

## G. Migrations executadas

1 (a3c1f8d2e6b4) — aplicada no banco dev. **PostgreSQL de produção: NÃO migrado** (migrations rodam apenas no deploy; `pg_dump` de produção segue pendente da Etapa 0).

## H. Tabelas criadas

- `financial_categories` (id, company_id FK, name, description, type, parent_id FK self, active, created_at, updated_at + índice por company)
- `cost_centers` (id, company_id FK, name, description, active, created_at, updated_at + índice por company)

## I. Colunas criadas

- `financial_records.financial_category_id` (Integer, FK, nullable)
- `financial_records.cost_center_id` (Integer, FK, nullable)
- Nenhum valor preenchido nos registros históricos (0 registros com os campos não-NULL).

## J. Índices/constraints

- `ix_financial_categories_company_id`, `ix_cost_centers_company_id`
- **Índice parcial UNIQUE** `uq_financial_records_active_reference` sobre `financial_records(reference) WHERE deleted_at IS NULL AND reference IS NOT NULL` — impede duplicidade lógica de lançamentos ativos sem impedir o ciclo void → re-baixa.

## K. Categorias criadas (seed separado e idempotente)

48 por empresa (96 no total, companies 1 e 2):
- **Receitas** (revenue): Receitas → Receita de Serviços, Outras Receitas
- **Custos Diretos** (direct_cost): Custos Diretos → Motoristas, Combustível, Pedágios, Estacionamentos, Hospedagem, Alimentação, Terceirização, Locação de Veículos
- **Despesas Operacionais**: Manutenção de Veículos, Lavagem, Seguro, Rastreamento, Licenciamento, IPVA, Telefonia, Sistemas Operacionais, Equipamentos, Uniformes
- **Despesas Administrativas**: Aluguel, Contabilidade, Material de Escritório, Internet, Telefonia, Sistemas Administrativos, Serviços Jurídicos
- **Pessoal**: Salários, Pró-labore, Encargos, Benefícios, Férias, 13º Salário
- **Impostos**: Simples Nacional, ISS, Taxas
- **Despesas Financeiras**: Tarifas Bancárias, Juros, Multas, Taxas de Cartão, IOF
- Tool: `tools/seed_financial_catalog.py` (executado 2× — segunda execução não duplicou nada).

## L. Centros de custo criados

7 por empresa: Operação, Frota, Administrativo, Comercial, Marketing, Tecnologia, Financeiro.

## M. Testes executados

- `tests/test_financial_catalog_etapa3a.py` (8 testes novos)
- Suíte completa (`pytest -q`)
- Teste de rollback em cópia isolada do banco (downgrade → verificação → upgrade)

## N. Resultado dos testes

- **8/8 novos testes: PASSARAM** (CRUD categorias + hierarquia; CRUD centros; isolamento company_id; colunas FK nullable; rotas do catálogo não tocam dados transacionais; seed idempotente).
- Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma falha nova.
- **Rollback validado em cópia isolada**: downgrade remove só as estruturas novas (55 FRs, 40 SOs, 32 POs intactos, integrity ok); re-upgrade reconstrói tudo corretamente.

## O. Comparação dos dados históricos (atual × backup pré-3A)

- `financial_records` (55 linhas, 18 colunas originais): **IDÊNTICOS**
- orders, order_items, order_payments, purchase_orders, po_items, po_payments, quotes, payment_receipts, clients, suppliers, companies, services, vehicles, audit_logs: **IDÊNTICOS**
- `users`: somente `updated_at` de 3 usuários (re-gravação do conftest RBAC em toda execução da suíte — comportamento pré-existente, não-financeiro).
- `PRAGMA integrity_check` = ok.

## P. SOs alterados — **ZERO**

## Q. POs alterados — **ZERO**

## R. Pagamentos alterados — **ZERO**

## S. FinancialRecords históricos alterados — **ZERO**

## T. Problemas encontrados

1. SQLite não suporta ADD COLUMN com FK — resolvido com `batch_alter_table` (copy-and-move) no dialect SQLite e ADD COLUMN comum no PostgreSQL.
2. O downgrade direto no banco dev foi bloqueado pelo classificador de segurança (risco de afetar dados históricos) — resolvido executando o teste de rollback em **cópia isolada** (mais seguro e igualmente conclusivo).
3. Nenhum outro problema.

## U. Pendências

1. **Dump do PostgreSQL de produção** (Render) — pendente desde a Etapa 0; obrigatório antes do próximo deploy (a migration nova rodará no boot de produção).
2. Formulário de Despesas (Etapa 3B) — NÃO implementado nesta etapa.
3. Integração SO/PO com categorias/centros de custo — etapa posterior (nenhum registro histórico recebeu vínculo).
4. PO-260602-005 (R$ 13.500,00) — classificação como despesa geral em etapa futura.
5. Restauração dos 27 FRs soft-deletados — decisão pendente.
6. V4 — intacto, sem dependência da nova estrutura (confirmado: nenhum model/rota V4 referencia o catálogo novo).

## V. Recomendação para Etapa 3B

1. Módulo de **Despesas Gerais**: tipo `expense` em FinancialRecord + formulário sem SO/PO (categoria obrigatória + centro de custo + fornecedor + emissão + vencimento + pagamento), reutilizando as rotas de baixa e o ledger existentes.
2. Classificar a PO-260602-005 e o FR manual id45 no novo catálogo (com autorização — é alteração de dado).
3. Filtros/report por categoria e centro de custo no painel financeiro.
4. DRE (após despesas) e fluxo de caixa.

**Nada da Etapa 3B foi implementado nesta etapa.**

🟢 **ETAPA 3A CONCLUÍDA — DADOS HISTÓRICOS PRESERVADOS**
