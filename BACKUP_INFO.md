# BACKUP_INFO — Etapa 0 (pré-evolução financeira)

**Data**: 2026-08-28
**Hora**: 14:54 (BRT)
**Objetivo**: ponto de restauração completo antes da evolução do módulo financeiro (pós-auditoria, sem nenhuma alteração funcional).

## Identificação

| Item | Valor |
|---|---|
| Branch | `v3` |
| Commit base (estado pré-checkpoint) | `91d6c12ddc8319f0781442b1c380d587be2c6ebc` |
| Commit de checkpoint (este arquivo + .gitignore) | ver `git rev-list -1 v3-pre-financeiro-20260828` |
| Tag | `v3-pre-financeiro-20260828` (annotated) |
| Alembic head | `b5c6d7e8f9a0` |
| Versão do projeto | ExecFlow_ERP_V3 (deploy Render via branch `v3`) |
| Python | 3.11.9 (venv `AI_Projects/venv`) |
| Flask | 3.1.0 |
| Flask-SQLAlchemy | 3.1.1 |
| SQLAlchemy | 2.0.30 |
| Alembic | 1.13.1 |

## Banco de dados

| Item | Valor |
|---|---|
| Ambiente atual (desenvolvimento) | SQLite — `instance/DB_V2.db` (507.904 bytes) |
| `DB_V2.db` na raiz | 0 bytes — NÃO é o banco ativo (sobra de versão anterior) |
| Produção (Render) | PostgreSQL via `DATABASE_URL` (não acessível deste ambiente — ver abaixo) |
| `DATABASE_URL` local | não definida neste ambiente |

## Artefatos de backup (pasta `backup/`)

| Arquivo | Tamanho (bytes) | SHA-256 |
|---|---|---|
| `DB_V2_pre-financeiro-20260828.db` | 507.904 | `1b1c5ed820be4aa5e631c89e91522c4054b507a682140f623bad23933b5bcbdd` |
| `DB_V2_pre-financeiro-20260828.db-wal` (cópia preservada) | 1.095.952 | (não calculado — arquivo auxiliar, cópia byte a byte) |
| `DB_V2_pre-financeiro-20260828.db-shm` (cópia preservada) | 32.768 | (não calculado — arquivo auxiliar, cópia byte a byte) |
| `execflow_v3_pre-financeiro.bundle` (git bundle `--all`) | 3.420.769 | `1673133f0d7f577cec92a6e30468476f36f1d651be5dafb44b342ca144867eff` |
| `execflow_v3_pre-financeiro-20260828.zip` (código) | 5.456.042 | `1e1d5f28306d6377ad0948f5436ebd153cde849c081fa803f1a18983863f59fb` |

## Integridade

| Verificação | Resultado |
|---|---|
| `PRAGMA integrity_check` — banco original (`instance/DB_V2.db`) | ✅ `ok` |
| `PRAGMA integrity_check` — backup (`DB_V2_pre-financeiro-20260828.db`) | ✅ `ok` |
| `PRAGMA integrity_check` — cópia restaurada (teste) | ✅ `ok` |
| Alembic head no original e no backup | ✅ `b5c6d7e8f9a0` |
| Contagens conferidas (companies 2 · users 5 · quotes 36 · orders 40 · order_payments 35 · purchase_orders 32 · po_payments 21 · financial_records 55 · payment_receipts 7 · clients 17 · suppliers 15) | ✅ idênticas original = backup = restaurado |

## Teste de restauração (executado em 2026-08-28)

1. Cópia do backup para diretório temporário (fora do projeto);
2. `PRAGMA integrity_check` na cópia → `ok`;
3. Verificação das 37 tabelas e das contagens principais → idênticas ao original;
4. Leitura pelos models reais da aplicação (SQLAlchemy ORM: Company, Quote, Order, OrderPayment, PurchaseOrder, POPayment, FinancialRecord, PaymentReceipt) → OK;
5. Cópia temporária removida após o teste. **Banco original não foi tocado.**

## Backup de produção (PostgreSQL)

Backup de produção **não foi executado** porque o ambiente atual não possui acesso ao PostgreSQL de produção (`DATABASE_URL` não definida localmente; `pg_dump` indisponível). Executar no Render antes da Etapa 1: dump via painel (Download DB) ou `pg_dump -Fc`.

## Instruções de restauração

### Desenvolvimento (SQLite)

1. Parar a aplicação;
2. Copiar `backup/DB_V2_pre-financeiro-20260828.db` para `instance/DB_V2.db`;
3. Remover `instance/DB_V2.db-wal` e `instance/DB_V2.db-shm` (se existirem);
4. Reiniciar a aplicação (o boot roda `create_all` + `upgrade` idempotentes);
5. Conferir `PRAGMA integrity_check` = `ok`.

### Código

- Via bundle: `git clone backup/execflow_v3_pre-financeiro.bundle <dir>` ou `git fetch <bundle> v3:refs/heads/restaurado` para recriar a branch;
- Via ZIP: extrair em diretório vazio e reinstalar dependências (`pip install -r requirements.txt`).

### Produção (PostgreSQL — Render)

1. Restaurar o dump com `pg_restore --clean --if-exists` no banco alvo;
2. Redepeloyar o código a partir da tag: `git checkout v3-pre-financeiro-20260828`.

## Observações

- Nenhuma alteração funcional foi realizada nesta etapa (nenhum model, rota, template, migration ou regra de negócio).
- Únicos arquivos de controle criados: `BACKUP_INFO.md` (este) e linha `backup/` no `.gitignore`.
- `docs/AUDITORIA_FINANCEIRA.md` (auditoria) entrou junto no commit de checkpoint.
- Nenhum push foi feito; deploy segue o fluxo normal da branch `v3`.
