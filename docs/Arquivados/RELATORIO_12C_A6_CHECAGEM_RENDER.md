# RELATÓRIO 12C-A6 — CHECAGEM OPERACIONAL FINAL DO RENDER (SOMENTE VERIFICAÇÃO)

**Data**: 29/08/2026 — **Modo**: somente leitura. **Nenhum commit, push, deploy, migration, alteração de código, banco, variáveis ou serviço no Render.**

---

## 1. Objetivo

Fechar as duas pendências operacionais restantes (UPLOAD_FOLDER/persistência e Gunicorn/bind/PORT) e revisar se há outro bloqueador antes do primeiro deploy da branch `v3`.

## 2. UPLOAD_FOLDER

- Definição: `config.py` — `UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "")`.
- Quando vazio: `app/__init__.py:54-56` faz fallback para `app/static/uploads` (**apenas para dev funcionar sem config**).
- Usos de upload: imagem de categoria (`categories/routes.py:90`), logo da empresa (`dashboard/routes.py:385`), imagem de placa da PO (`purchase_orders/routes.py:917`); PDFs leem logo/placa de lá (`order_pdf.py`, `purchase_order_pdf.py`).
- Documentado em `docs/deployment.md` (linhas 13, 26, 237): **Render Disk 1 GB em `/orcamentos`** e `UPLOAD_FOLDER=/orcamentos/uploads`.
- Risco sem configuração: uploads caem no static efêmero do container → **perdidos a cada redeploy/restart** (logo, imagens de categoria e placa). Sem risco se essas funcionalidades não forem usadas em produção.

**Classificação: B — precisa configuração no Render** (somente se uploads forem utilizados).

## 3. Armazenamento persistente

Necessário apenas para uploads (logo/categoria/placa). PDFs são gerados em memória (sem persistência). Render Disk é a solução documentada; **não criado por mim** (proibido nesta etapa).

## 4. Gunicorn

- Start Command = Procfile: `web: gunicorn ExecFlow:app --workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20 --access-logfile - --error-logfile -`.
- 1 worker/2 threads coerente com Render 512 MB; timeout 60s; reciclagem por max-requests (mitigação de memória).
- Sem `--bind` no comando.

## 5. PORT

- Nenhuma referência a `PORT`/`--bind`/`0.0.0.0` no repositório (Procfile, ExecFlow.py, deployment.md — este último apenas define "Start Command (definido pelo Procfile)" e Health Check `/`).
- **Sem `--bind`**, o gunicorn escutaria em `127.0.0.1:8000` por padrão — incompatível com o modelo Web do Render, que exige escuta em `0.0.0.0:$PORT`.
- O serviço de produção **já funciona** (deploys anteriores) — o que sugere que a porta é resolvida fora do repositório (ex.: Start Command sobrescrito no Dashboard do Render ou `GUNICORN_CMD_ARGS` com `--bind`). **Não verificável deste ambiente.**

**Classificação: B — precisa confirmação no Render** (confirmar que o serviço expõe `0.0.0.0:$PORT`; se necessário, adicionar `--bind 0.0.0.0:$PORT` ao Procfile — alteração de configuração, não de código).

## 6. SECRET_KEY

Declarado pelo responsável como **configurada no Render** (12C-A2). Código: env var única (`SECRET_KEY`), fallback inseguro apenas quando ausente. ✅ (confirmação do responsável).

## 7. FLASK_ENV

Declarado pelo responsável como `FLASK_ENV=production` configurado no Render (12C-A2) → `ProductionConfig`: DEBUG=False + cookie Secure. ✅ (confirmação do responsável).

## 8. DATABASE_URL

Fornecida pelo PostgreSQL do Render; código normaliza `postgres://`→`postgresql://`; engine options por driver. ✅ pelo código; valor nunca acessado/exposto por mim.

## 9. Migrations

- Boot roda `flask_migrate.upgrade()` (ExecFlow.py) — idempotente.
- Head de produção: `b5c6d7e8f9a0` → o deploy aplicará **2 migrations adicionais** (3A/3B: novas tabelas/colunas, validadas em dev e em cópia isolada).
- Restore-test da produção validado (12C-A5, classificação A) — o banco de produção está pronto para recebê-las.

## 10. PostgreSQL

- Compatibilidade confirmada (JSON, FKs, índice parcial UNIQUE suportado quando a 3A rodar; batch só SQLite).
- Timezone da produção = UTC (informativo; app escreve timestamps naive BRT — consistente).
- Valores monetários em double precision (débito MÉDIO documentado, não bloqueador).

## 11. Segurança

DEBUG=False (com FLASK_ENV confirmado) · CSRF global ativo · cookies HttpOnly+SameSite=Lax+Secure (prod) · HTTPS nativo Render · RBAC · multiempresa — sem pendências de código.

## 12. Dependências

`requirements.txt` completo (gunicorn, psycopg2-binary, reportlab, flask stack…). Sem dependências de dev em produção. Versões sem pin (recomendação futura).

## 13. Outros riscos operacionais

- Static files servidos pelo Flask/gunicorn (1 worker) — adequado ao volume; sem WhiteNoise (recomendação futura, não bloqueador).
- Health Check `/` → 302 para login (aceito pelo Render).
- Logs no stdout/stderr (acessíveis no Render). Sem config adicional.
- Restart manual: proibido nesta etapa — não executado.

## 14. Itens confirmados

- Pelo código: configuração de SECRET_KEY/FLASK_ENV/DATABASE_URL/CSRF/sessão, migrations no boot, Procfile, fallback de uploads (dev), normalização postgres.
- Pelo responsável: SECRET_KEY e FLASK_ENV configurados no Render; dump/restore validados (A5).

## 15. Itens que dependem do Render

1. Confirmar bind/porta do serviço (seção 5).
2. Definir `UPLOAD_FOLDER=/orcamentos/uploads` + Render Disk (se uploads usados).
3. (Opcional) revisar Start Command se o bind atual for via Dashboard.

## 16. Bloqueadores

**Nenhum bloqueador de código.** As duas pendências (bind e uploads) são operacionais e têm solução direta no Render; nenhuma impede o deploy se o bind atual já estiver funcionando (produção já responde).

## 17. Checklist final para deploy

- [x] Backup de produção validado (A5)
- [x] Restore-test aprovado (A5)
- [x] SECRET_KEY configurada (responsável)
- [x] FLASK_ENV=production (responsável)
- [x] DATABASE_URL (Render PostgreSQL)
- [x] Migrations preparadas e validadas (head b5c6d7e8f9a0 → c4d2e9f0a1b5)
- [x] Suíte com baseline (6 falhas pré-existentes)
- [x] Smoke local completo
- [ ] Confirmar bind/PORT no serviço Render (responsável)
- [ ] UPLOAD_FOLDER + Disk (responsável, se uploads usados)
- [ ] Push da branch v3 + monitorar logs do boot

## 18. Classificação final

**B — PRONTO COM PENDÊNCIAS OPERACIONAIS**

As únicas pendências são: (1) confirmação do bind/porta no serviço Render e (2) UPLOAD_FOLDER + Render Disk se uploads forem usados. Ambas são ações do responsável no Dashboard do Render — **nenhuma alteração de código é necessária**. O deploy pode ser autorizado assim que esses dois pontos forem confirmados.

---

**Nenhum commit, push, deploy, migration, alteração de código, banco, variáveis ou serviço foi realizada.** PARADO — aguardando autorização.
