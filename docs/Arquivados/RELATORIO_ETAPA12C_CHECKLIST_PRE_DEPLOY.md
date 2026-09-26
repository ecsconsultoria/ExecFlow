# RELATÓRIO ETAPA 12C — CHECKLIST FINAL E ENSAIO PRÉ-DEPLOY (SEM DEPLOY)

**Data**: 29/08/2026 — **Modo**: verificação final. **Nenhum commit, push, deploy, migration, alteração de produção ou de dados.**

---

## 1. Resumo executivo

Tudo o que é verificável **deste ambiente local** está OK (código, migrações, testes, smoke, dados protegidos). O deploy permanece **bloqueado por pendências operacionais que dependem do responsável pela produção** (acesso ao Render): dump do PostgreSQL, definição das env vars e confirmações de bind/timezone/disk. **Esta etapa não é o deploy e nada foi alterado.**

## 2. SECRET_KEY

⚠️ **Ainda pendente** — o código usa `SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")`. A chave real **deve** ser fornecida por Environment Variable no Render (procedimento documentado na 12B: gerar `secrets.token_hex(32)` e configurar como secret). **Não confirmável deste ambiente.**

## 3. FLASK_ENV

🔴 **BLOQUEADOR OPERACIONAL** — não confirmável deste ambiente. Sem `FLASK_ENV=production`, o app sobe com `DevelopmentConfig` (DEBUG=True + cookie sem Secure). **Ação (responsável, no Render):** definir `FLASK_ENV=production` e confirmar DEBUG=False no boot. **Não alterar automaticamente.**

## 4. DATABASE_URL

⚠️ Não definida neste ambiente (não revelada). Em produção é fornecida pelo Render PostgreSQL; o código normaliza `postgres://` → `postgresql://`. Confirmação no Render: pendente (responsável).

## 5. Uploads

⚠️ `UPLOAD_FOLDER` default vazio. Configuração necessária (documentada em `docs/deployment.md:52,237`): `UPLOAD_FOLDER=/orcamentos/uploads` + Render Disk em `/orcamentos`. Persistência após restart **não testável deste ambiente** — validar no Render (upload de teste → restart → arquivo presente).

## 6. PostgreSQL

✅ Compatibilidade de schema confirmada por análise (JSON, FKs, índice parcial UNIQUE, ADD COLUMN comum; batch só SQLite). ⚠️ Float para moeda (débito MÉDIO, não bloqueador). ⚠️ Timezone (seção 11).

## 7. Dump

🔴 **BLOQUEADOR PARA DEPLOY** — **não executado**: este ambiente não possui `DATABASE_URL` nem `pg_dump`/`psql`. Procedimento exato (responsável, no Render): botão **"Download DB"** ou `pg_dump -Fc "$DATABASE_URL" -f execflow_prod_pre_deploy_YYYYMMDD.dump`; armazenar **fora do Git**; validar com `pg_restore --list`. Sem dump válido, **o deploy não deve ser autorizado**.

## 8. Restore

⚠️ Não executado (sem dump e sem cópia PostgreSQL isolada neste ambiente). Procedimento documentado: `pg_restore --clean --if-exists` **somente em banco de teste**, nunca sobre produção sem autorização. Pendência: validar o restore em ambiente isolado antes do deploy.

## 9. Gunicorn

✅ Procfile auditado: `gunicorn ExecFlow:app --workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20` — coerente com Render 512 MB.

## 10. PORT

⚠️ Procfile **sem `--bind`** explícito. Se o serviço atual do Render já responde, o mecanismo atual funciona; caso contrário, o Start Command deve expor `0.0.0.0:$PORT` (ex.: `gunicorn ... --bind 0.0.0.0:$PORT`). **Confirmar no Render — não alterável deste ambiente.**

## 11. Timezone

- Aplicação: `now_br()` retorna **datetime naive em horário de Brasília** (tzinfo removido) — todos os `created_at/updated_at/paid_at/deleted_at` são armazenados como **naive BRT** (`db.DateTime` sem timezone).
- PostgreSQL: naive → "timestamp without time zone" — **consistente com a semântica atual do app** (sem shift), desde que o app continue escrevendo wall-clock BRT.
- ⚠️ Risco baixo: qualquer agregação SQL feita por ferramenta externa assumindo UTC veria as horas "naive" como UTC — não afeta o app. **Confirmar o timezone da sessão do Postgres do Render como informativo (não alterar dados).**

## 12. Migrations

✅ Head esperado e confirmado: **`c4d2e9f0a1b5`** (17 arquivos versionados, cadeia linear, guardas idempotentes). ✅ Downgrade/upgrade validado em cópia isolada hoje (dados intactos, integrity ok). ⚠️ Upgrade em PostgreSQL isolado **não testável deste ambiente** — pendência do responsável (opcional: staging com `DATABASE_URL` de teste). Primeiro boot em produção aplica a cadeia completa — idempotente; monitorar logs.

## 13. Segurança

✅ DEBUG=False (com FLASK_ENV=production) · CSRF global · HttpOnly + SameSite=Lax · Secure em ProductionConfig · HTTPS nativo Render · RBAC · multiempresa. 🔴 dependem de SECRET_KEY/FLASK_ENV (seções 2–3).

## 14. Financeiro

✅ Regressão confirmada hoje: DRE = competência · Caixa = paid_date · AR/AP = due_date · Dashboard = fontes consolidadas · baixa parcial acumulativa · FR espelho acumulado · **0 duplicidades ativas**. ✅ Pronampe/FR28 (pago 13.500) · FR45 (cancelado) · 6 soft-deletados — **intactos**. Contagens: orders 40 · POs 32 · FRs 55. Integrity ok.

## 15. Smoke test

✅ Local (somente leitura): login · Dashboard · SO 36 · PO 13 · DRE · Caixa · Relatórios — 6/6 telas 200 · PDF 200 (application/pdf). Nenhuma operação financeira executada.

## 16. Testes

✅ Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova.

## 17. Checklist pré-deploy

**ANTES DO DEPLOY**
- [ ] Backup PostgreSQL confirmado (🔴 pendente — seção 7)
- [ ] Restore testado ou procedimento validado (⚠️ pendente)
- [ ] SECRET_KEY configurada (⚠️ pendente — responsável)
- [ ] FLASK_ENV=production (🔴 pendente — responsável)
- [ ] DATABASE_URL configurada (⚠️ confirmar no Render)
- [ ] Upload Disk configurado (⚠️ se uploads)
- [ ] UPLOAD_FOLDER configurado (⚠️ se uploads)
- [ ] Gunicorn/PORT confirmado (⚠️ seção 10)
- [ ] Timezone confirmado (⚠️ informativo)
- [ ] Environment revisado (responsável)
- [ ] Git revisado (✅ branch v3, HEAD a9950b0 — docs 12A/12B/11B-A2/A3 sem commit por instrução)

**DURANTE O DEPLOY**
- [ ] Push da branch autorizada (v3)
- [ ] Deploy iniciado no Render
- [ ] Logs monitorados (migrations no primeiro boot)
- [ ] Migration somente se necessária e previamente validada
- [ ] Health check

**DEPOIS DO DEPLOY**
- [ ] Login · Dashboard · Financeiro · SO · PO · AR/AP · DRE · Caixa · PDF · Upload · RBAC · Multiempresa

**ROLLBACK**
- [ ] Reverter deploy no Render (commit anterior)
- [ ] Restaurar código anterior
- [ ] Nunca executar downgrade de migration sem análise
- [ ] Restaurar banco somente mediante procedimento autorizado (dump)

## 18. Procedimento de deploy (primeiro deploy desta evolução)

1. Responsável executa o **dump** (seção 7) e valida `pg_restore --list`.
2. Responsável define no Render: `SECRET_KEY` (nova), `FLASK_ENV=production`, `UPLOAD_FOLDER` (+Disk), confirma `DATABASE_URL` e bind/porta.
3. Push da branch `v3` (deploy automático do Render).
4. Acompanhar logs do boot (migrations idempotentes; alembic head deve chegar a `c4d2e9f0a1b5`).
5. Smoke test pós-deploy + conferência do head no banco de produção.

## 19. Procedimento de rollback

1. Reverter o deploy no Render (redeploy do commit anterior `6b70e2f` ou tag de checkpoint).
2. Banco: **nunca** downgrade de migration sem análise; se necessário, restaurar o dump (autorização explícita).
3. Validar smoke pós-rollback.

## 20. Bloqueadores

| # | Item | Classificação | Dependência |
|---|---|---|---|
| 1 | **Dump do PostgreSQL de produção** | 🔴 BLOQUEADOR PARA DEPLOY | responsável (acesso Render) |
| 2 | **FLASK_ENV=production confirmado** | 🔴 BLOQUEADOR OPERACIONAL | responsável (Render) |
| 3 | SECRET_KEY externa | 🟠 obrigatório | responsável (Render) |
| 4 | Uploads (Disk + pasta) | 🟠 se uploads usados | responsável (Render) |
| 5 | Bind/porta do gunicorn | 🟠 confirmar | responsável (Render) |
| 6 | Restore-test em cópia | 🟡 recomendado | responsável |

## 21. Pendências

As mesmas da seção 20 + débitos documentados (Float→Numeric; pin de versões; N+1; Pronampe; baixa_record/PO fora do escopo; docs 12A/12B/11B-A2/A3 sem commit — aguardando autorização).

## 22. Decisão final

**C) 🔴 BLOQUEADO**

O código está tecnicamente pronto, mas o deploy **não pode ser autorizado** enquanto o **dump do PostgreSQL de produção não existir/for validado** e as configurações operacionais do Render (FLASK_ENV, SECRET_KEY, uploads, bind/porta) não forem confirmadas pelo responsável. Esses itens dependem exclusivamente de acesso ao Render, indisponível neste ambiente — **não serão executados nem simulados aqui.**

---

**Nenhum commit, push, deploy, migration ou alteração de produção foi realizada.** PARADO — aguardando autorização.
