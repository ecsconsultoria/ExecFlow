# AGENTS_PROD.md — Produção

> **Objetivo:** Guia RÍGIDO para agentes de IA operarem no ambiente de produção. Segurança e integridade dos dados são prioridade absoluta.

---

## 1. Ambiente de Produção

| Configuração | Valor |
|-------------|-------|
| Plataforma | Render |
| Servidor | Gunicorn (`Procfile`) |
| Banco | PostgreSQL |
| Python | 3.11 |
| Debug | **DESATIVADO** (`DEBUG=False`) |
| CSRF | **ATIVADO** |
| Cookie Secure | **ATIVADO** (`SESSION_COOKIE_SECURE=True`) |
| HSTS | **ATIVADO** (1 ano, includeSubDomains) |
| Memória | 512 MB (Render Starter) |

---

## 2. Procfile (Render)

```
web: gunicorn app_v2:app
```

O Gunicorn é iniciado com configurações padrão do Render. O `app_v2.py`:
1. Cria o app via factory
2. Aplica migrações pendentes automaticamente (`flask db upgrade`)
3. Em produção, chama `gc.collect()` e `gc.freeze()` para reduzir pressão de memória

---

## 3. Variáveis de Ambiente Obrigatórias

```env
SECRET_KEY=<chave-segura-aleatoria>
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/dbname
BASE_URL=https://<app-name>.onrender.com
SESSION_COOKIE_SECURE=1
UPLOAD_FOLDER=/orcamentos/uploads
```

### Opcionais (funcionalidades extras)

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@gmail.com
SMTP_PASS=app-password
WPP_NUMBER=5511989178312
PIX_KEY=sua-chave-pix
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

---

## 4. Regras RÍGIDAS DE PRODUÇÃO

### 🔴 NUNCA executar estas ações sem aprovação explícita do usuário:

| Ação Proibida | Endpoint/Rota | Motivo |
|---------------|---------------|--------|
| Reset de dados transacionais | `POST /dashboard/settings/reset-transactional` | Apaga Quotes, Orders, POs, OS |
| Reset de dados financeiros | `POST /dashboard/settings/reset-financial` | Apaga todos os registros financeiros |
| Reset total | `POST /dashboard/settings/reset-all` | Apaga TODOS os dados transacionais + financeiros |
| DELETE direto no banco | N/A | Perda irreversível de dados |
| ALTER TABLE manual | N/A | Pode corromper schema |
| DROP TABLE | N/A | Destrói tabelas |

### 🟡 NUNCA fazer sem verificação adicional:

- Alterar `SECRET_KEY` (invalida todas as sessões)
- Alterar permissões de usuários admin
- Modificar dados diretamente via SQL
- Desabilitar CSRF (`WTF_CSRF_ENABLED=False`)
- Desabilitar `SESSION_COOKIE_SECURE`
- Rodar migrações que alteram colunas existentes sem backup

### 🟢 Permitido com cautela:

- Criar novos registros (CRUD normal via app)
- Corrigir dados via interface do app
- Rodar `flask db upgrade` (migrações pendentes)
- Visualizar logs no Render Dashboard
- Reiniciar o serviço no Render

---

## 5. Segurança

### Headers de Segurança

O sistema aplica automaticamente:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HSTS)

### Rate Limiting

O `LoginRateLimiter` limita 5 tentativas de login por IP/email em 15 minutos. **Limitação conhecida:** em deploys com múltiplos workers Gunicorn, cada worker tem seu próprio contador (não compartilhado). Para produção com `--workers N`, considere migrar para Flask-Limiter + Redis.

### CSRF

Toda requisição POST/PUT/PATCH/DELETE requer token CSRF. Templates usam `{{ csrf_token() }}` nos forms. AJAX usa header `X-CSRFToken`.

### CSP (Content-Security-Policy)

**Não implementado** — esta é uma fraqueza de segurança conhecida. Se for implementar, adicione ao `register_security_headers()` em `app/utils/security.py`.

---

## 6. PostgreSQL — Especificidades

### Connection Pooling

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,    # Verifica conexão antes de usar
    "pool_recycle": 300,      # Recicla conexões a cada 5 min
}
```

### Índices

FKs não têm `index=True` explícito — SQLite cria automaticamente, PostgreSQL **não**. Em produção PostgreSQL com volume de dados, consultas por FK podem ser lentas. Considere adicionar índices antes da migração para produção.

### Migração de SQLite → PostgreSQL

O código suporta ambos os bancos via `DATABASE_URL`. A migração de dados requer ferramenta externa (ex: `pgloader`).

---

## 7. Monitoramento

### Logs

Acessíveis via Render Dashboard → Logs. Gunicorn loga requests HTTP. Erros da aplicação são logados com `app.logger`.

### Health Check

O Render monitora a porta do serviço. O endpoint raiz `/` redireciona para `/dashboard/` (requer autenticação). Considere adicionar um endpoint `/health` público para health check.

---

## 8. Checklist de Deploy em Produção

> **Esta seção é obrigatória para qualquer deploy.** Ignorar estes passos pode causar incidentes em produção.

### 8.1 Pré-Deploy (Planejamento)

- [ ] **Tipo de deploy classificado:**
  - `Tipo A — Hotfix`: Correção crítica, sem migração, sem alteração de schema
  - `Tipo B — Feature`: Nova funcionalidade, pode ter migração
  - `Tipo C — Refactor`: Alteração interna, sem mudança de comportamento
  - `Tipo D — Migração destrutiva`: Altera/dropa colunas/tabelas existentes

- [ ] **Para Tipo D (migração destrutiva):**
  - [ ] Backup completo do banco PostgreSQL foi feito
  - [ ] Migração foi testada em staging COM DADOS REAIS (cópia anonimizada)
  - [ ] Rollback foi testado (`flask db downgrade -1`)
  - [ ] Janela de deploy definida (horário de baixo uso)
  - [ ] Equipe notificada com antecedência

- [ ] **Para todos os tipos:**
  - [ ] `pytest tests/ -v` passa em todos os 85 testes
  - [ ] Código revisado (PR aprovado)
  - [ ] Testado manualmente em ambiente local com `FLASK_ENV=production`
  - [ ] Variáveis de ambiente verificadas (sem "change-me-in-production")
  - [ ] `SECRET_KEY` não foi alterado (invalidaria sessões)

### 8.2 Deploy

- [ ] **Deploy manual ou automático:**
  - Render Dashboard → Deploy → Deploy latest commit
  - Ou: push na branch `main` (auto-deploy)

- [ ] **Monitorar logs durante o boot:**
  - [ ] Sem erros de migração (`flask db upgrade` concluiu)
  - [ ] Sem erros de import (módulos carregados)
  - [ ] `_ensure_schema_columns()` executou sem warnings
  - [ ] `_seed_rbac()` executou sem erros
  - [ ] App respondeu na porta `$PORT`

### 8.3 Pós-Deploy — Smoke Tests Obrigatórios

Execute estes testes **manualmente** no ambiente de produção em até 5 minutos após o deploy:

#### Autenticação
- [ ] `GET /login` — Página de login carrega
- [ ] `POST /login` — Login com admin funciona
- [ ] `GET /logout` — Logout funciona
- [ ] `POST /login` com senha errada — Rate limiter ativo (429 após 5 tentativas)

#### Core — Orçamentos
- [ ] `GET /quotes/` — Lista de orçamentos carrega
- [ ] `GET /quotes/new` — Formulário de novo orçamento carrega
- [ ] Criar orçamento com 1 item — Salva e redireciona
- [ ] `GET /quotes/<id>/pdf/pt` — PDF em português gerado
- [ ] `GET /quotes/<id>/pdf/en` — PDF em inglês gerado

#### Core — Pedidos
- [ ] `GET /orders/` — Lista de pedidos carrega
- [ ] `GET /orders/<id>` — Detalhe do pedido carrega
- [ ] Aprovar orçamento → Order criada automaticamente

#### Core — Despacho
- [ ] `GET /dispatch/` — Dashboard de despacho carrega
- [ ] `GET /dispatch/?date=<hoje>` — Filtro por data funciona

#### Core — Financeiro
- [ ] `GET /financial/` — Lista financeira carrega
- [ ] `GET /reports/` — Relatórios carregam com métricas

#### Segurança
- [ ] Headers de segurança presentes (DevTools → Network → Response Headers):
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Strict-Transport-Security` (presente em HTTPS)
- [ ] CSRF token presente em formulários (verificar `<input type="hidden" name="csrf_token">`)
- [ ] Tentar acessar `/dashboard/` sem login → Redireciona para `/login`

#### Integridade de Dados
- [ ] Criar orçamento de teste → Deletar após validação
- [ ] Verificar se dados existentes não foram corrompidos (spot-check em 3-5 registros)

### 8.4 Pós-Deploy — Monitoramento (30 minutos)

- [ ] **T=0min:** Smoke tests concluídos sem erro
- [ ] **T=5min:** Logs do Render sem erros ou warnings novos
- [ ] **T=10min:** Métricas de CPU/memória normais
- [ ] **T=15min:** Nenhum erro 500 reportado (verificar logs)
- [ ] **T=30min:** Sistema operando normalmente

### 8.5 Rollback (se necessário)

Se qualquer smoke test falhar:

1. **Reverter deploy imediatamente:**
   - Render Dashboard → Deploys → Último deploy estável → "Deploy again"

2. **Se houve migração:**
   ```bash
   # Conectar ao banco de produção
   flask db downgrade -1
   ```

3. **Verificar após rollback:**
   - [ ] App responde
   - [ ] Login funciona
   - [ ] Dados críticos intactos

4. **Investigar causa raiz antes de tentar novo deploy**

---

## 9. Como Validar Deploy em Produção (Procedimento Passo a Passo)

### 9.1 Antes do Deploy

1. **Verificar environment:**
   - [ ] `SECRET_KEY` é uma chave aleatória forte (não "change-me-in-production")
   - [ ] `FLASK_ENV=production`
   - [ ] `DATABASE_URL` aponta para PostgreSQL (não SQLite)
   - [ ] `SESSION_COOKIE_SECURE=1`
   - [ ] `BASE_URL` está correto
   - [ ] `UPLOAD_FOLDER` é um disco persistente do Render

2. **Verificar código:**
   - [ ] `pytest tests/ -v` passa em todos os 85 testes
   - [ ] Migrações foram testadas em staging
   - [ ] Backup do banco foi feito antes de migrações destrutivas

3. **Verificar segurança:**
   - [ ] Nenhuma variável de ambiente contém valor "change-me-in-production"
   - [ ] `DEBUG=False` (ProductionConfig garante, mas verifique)
   - [ ] `WTF_CSRF_ENABLED=True` (ProductionConfig garante)
   - [ ] `SESSION_COOKIE_SECURE=True` (ProductionConfig garante)

### 9.2 Durante o Deploy

1. **Iniciar deploy** (manual ou automático)
2. **Acompanhar logs** no Render Dashboard em tempo real
3. **Verificar stages do boot:**
   - `flask db upgrade` — sem erros
   - `create_app()` — sem exceções
   - `_seed_rbac()` — idempotente, sem erros

### 9.3 Após o Deploy (Primeiros 5 Minutos)

1. **Acessar a URL de produção**
2. **Login com conta admin**
3. **Executar smoke tests** (§8.3 completo)
4. **Verificar logs** — sem erros ou warnings

### 9.4 Monitoramento Contínuo

- Primeiros 30 min: verificar logs a cada 10 min
- Primeiras 24h: verificar logs ao final do dia
- Primeira semana: verificar métricas de uso e performance

---

## 10. Troubleshooting de Produção

| Sintoma | Causa Provável | Ação |
|---------|---------------|------|
| 500 após deploy | Migração falhou | Ver logs do Render, rodar `flask db upgrade` manual |
| "database is locked" | SQLite em produção | Migrar para PostgreSQL |
| Sessão expirando rápido | `SESSION_COOKIE_SECURE` sem HTTPS | Verificar config do Render |
| CSRF token inválido | `WTF_CSRF_TIME_LIMIT` expirado | Verificar se horário do servidor está correto |
| Uploads desaparecendo | Disco não persistente | Configurar `UPLOAD_FOLDER` no Render Disk |
| Memória alta | PDF generation pesada | Aumentar plano Render, otimizar PDF |

---

## 11. Limitações Conhecidas em Produção

1. **Rate limiter não compartilhado entre workers** — usar Flask-Limiter + Redis para multi-worker
2. **Google Translate envia dados para terceiros** — questão LGPD não resolvida
3. **Sem CSP** — vulnerabilidade XSS teórica
4. **Reset endpoints sem confirmação forte** — acessíveis a admins autenticados
5. **Numeração sequencial tem race condition** — sem lock em produção multi-worker
6. **FKs sem índices explícitos** — performance degradada em PostgreSQL com volume

---

## 12. Contatos de Emergência

- **Admin padrão:** `admin@executivecarsp.com`
- **WhatsApp configurado:** `5511989178312`
- **Email admin (config):** `EMAIL_ADMIN` (definido no `.env`)
