# RELATÓRIO 12C-A6.1 — INVESTIGAÇÃO DO START COMMAND / GUNICORN (SOMENTE VERIFICAÇÃO)

**Data**: 29/08/2026 — **Modo**: somente leitura. **Nenhum commit, push, deploy, restart, alteração de código, Procfile, env vars ou serviço no Render.**

---

## 1. Objetivo

Determinar como o serviço atual do Render consegue responder apesar de o repositório não conter `--bind` nem referência a `PORT`.

## 2. Evidências do repositório (verificadas por grep)

- **Procfile** (raiz): `web: gunicorn ExecFlow:app --workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20 --access-logfile - --error-logfile -` — **sem `--bind`**.
- **`PORT`** (palavra exata): nenhuma ocorrência em `config.py`, `ExecFlow.py`, `app/`, Procfile — **exceto na documentação** (`docs/production.md:15,35`).
- **`GUNICORN_CMD_ARGS` / `WEB_CONCURRENCY`**: **zero ocorrências** no repositório.
- **`render.yaml`**: não existe.
- **`docs/production.md`** (guia V2, §2): "O Gunicorn detecta automaticamente `$PORT` do Render."
- **`docs/deployment.md`**: Start Command = "(definido pelo Procfile)"; Health Check `/`; sem menção a bind.

## 3. Respostas

**A) Comando efetivamente definido no repositório:** `gunicorn ExecFlow:app --workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20` (Procfile) — **sem bind explícito**.

**B) Existe variável/configuração no código que altere o comportamento padrão do Gunicorn?** Não. Nenhum uso de `GUNICORN_CMD_ARGS`, `WEB_CONCURRENCY`, `PORT` ou parâmetros de bind no código da aplicação.

**C) Evidência no repositório de configuração externa?** Apenas a **afirmação documental** (`docs/production.md:35`) de que o Gunicorn "detecta automaticamente $PORT". Tecnicamente, o gunicorn padrão **não lê `PORT` sozinho** — a detecção documentada só é possível por um destes mecanismos externos:
1. Variável de ambiente `GUNICORN_CMD_ARGS` (ex.: `--bind 0.0.0.0:$PORT`) definida no Dashboard do Render — o gunicorn a lê nativamente; ou
2. **Start Command sobrescrito no Dashboard do Render** (ignorando o Procfile do repositório).

**NÃO CONFIRMADO NO CÓDIGO — requer verificação no Dashboard do Render.**

**D) O que precisa ser confirmado no Dashboard do Render:** qual dos dois mecanismos acima está ativo (qualquer um deles explica o funcionamento atual). Verificar em Settings → Start Command e na lista de Environment Variables.

## 4. Risco técnico de manter `gunicorn ExecFlow:app` sem bind

Sem `--bind`, o gunicorn escuta por padrão em **127.0.0.1:8000**. No modelo Web Service do Render, o proxy externo faz o health check e encaminha requisições para **`$PORT`** (porta dinâmica injetada). Consequências se nenhum mecanismo externo resolver o bind:

- O serviço escutaria numa porta errada → **health check falha** → crash-loop de deploy;
- O app ficaria inacessível externamente.

**Como a produção atual responde normalmente, um dos mecanismos externos (C1 ou C2) já está ativo.** O risco residual é **operacional**: futuras edições de env vars/Start Command ou recriação do serviço poderiam remover o mecanismo silenciosamente, sem que o repositório documente isso. Recomendação futura (não executada): adicionar `--bind 0.0.0.0:$PORT` ao Procfile para tornar o bind explícito e independente de configuração externa — **alteração de configuração, requer autorização**.

## 5. Classificação

**B — bind depende de configuração externa**

O bind atual não está no repositório; funciona por configuração no Render (a confirmar qual mecanismo). Não é bloqueador enquanto o serviço responder, mas deve ser confirmado antes do próximo deploy e, idealmente, explicitado no Procfile (com autorização).

---

**Nenhum commit, push, deploy, alteração de código, Procfile, env vars ou serviço foi realizada.** PARADO — aguardando autorização.
