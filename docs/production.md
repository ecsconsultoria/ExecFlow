# Production Guide — App_Orcamentos_V2

> Guia para ambiente de produção no Render.

---

## 1. Arquitetura no Render

```
┌──────────────────────────────────────┐
│  Render Web Service                  │
│  ├── Gunicorn (Procfile)             │
│  ├── Python 3.11                     │
│  ├── 512 MB RAM (Starter)            │
│  └── Porta: $PORT                    │
├──────────────────────────────────────┤
│  Render PostgreSQL                   │
│  ├── Connection pooling              │
│  └── DATABASE_URL (interno)          │
├──────────────────────────────────────┤
│  Render Disk (opcional)              │
│  ├── /orcamentos/uploads             │
│  └── Logos e arquivos enviados       │
└──────────────────────────────────────┘
```

---

## 2. Procfile

```
web: gunicorn app_v2:app
```

O Gunicorn detecta automaticamente `$PORT` do Render.

---

## 3. Variáveis de Ambiente

### Obrigatórias

```env
SECRET_KEY=<chave-aleatoria-de-64-chars>
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/dbname
BASE_URL=https://<app>.onrender.com
SESSION_COOKIE_SECURE=1
```

### Recomendadas

```env
UPLOAD_FOLDER=/orcamentos/uploads
EMAIL_ADMIN=admin@executivecarsp.com
```

### Opcionais (funcionalidades extras)

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@gmail.com
SMTP_PASS=app-password
SENDER_NAME=Executive Car SP
WPP_NUMBER=5511989178312
PIX_KEY=sua-chave-pix
PIX_MERCHANT_NAME=Executive Car SP
PIX_MERCHANT_CITY=Sao Paulo
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_MODE=live
NF_RATE=0.10
CARD_RATE=0.065
WTF_CSRF_TIME_LIMIT=28800
SESSION_LIFETIME_SECONDS=28800
```

---

## 4. Segurança em Produção

### Configurações Ativas com `FLASK_ENV=production`

| Configuração | Valor | Efeito |
|-------------|-------|--------|
| `DEBUG` | `False` | Sem tracebacks públicos |
| `SESSION_COOKIE_SECURE` | `True` | Cookies só em HTTPS |
| `WTF_CSRF_ENABLED` | `True` | Proteção CSRF |
| HSTS | `max-age=31536000` | HTTPS forçado por 1 ano |
| Headers segurança | Todos ativos | X-Frame, nosniff, referrer, permissions |

### O Que Verificar

- [ ] `SECRET_KEY` **não** é "change-me-in-production"
- [ ] `SECRET_KEY` tem pelo menos 64 caracteres aleatórios
- [ ] `DATABASE_URL` usa PostgreSQL (não SQLite)
- [ ] HTTPS está ativo (Render fornece por padrão)
- [ ] Rate limiter está funcionando (testar 6+ logins com senha errada)
- [ ] Uploads persistem (Render Disk montado em `/orcamentos/uploads`)

---

## 5. PostgreSQL

### Configuração no Render

O Render fornece `DATABASE_URL` interno. O código em `config.py` converte `postgres://` → `postgresql://` automaticamente.

### Connection Pool

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,    # Verifica conexão ativa antes de usar
    "pool_recycle": 300,      # Recicla conexões a cada 5 minutos
}
```

### Índices

FKs não têm `index=True` explícito no código. Em PostgreSQL, queries por FK sem índice fazem **full table scan**. Monitore queries lentas e adicione índices conforme necessário.

### Migrações

As migrações são aplicadas automaticamente no boot via `flask db upgrade` em `app_v2.py`. **Isso é seguro** porque:
- Alembic rastreia migrações já aplicadas na tabela `alembic_version`
- Migrações são idempotentes (não reaplicam se já executadas)

---

## 6. Monitoramento

### Render Dashboard

- **Logs:** Render Dashboard → Seu serviço → Logs
- **Métricas:** CPU, memória, requests
- **Health:** Status do serviço

### Logs da Aplicação

Erros são logados via `app.logger`. Em produção, logs vão para stdout/stderr (capturados pelo Render).

### Endpoints de Verificação

| Endpoint | O Que Verifica |
|----------|---------------|
| `/` | Redireciona para `/dashboard/` (requer login) |
| `/login` | Página de login carrega |
| `/dashboard/` | Dashboard com KPIs (requer login) |

---

## 7. Backup

### PostgreSQL

O Render oferece backups automáticos no plano pago. No plano gratuito, configure backup manual:

```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### Arquivos (Uploads)

Arquivos em `UPLOAD_FOLDER` (Render Disk) são persistentes mas não têm backup automático. Faça backup periódico do diretório.

---

## 8. Limitações Conhecidas

| Limitação | Impacto | Mitigação |
|-----------|---------|-----------|
| Rate limiter in-memory | Não compartilhado entre workers Gunicorn | Usar Flask-Limiter + Redis |
| Google Translate (LGPD) | Dados de clientes enviados a terceiros | Documentar/obter consentimento |
| Sem CSP | Vulnerabilidade XSS teórica | Adicionar header CSP |
| Numeração com race condition | Duplicatas em concorrência | Sequences PostgreSQL |
| FKs sem índice | Lentidão em joins PostgreSQL | Adicionar `index=True` |
| Reset endpoints frágeis | DELETE massivo sem confirmação forte | Adicionar modal + re-autenticação |

---

## 9. Troubleshooting

### O App Não Inicia

1. Ver logs no Render Dashboard
2. Confirmar que `DATABASE_URL` é PostgreSQL válido
3. Verificar se migrações estão pendentes: `flask db current`
4. Testar localmente com `FLASK_ENV=production`

### Erro 500 Generalizado

1. Ver logs de erro no Render
2. Possível falha em migração automática — rodar `flask db upgrade` manualmente
3. Possível `IntegrityError` em seed data — `_seed_rbac()` é idempotente

### CSRF Token Inválido

1. Verificar se `WTF_CSRF_TIME_LIMIT` não expirou
2. Verificar se o template inclui `{{ csrf_token() }}`
3. Para AJAX, verificar header `X-CSRFToken`

### Sessão Expirando Rápido

1. Verificar `SESSION_LIFETIME_SECONDS` (default 28800 = 8h)
2. Verificar se `SESSION_COOKIE_SECURE=True` (requer HTTPS)
3. Verificar se `SECRET_KEY` não foi alterado (invalida sessões existentes)

### Uploads Desaparecendo

1. Verificar se `UPLOAD_FOLDER` aponta para Render Disk
2. Render Disk gratuito tem limite de espaço
3. Sem Render Disk, arquivos são efêmeros (reinício do serviço = perda)

---

## 10. Checklist de Segurança para Produção

- [ ] `SECRET_KEY` forte e único
- [ ] HTTPS ativo (Render fornece)
- [ ] `SESSION_COOKIE_SECURE=1`
- [ ] CSRF ativo (`WTF_CSRF_ENABLED=True`)
- [ ] Headers de segurança ativos
- [ ] HSTS ativo
- [ ] Senhas com hash (pbkdf2:sha256)
- [ ] Rate limiter no login
- [ ] Multi-tenant: `company_id` em todas as queries
- [ ] RBAC: decorators em todas as rotas sensíveis
- [ ] Sem secrets hardcoded no código
- [ ] `.env` no `.gitignore`
- [ ] Auditoria de operações críticas

---

## 11. Plano de Recuperação de Desastres

### Cenário: Banco Corrompido

1. Restaurar backup mais recente do PostgreSQL
2. Verificar integridade com queries de sanity check
3. Reconectar o app

### Cenário: App Comprometido

1. Entrar no Render Dashboard
2. Reverter deploy para versão anterior
3. Rotacionar `SECRET_KEY`
4. Verificar logs de auditoria para identificar ações não autorizadas

### Cenário: Render Indisponível

1. Verificar status.render.com
2. O banco PostgreSQL é independente e continua acessível
3. Considerar failover manual para outro provedor com backup do banco
