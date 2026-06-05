# Deployment Guide — App_Orcamentos_V2

> Processo completo de deploy no Render.

---

## 1. Visão Geral do Deploy

```
GitHub ──(push)──▶ Render ──(build)──▶ Gunicorn ──▶ App
                     │
                     ├── PostgreSQL (Render)
                     └── Disk (uploads)
```

---

## 2. Pré-Requisitos no Render

### Serviços Necessários

| Serviço | Plano | Finalidade |
|---------|-------|-----------|
| Web Service | Starter (512 MB) | App Python |
| PostgreSQL | Starter | Banco de dados |
| Disk (opcional) | 1 GB | Uploads persistentes |

### Configuração do Web Service

| Campo | Valor |
|-------|-------|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | (definido pelo Procfile) |
| Health Check Path | `/` |

---

## 3. Variáveis de Ambiente no Render

Configure no Render Dashboard → Environment:

```env
# Obrigatórias
SECRET_KEY=<gerar-chave-aleatoria>
FLASK_ENV=production
DATABASE_URL=<fornecido-pelo-render-postgresql>
BASE_URL=https://<nome-do-app>.onrender.com
SESSION_COOKIE_SECURE=1

# Recomendadas
UPLOAD_FOLDER=/orcamentos/uploads
EMAIL_ADMIN=admin@executivecarsp.com
WTF_CSRF_TIME_LIMIT=28800
SESSION_LIFETIME_SECONDS=28800

# Opcionais (funcionalidades extras)
NF_RATE=0.10
CARD_RATE=0.065
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASS=sua-senha-app
SENDER_NAME=Executive Car SP
WPP_NUMBER=5511989178312
PIX_KEY=sua-chave-pix
PIX_MERCHANT_NAME=Executive Car SP
PIX_MERCHANT_CITY=Sao Paulo
```

---

## 4. Processo de Deploy

### Deploy Automático (Recomendado)

1. Conectar repositório GitHub ao Render
2. Configurar branch de deploy (ex: `main`)
3. Cada push na branch → build + deploy automático

### Deploy Manual

1. Render Dashboard → Manual Deploy → Deploy latest commit

### Build Steps (Automático)

1. `pip install -r requirements.txt`
2. `flask db upgrade` (executado no boot do app, não no build)

---

## 5. O Que Acontece no Boot

Ao iniciar, `app_v2.py` executa:

1. **`create_app()`** — Factory do Flask
   - Inicializa extensões (db, migrate, login, csrf)
   - Registra blueprints
   - Configura headers de segurança
   - Configura upload folder
   - Registra Jinja filters e context processors
   - Roda `db.create_all()` (seguro — só cria tabelas novas)
   - Roda `_ensure_schema_columns()` (hotfix de colunas faltantes)
   - Roda `_seed_initial_data()` (idempotente)
   - Roda `_seed_rbac()` (idempotente)

2. **`flask db upgrade`** — Aplica migrações pendentes

3. **`gc.collect(); gc.freeze()`** — Otimização de memória (produção)

---

## 6. Migrações em Produção

### Comportamento

As migrações são aplicadas automaticamente a cada deploy via `flask db upgrade`. O Alembic verifica a tabela `alembic_version` no banco e só aplica migrações novas.

### Migrações Destrutivas (CUIDADO)

Se uma migração altera/dropa colunas existentes:

1. **Faça backup do banco antes**
2. Teste a migração em ambiente de staging
3. Verifique se o código ainda referencia colunas antigas
4. Deploy em horário de baixo uso

---

## 7. Rollback

### Reverter Deploy

1. Render Dashboard → Seu serviço → Deploys
2. Encontrar o deploy estável anterior
3. "Deploy again" naquele commit

### Reverter Migração

Se o deploy incluiu uma migração problemática:

```bash
# Conectar ao banco de produção e reverter
flask db downgrade -1
```

**⚠️ Cuidado:** `downgrade` pode causar perda de dados se a migração dropou colunas.

### Reverter Código + Migração

1. Reverter deploy no Render para commit anterior
2. Conectar ao banco e rodar `flask db downgrade -1`
3. Verificar se o app funciona normalmente

---

## 8. Verificações Pós-Deploy

### 8.1 Smoke Tests Imediatos (Primeiros 5 Minutos)

Execute estas verificações na ordem indicada. Se qualquer teste falhar, inicie rollback (§7).

#### Fase 1: Disponibilidade (30 segundos)
- [ ] `GET /` — Redireciona para `/dashboard/` (ou `/login` se não autenticado)
- [ ] `GET /login` — Página de login carrega (HTTP 200)
- [ ] Sem erros 500 nos logs do Render

#### Fase 2: Autenticação (1 minuto)
- [ ] `POST /login` com credenciais admin — Sucesso, redireciona para `/dashboard/`
- [ ] `POST /login` com senha errada — Flash message de erro (não 500)
- [ ] `POST /login` 6x com senha errada — Rate limiter bloqueia (HTTP 429)
- [ ] `GET /logout` — Logout funciona, redireciona para `/login`

#### Fase 3: Navegação Core (2 minutos)
- [ ] `GET /dashboard/` — KPIs carregam (clientes, orçamentos, reservas, OS)
- [ ] `GET /quotes/` — Lista de orçamentos carrega
- [ ] `GET /orders/` — Lista de pedidos carrega
- [ ] `GET /dispatch/` — Dashboard de despacho carrega
- [ ] `GET /financial/` — Lista financeira carrega
- [ ] `GET /reports/` — Relatórios carregam com métricas
- [ ] `GET /clients/` — Lista de clientes carrega
- [ ] `GET /drivers/` — Lista de motoristas carrega
- [ ] `GET /vehicles/` — Lista de veículos carrega
- [ ] `GET /suppliers/` — Lista de fornecedores carrega

#### Fase 4: CRUD Básico (1 minuto)
- [ ] Criar cliente de teste — Salva e aparece na lista
- [ ] Criar orçamento com 1 item — Salva, número gerado
- [ ] Visualizar detalhe do orçamento — Página carrega
- [ ] Gerar PDF do orçamento (PT) — Arquivo PDF válido
- [ ] Deletar orçamento de teste — Remove sem erro

#### Fase 5: Fluxo Financeiro (1 minuto)
- [ ] Criar orçamento → Aprovar → Order criada automaticamente
- [ ] Order → Gerar parcelas → Total das parcelas = total do pedido
- [ ] Order → Criar PO → PO vinculada ao order
- [ ] PO → Aprovar → Concluir → Margem do order recalculada
- [ ] Deletar dados de teste criados

#### Fase 6: Segurança (30 segundos)
- [ ] Headers de segurança presentes (DevTools → Network → qualquer resposta):
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Strict-Transport-Security` (presente em produção HTTPS)
- [ ] CSRF token presente em formulários
- [ ] Tentar acessar URL protegida sem login → Redireciona para `/login`
- [ ] Tentar acessar recurso de outro tenant → 403 ou 404

### 8.2 Monitoramento Pós-Deploy

| Tempo | Ação |
|-------|------|
| T+5min | Verificar logs — sem erros ou warnings novos |
| T+10min | Verificar métricas de CPU/memória no Render |
| T+30min | Verificar logs novamente |
| T+24h | Verificar logs e métricas do dia |

### 8.3 Rollback se Necessário

Se qualquer verificação nas Fases 1-2 falhar: **rollback imediato**. Fases 3-6: avaliar severidade.

1. Render Dashboard → Deploys → Último deploy estável → "Deploy again"
2. Se houve migração: `flask db downgrade -1`
3. Verificar se app responde após rollback
4. Investigar causa raiz antes de novo deploy

---

## 9. Primeiro Deploy (Setup Inicial)

### Passos

1. Criar conta no Render
2. Criar PostgreSQL no Render
3. Criar Web Service conectado ao repositório
4. Configurar variáveis de ambiente
5. Criar Render Disk (se usar uploads)
6. Fazer primeiro deploy
7. **Importante:** O primeiro boot cria o schema automaticamente (`db.create_all()` + `flask db upgrade` + seed data)
8. Criar usuário admin via seed automático (`admin@executivecarsp.com` / `admin123`)
9. **Trocar a senha do admin imediatamente**

---

## 10. Deploy de Hotfix

Para correções urgentes em produção:

1. Criar branch `hotfix/<descricao>` a partir de `main`
2. Corrigir o bug
3. Testar localmente: `pytest tests/ -v`
4. Testar manualmente em modo produção local:
   ```bash
   set FLASK_ENV=production
   python app_v2.py
   ```
5. PR → Review → Merge na `main`
6. Deploy automático dispara
7. Verificar checklist pós-deploy

---

## 11. Troubleshooting de Deploy

| Sintoma | Causa | Solução |
|---------|-------|---------|
| Build falha | Dependência ausente | Verificar `requirements.txt` |
| App inicia mas mostra 500 | Erro em migração | Ver logs, rodar `flask db upgrade` manual |
| "Database is locked" | SQLite em produção | Verificar `DATABASE_URL` — deve ser PostgreSQL |
| Timeout no health check | App lento para iniciar | Aumentar timeout no Render |
| CSRF token missing | `WTF_CSRF_ENABLED` desabilitado | Verificar env var |
| Uploads não persistem | Sem Render Disk | Criar Disk e configurar `UPLOAD_FOLDER` |
| Memória estourada | PDF generation pesada | Aumentar plano ou otimizar PDFs |
| Sessão inválida após deploy | `SECRET_KEY` alterado | Todos usuários precisam re-login |

---

## 12. Ambiente de Staging

Recomendação: criar um segundo Web Service no Render (`app-staging`) conectado a um banco PostgreSQL separado para testes antes de deploy em produção.

### Configuração Staging

```env
FLASK_ENV=development  # DEBUG ativo para debug
DATABASE_URL=<postgresql-staging>
BASE_URL=https://<app>-staging.onrender.com
```

---

## 13. Automação (Futuro)

Sugestões para pipeline CI/CD:

1. **GitHub Actions:** Rodar `pytest` + `flake8` em cada PR
2. **Staging Deploy:** Deploy automático da branch `staging`
3. **Production Deploy:** Deploy manual ou via tag `v*`
4. **Backup Automático:** Script `pg_dump` agendado no Render Cron
