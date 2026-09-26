# RELATÓRIO ETAPA 12B — PREPARAÇÃO DE PRODUÇÃO (SEM DEPLOY)

**Data**: 29/08/2026 — **Modo**: preparação + verificação. **Nenhum commit, push, deploy, migration, alteração de produção ou de dados.**

---

## 1. Resumo executivo

Toda a configuração necessária para produção foi mapeada e documentada. Nenhuma alteração de código é necessária. Faltam **ações operacionais no Render** (env vars, dump, disk) e a confirmação do bind do gunicorn. Deploy não realizado — aguardando autorização.

## 2. Environment

| VARIÁVEL | OBRIGATÓRIA? | VALOR CONFIGURADO? | AÇÃO NECESSÁRIA? |
|---|---|---|---|
| `SECRET_KEY` | SIM | ❌ (usa default inseguro) | Definir no Render (ver seção 3) |
| `FLASK_ENV=production` | SIM | ❌ verificar no Render | Definir no Render (ver seção 4) |
| `DATABASE_URL` | SIM (prod) | ✅ fornecida pelo Render PostgreSQL | Confirmar no serviço |
| `UPLOAD_FOLDER` | SIM (se usar uploads) | ❌ verificar | `/orcamentos/uploads` + Render Disk (seção 5) |
| `SESSION_COOKIE_SECURE=1` | Não (ProductionConfig força True) | — | Opcional |
| `BASE_URL`, `SMTP_*`, `PAYPAL_*`, `PIX_*`, `WPP_NUMBER`, `COMPANY_*` | OPCIONAIS | — | Conforme recursos utilizados |

## 3. SECRET_KEY

- ❌ Código usa `SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")` — **produção NÃO pode usar o default**.
- ✅ Nenhum segredo está versionado; nenhum valor real será gravado em código/arquivo.
- **Procedimento seguro (executar no Render → Environment):**
  1. Gerar localmente: `python -c "import secrets; print(secrets.token_hex(32))"` (não commitar o resultado).
  2. Adicionar `SECRET_KEY=<valor gerado>` no Render Dashboard → Environment → Secret Files/Environment Variables (marked as secret).
  3. Efeito colateral esperado: sessões existentes são invalidadas no próximo deploy (relogin) — normal.

## 4. FLASK_ENV

- ⚠️ `create_app()` usa `os.environ.get("FLASK_ENV", "default")` → default = `DevelopmentConfig` (**DEBUG=True**). Sem `FLASK_ENV=production`, a produção subiria com debug e cookie sem Secure.
- ✅ `ProductionConfig`: DEBUG=False + SESSION_COOKIE_SECURE=True (comportamento correto quando FLASK_ENV=production).
- **Ação:** definir `FLASK_ENV=production` no Render. Nenhuma alteração de código necessária.

## 5. Uploads

- Uploads existentes: logo da empresa (`dashboard/routes.py:385-387`) e imagem de placa da PO (`purchase_orders/routes.py:917-920`) — salvos em `current_app.config["UPLOAD_FOLDER"]`, servidos via `/uploads/<arquivo>`.
- ⚠️ Default `UPLOAD_FOLDER` = "" (vazio) → em produção os uploads seriam salvos no filesystem efêmero e **desapareceriam em cada deploy**.
- **Configuração necessária (já documentada em docs/deployment.md:52,237):** `UPLOAD_FOLDER=/orcamentos/uploads` + **Render Disk** montado em `/orcamentos` (plano pago do Render). Sem disco: uploads não persistem (risco atual).
- PDFs: gerados em memória (ReportLab) — sem persistência necessária.

## 6. PostgreSQL

- ✅ Compatibilidade: JSON (`companies.settings`) OK; FKs e índice parcial UNIQUE (`WHERE deleted_at IS NULL AND reference IS NOT NULL`) suportados; Boolean/Date/DateTime/String OK; migrations usam ADD COLUMN comum no Postgres (batch só no SQLite); `postgres://` normalizado para `postgresql://`.
- ⚠️ Valores monetários usam `Float` (não `Numeric`) — risco de arredondamento em escala; **MÉDIO, não bloqueador** (documentado como débito).
- ⚠️ Confirmar timezone do Postgres do Render (datas são `now_br()` no app; UTC no banco pode deslocar `created_at`) — **verificar, não alterar**.

## 7. Dump

**Dump de produção não executado porque o ambiente atual não possui `DATABASE_URL` definida nem `psql`/`pg_dump` instalados.**

Procedimento para o responsável (Render):
- Via painel Render: PostgreSQL → botão **"Download DB"** (dump do backup automático), ou
- Via CLI/local com acesso: `pg_dump -Fc "$DATABASE_URL" -f execflow_prod_pre_deploy_$(date +%Y%m%d).dump`
- Armazenar **fora do banco e fora do Git** (não versionar). Registrar hash (sha256sum) e testar `pg_restore --list` para validar o formato.

## 8. Restore

- Não executado (sem dump disponível). Procedimento: `pg_restore --clean --if-exists -d "$DATABASE_URL" execflow_prod_pre_deploy_*.dump` — **somente em banco de teste primeiro; nunca direto sobre produção sem confirmação**.
- Rollback de código: reverter o deploy no Render (branch anterior); rollback de migration: nunca `flask db downgrade` em produção sem dump validado — restaurar dump se necessário.

## 9. Migrations

- ✅ Head esperado e confirmado: **`c4d2e9f0a1b5`**; todas as migrations versionadas (17 arquivos); cadeia linear; guardas idempotentes.
- ✅ Teste de downgrade/upgrade re-executado hoje em **cópia isolada**: OK (dados intactos, integrity ok nos dois sentidos).
- ⚠️ No primeiro boot em produção, o app aplicará toda a cadeia (create_all + upgrade) — idempotente; monitorar logs do boot.

## 10. Render

| Item | Configuração |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | Procfile (`web: gunicorn ExecFlow:app --workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20`) |
| Port | `$PORT` do Render — ⚠️ **verificar bind**: o Procfile não tem `--bind 0.0.0.0:$PORT`; se o serviço atual já responde, o bind atual funciona (Render pode injetar via GUNICORN_CMD_ARGS); caso contrário, adicionar o bind (alteração de configuração de serviço, não de código) |
| Environment | SECRET_KEY, FLASK_ENV=production, DATABASE_URL, UPLOAD_FOLDER (seções 2–5) |
| Disk | `/orcamentos` (Render Disk) se uploads forem usados |
| Health check | `/` (retorna 302 → login — aceitável) |

## 11. Segurança

✅ DEBUG=False (com FLASK_ENV=production) · SECRET_KEY (pendência de env) · CSRF ativo global · cookies HttpOnly+SameSite=Lax+Secure (prod) · HTTPS nativo do Render · RBAC · multiempresa. Nada a alterar em código.

## 12. RBAC / 13. Multiempresa

✅ Confirmados nas etapas anteriores (12A): decorators, 403/404 e ausência de vazamento testados; sem rota financeira sem permissão.

## 14. Financeiro / 15. DRE / 16. Caixa / 17. AR/AP

✅ Regras consolidadas intactas (competência × caixa × vencimento; espelhos 1:1 com UNIQUE; baixa parcial acumulativa; saldo inicial via settings). Nenhuma alteração nesta etapa.

## 18. PDFs

✅ RFQ/SO/PO gerados com ReportLab (smoke de hoje: SO PDF = 751.480 bytes, application/pdf) — sem arquivos temporários, sem caminho absoluto.

## 19. Testes

✅ Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova.

## 20. Smoke test (local, somente leitura)

✅ Login 302→OK · Dashboard, SO 36, PO 13, Financeiro, Despesas, AR, AP, DRE, Caixa, Relatórios: **10/10 telas 200** · PDF 200. Nenhuma operação financeira executada.

## 21. Rollback

Documentado: reverter deploy no Render (commit anterior) · dump restaurado se necessário · nunca downgrade sem backup validado.

## 22. Checklist final

| ITEM | STATUS | EVIDÊNCIA | AÇÃO |
|---|---|---|---|
| Git | 🟢 OK | v3 / a9950b0 / tree limpo | — |
| Environment | 🟠 | config.py auditado | definir vars no Render |
| SECRET_KEY | 🟠 | default inseguro no código | gerar + definir no Render |
| FLASK_ENV | 🟠 | default → DEBUG | definir `production` no Render |
| DATABASE_URL | 🟢 | normalização pronta | confirmar no Render |
| Uploads | 🟠 | default vazio | `/orcamentos/uploads` + Disk |
| PostgreSQL | 🟢/⚠️ | compatível; Float p/ moeda | verificar tz; débito MÉDIO |
| Dump | 🟠 | não executado (sem acesso) | pg_dump -Fc pelo responsável |
| Restore | 🟡 | procedimento documentado | testar em cópia antes |
| Migrations | 🟢 | head c4d2e9f0a1b5; rollback isolado OK | — |
| Security | 🟢/🟠 | itens ok; depende das env vars | seções 2–4 |
| RBAC / Multiempresa | 🟢 | testados | — |
| Financeiro/DRE/Caixa/AR/AP | 🟢 | consolidados | — |
| PDF | 🟢 | smoke 751 KB | — |
| Tests | 🟢 | 6 pré-existentes, 0 novas | — |
| Smoke test | 🟢 | 10/10 telas 200 | — |
| Render | 🟠 | bind do gunicorn a confirmar | verificar `--bind 0.0.0.0:$PORT` |
| Rollback | 🟢 | documentado | — |

🔴 Bloqueadores: **0** · 🟠 Necessários antes do deploy: **7** (env vars ×3, uploads, dump, bind, tz) · 🟡 Recomendados: restore-test, pin de versões · 🟢 OK: demais.

## 23. Pendências

1. Definir SECRET_KEY (gerada) no Render.
2. Definir FLASK_ENV=production.
3. Confirmar/definir UPLOAD_FOLDER + Render Disk (se uploads).
4. **Dump do PostgreSQL de produção** (responsável com acesso ao Render).
5. Confirmar bind do gunicorn na porta do Render.
6. Verificar timezone do Postgres do Render.
7. (Futuro) Float→Numeric para moeda; pin de dependências.

## 24. Decisão final

**B) 🟡 PRONTO, MAS FALTA CONFIGURAÇÃO OPERACIONAL**

Nenhuma alteração de código é necessária. As pendências são exclusivamente operacionais (env vars no Render, disk, dump, verificação de bind/timezone) — listadas na seção 23. **Deploy NÃO realizado** e não será feito sem autorização explícita.

---

**Nenhum commit, push, deploy, migration ou alteração de produção foi realizada.** PARADO — aguardando autorização.
