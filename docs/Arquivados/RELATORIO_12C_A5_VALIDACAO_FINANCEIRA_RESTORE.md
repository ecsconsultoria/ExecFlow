# RELATÓRIO 12C-A5 — VALIDAÇÃO FINAL DO RESTORE FINANCEIRO (SOMENTE LEITURA)

**Data**: 29/08/2026 — **Modo**: somente leitura sobre o banco restaurado isolado (`execflow_restore_test`, localhost:55432, container temporário). **Nenhuma escrita, migration, deploy, push, commit ou alteração.**

---

## 1. Ambiente utilizado

Container PostgreSQL temporário local (`postgres:18`), porta 55432, banco `execflow_restore_test`, acesso via `psycopg2` (venv do projeto). Credenciais temporárias **não registradas**. PostgreSQL **18.6** (x86_64-windows), encoding UTF8, 39 tabelas públicas.

## 2. Backup utilizado

`Backup_DB_2026-08-29T11_54Z.dir.tar.gz` (pg_dump directory; original **intocado**; SHA-256 `3534b9df…f4dc` reconfirmado na 12C-A4).

## 3. Resultado do restore

Restaurado com sucesso pelo responsável (e conferido agora por conexão direta): banco abre, consultas funcionam, dados legíveis.

## 4. Estrutura restaurada

39 tabelas públicas · 94 foreign keys (**todas `convalidated = true`**) · 162 constraints UNIQUE/PK · `alembic_version` = **`b5c6d7e8f9a0`** ✓ (igual à produção). Índices de `financial_records`: apenas `pkey` (esperado no head b5c6d7e8f9a0 — o índice parcial UNIQUE é criado pela migration 3A, ainda não aplicada na produção).

## 5. Integridade

FKs 94/94 validadas · sem órfãos (seção 12) · sem duplicidades (seção 11) · constraints presentes.

## 6. FKs

94 constraints de FK restauradas e validadas; nenhuma violação detectada nas consultas de órfãos.

## 7. FinancialRecords

- Total: **178** (123 ativos · 55 soft-deletados — produção pré-Etapa 6C: registros soft-deletados existem historicamente).
- Ativos: **R$ 210.000,00** · Soft-deletados: R$ 191.500,00.
- Por tipo/status: revenue pago 56 (R$ 115.000,00) · revenue pendente 27 (R$ 140.000,00) · revenue cancelado 1 (R$ 1.500,00) · cost pago 68 (R$ 105.000,00) · cost pendente 26 (R$ 40.000,00).
- Origem de `reference`: `order_payment` 84 · `po_payment` 94 · expense/NULL/OUTRO: **0** (produção é pré-3B — despesas não existem ainda).

## 8. OrderPayments

73 parcelas · pago R$ 115.000,00 · total R$ 155.000,00.

## 9. POPayments

75 parcelas · pago R$ 95.000,00 · total R$ 105.000,00.

## 10. AccountsReceivable

0 registros (tabela existe, vazia — consistente com a arquitetura atual que usa parcelas).

## 11. Duplicidades

- FR ativos com `reference` duplicada: **0**
- Parcelas SO duplicadas (order+installment): **0**
- Parcelas PO duplicadas: **0**
- `receipt_number` duplicado: **0**

## 12. Órfãos

- `order_payments` sem order: **0** · `po_payments` sem PO: **0** · `payment_receipts` sem parcela: **0**
- FR ativos com reference para parcela inexistente (SO/PO): **0**

## 13. Registros críticos

- **FR28/FR45 são registros do DEV** — na produção os ids 28 e 45 correspondem a outros lançamentos: prod FR28 = revenue 400 pendente (`order_payment:31`, soft-deletado); prod FR45 = cost 300 pago (`po_payment:32`, ativo). **Nenhuma ação** — são bases diferentes por natureza (documentado, não comparável).
- Espelhos 1:1 (produção): **4 parcelas SO pagas sem FR ativo** e **6 parcelas PO pagas sem FR ativo** — característica pré-existente dos dados de produção (pré-Etapa 6C), **não causada pelo restore**. Nada foi corrigido.

## 14. Comparação A3 × backup

| Tabela | A3 (wc -l) | Restore (banco) | Parser COPY rigoroso (.dat) |
|---|---:|---:|---:|
| orders | 62 | **59** | **59** ✓ |
| purchase_orders | 71 | **68** | **68** ✓ |
| financial_records | 181 | **178** | **178** ✓ |
| audit_logs | 2.888 | **2.885** | **2.885** ✓ |
| clients | 80 | **77** | **77** ✓ |

## 15. Explicação comprovada da diferença de 3 registros

**(b) outra explicação verificável**: a contagem da A3 usou `wc -l` sobre os arquivos `.dat` (COPY text). Os arquivos contêm **3 quebras de linha físicas extras** (campos textuais com newline real em registros) que o `wc -l` contou como linhas adicionais. Um **parser COPY rigoroso** (ciente de escapes e campos entre aspas) aplicado aos mesmos `.dat` reproduz **exatamente** as contagens do banco restaurado (59/68/178/2.885/77 e todas as demais 39 tabelas, 1:1). **Os dados restaurados são os dados do backup, sem perda de registros.**

## 16. Riscos

- 10 parcelas pagas sem espelho FR ativo (produção pré-6C) — risco de reconciliação **pós-deploy**, não do restore.
- 55 FRs soft-deletados em produção — tratáveis com a série de etapas 6 quando autorizado.
- Sem o índice parcial UNIQUE até a migration 3A rodar no deploy (esperado).

## 17. Conclusão

O backup do Render **restaurou corretamente**: schema íntegro (39 tabelas, FKs válidas), alembic head correto (`b5c6d7e8f9a0`), dados financeiros completos e consistentes (0 duplicidades, 0 órfãos), e as contagens do banco restaurado batem 1:1 com a análise independente dos arquivos do backup. As diferenças da A3 foram **comprovadamente** artefato de contagem, não de perda de dados.

## 18. Classificação final

**A — RESTORE VALIDADO**

O restore foi validado com sucesso em ambiente isolado; objetos e dados principais acessíveis; integridade e consistência financeira confirmadas. Observações (espelhos ausentes e FRs soft-deletados) são características **pré-existentes da produção**, não problemas do backup/restore.

---

## Preservação absoluta

Código: **ZERO** · Banco restaurado: **nenhuma escrita** (somente SELECTs) · Produção: **ZERO** · Banco dev: **ZERO** · Migrations: **ZERO** · SO/PO/Pagamentos/FRs/Audit: **ZERO** · Env vars: **ZERO** · Deploy/Push/Commit: **ZERO** · Backup original: **intocado**.

**Nenhuma credencial consta neste relatório.**

PARADO — aguardando autorização explícita para o próximo passo.
