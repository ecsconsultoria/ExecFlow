# RELATÓRIO 12C-A3 — VALIDAÇÃO DO BACKUP POSTGRESQL DE PRODUÇÃO (SOMENTE VALIDAÇÃO)

**Data**: 29/08/2026 — **Modo**: validação do arquivo exportado pelo Render. **Nenhum deploy, push, commit, migration, alteração de produção, código ou variáveis.**

---

## 1. Resumo executivo

O export do Render foi localizado, identificado como **pg_dump directory format** (toc.dat + 40 arquivos `.dat` de dados COPY) e validado estruturalmente: TOC legível com DDL completo, tabelas e contagens coerentes, e o `alembic_version` da produção presente (**head `b5c6d7e8f9a0`**). O **restore-test em PostgreSQL isolado não pôde ser executado** (sem `pg_restore`/Docker/Postgres neste ambiente) — pendência documentada. Descobertas relevantes para o deploy registradas na seção de recomendações.

## 2. Arquivo

- **Nome**: `Backup_DB_2026-08-29T11_54Z.dir.tar.gz`
- **Caminho**: `C:\Users\ECS\Downloads\`
- **Data**: 29/08/2026 11:54Z
- **Tamanho**: 141.875 bytes

## 3. Formato

gzip contendo diretório `2026-08-29T11:54Z/app_orcamentos_v2_db/` com `toc.dat` (**TOC binário do pg_dump**) + 40 arquivos `.dat` (COPY text por tabela). Equivale ao **pg_dump directory format** — restaurável com `pg_restore --format=d`. O original **não foi alterado** (inspeção em cópia de trabalho em `%TEMP%\execflow_12ca3\work`).

## 4. Tamanho

141.875 bytes (comprimido) · 43 entradas no tar (toc + 40 .dat + diretórios).

## 5. SHA-256

`3534b9dface37030e8a9af62c3721e3bf41a6556ccb187399b98ac268f2cf4dc`

## 6. Validação pg_restore

`pg_restore --list` **não executado** (pg_restore indisponível neste ambiente). Validação equivalente realizada por leitura direta do TOC: DDL completo presente (CREATE TABLE/DROP/COPY/ALTER), cabeçalho `PGDMP`, PostgreSQL 18.6 (Debian), encoding UTF-8, `ALTER DATABASE ... SET TimeZone TO 'utc'` (produção opera em UTC).

## 7. Objetos encontrados (tabelas no export)

`accounts_receivable · alembic_version · audit_logs · bookings · catalogo_custom · clients · companies · configuracoes · drivers · financial_entries · financial_records · operation_costs · orcamentos · order_items · order_payments · orders · payment_receipts · permissions · po_items · po_payments · purchase_orders · quote_inclusions · quote_items · quotes · revenue_entries · role_permissions · roles · service_order_assignments · service_order_events · service_orders · service_pricing · services · states · supplier_payments · suppliers · user_roles · users · vehicle_categories · vehicles`

⚠️ **Achados relevantes**:
- **NÃO existem** `financial_categories` nem `cost_centers` na produção (migrations 3A ainda não aplicadas).
- Existem tabelas **legadas com dados** (`orcamentos` 4, `configuracoes` 5, `catalogo_custom` 297, `bookings` 3) e tabelas **V4 com dados** (`service_orders` 3, `financial_entries` 3, `operation_costs` 3, `revenue_entries` 3, `supplier_payments` 3) — a produção é um ambiente V2-era com dados reais.

## 8. Estrutura financeira (contagens do export)

| Tabela | Registros | Tabela | Registros |
|---|---:|---|---:|
| orders | 62 | purchase_orders | 71 |
| order_payments | 76 | po_payments | 78 |
| financial_records | 181 | payment_receipts | 7 |
| audit_logs | 2.888 | quotes | 74 |
| clients | 80 | users | 6 |
| companies | 4 | alembic_version | 4 → head **`b5c6d7e8f9a0`** |

Amostra de `financial_records` verificada: linhas COPY íntegras com colunas esperadas (type/category/amount/status/paid_date/reference) — conteúdo reconhecível e consistente.

## 9. Restore-test

🔴 **PENDENTE** — não executado: sem `pg_restore`/`psql`, sem Docker e sem servidor PostgreSQL local neste ambiente. Procedimento documentado (seção 15). O banco dev **não** foi usado como substituto.

## 10. Segurança

✅ Backup **fora do Git** (em `Downloads`, nenhum arquivo `.dump/.tar.gz` no repositório — git status conferido) · ✅ nenhum dado sensível no relatório (sem DATABASE_URL/senha/SECRET_KEY) · ✅ arquivo original intocado (apenas leitura + cópia de trabalho descartável).

## 11. Localização do backup

`C:\Users\ECS\Downloads\Backup_DB_2026-08-29T11_54Z.dir.tar.gz` (original) + cópia de trabalho em `%TEMP%\execflow_12ca3\work` (descartável). Recomendação: mover/duplicar o original para armazenamento externo corporativo e registrar o SHA-256.

## 12. Limitações

1. Restore-test não executado (sem infraestrutura PostgreSQL local).
2. Validação por leitura do TOC (equivalente estrutural do `pg_restore --list`), não pela ferramenta oficial.
3. Contagens por `.dat` assumem COPY texto com 1 linha por registro (formato padrão do pg_dump; amostras conferidas).
4. Comparação com dev é **informativa apenas** — produção tem dados próprios e schema legado (não é espelho do dev).

## 13. Checklist

| Item | Status | Evidência |
|---|---|---|
| Arquivo localizado | ✅ | `Backup_DB_2026-08-29T11_54Z.dir.tar.gz` |
| Formato identificado | ✅ | gzip + toc.dat (PGDMP, PG 18.6) |
| Tamanho > 0 | ✅ | 141.875 bytes |
| Arquivo legível | ✅ | tar -tzf + leitura do TOC |
| Conteúdo PostgreSQL reconhecido | ✅ | CREATE TABLE/COPY/DATABASE |
| pg_restore --list OK | ⚠️ | não executado (sem ferramenta) — TOC lido diretamente |
| SHA-256 calculado | ✅ | `3534b9df…f4dc` |
| Fora do Git | ✅ | Downloads; git sem dumps |
| Restore isolado testado | 🔴 | PENDENTE |
| Banco restaurado abre | 🔴 | PENDENTE |
| Tabelas principais presentes | ✅ | 40 tabelas mapeadas (contagens) |
| Estrutura financeira presente | ✅ | financial_records/orders/po_payments/etc. |
| Produção não alterada | ✅ | nenhum comando contra produção |

## 14. Classificação final

🟡 **BACKUP VÁLIDO, MAS RESTORE-TEST PENDENTE**

O arquivo é um export PostgreSQL legítimo e estruturalmente íntegro (TOC + 40 arquivos de dados + alembic head presente). A única lacuna é o restore-test em PostgreSQL isolado, impossível neste ambiente.

## 15. Recomendação para deploy

1. **Executar o restore-test antes do deploy** (máquina com Docker/Postgres): `pg_restore --format=d --clean --if-exists -d <db_teste> "<pasta do export>"` e conferir head `b5c6d7e8f9a0`, tabelas e integridade.
2. **Planejar o boot de produção**: o head de produção é `b5c6d7e8f9a0` — o primeiro boot do novo código aplicará **apenas 2 migrations adicionais** (`a3c1f8d2e6b4` + `c4d2e9f0a1b5`: novas tabelas/colunas, idempotentes e validadas em dev) + `create_all` — **nenhuma alteração destrutiva** nas tabelas legadas existentes.
3. O schema legado (orcamentos/configuracoes/catalogo_custom/bookings) e as tabelas V4 **com dados** devem ser preservados — nenhuma migration desta evolução os toca; aposentadoria do V4 deve ser reavaliada (produção tem 3 registros em cada tabela V4).
4. Timezone da produção = UTC — informativo; timestamps naive BRT do app seguem consistentes (documentado na 12C).

---

## Preservação absoluta

- Código alterado: **ZERO** · Banco de produção alterado: **ZERO** · Banco dev alterado: **ZERO** · Migrations: **ZERO** · SO alterados: **ZERO** · PO alterados: **ZERO** · FinancialRecords alterados: **ZERO** · Pagamentos alterados: **ZERO** · Audit logs alterados: **ZERO** · Environment Variables alteradas: **ZERO** · Deploy: **ZERO** · Push: **ZERO** · Commit: **ZERO**

**Nenhuma credencial, DATABASE_URL, senha ou SECRET_KEY consta neste relatório.**

PARADO — aguardando autorização explícita para o próximo passo.
