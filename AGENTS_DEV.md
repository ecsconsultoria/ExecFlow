# AGENTS_DEV.md — Desenvolvimento Local

> **Objetivo:** Guia para agentes de IA trabalharem no ambiente de desenvolvimento local.

---

## 1. Ambiente Local

| Configuração | Valor |
|-------------|-------|
| Python | 3.11 |
| Banco | SQLite (`instance/DB_V2.db`) |
| Servidor | Flask dev server |
| Porta | 5004 |
| Debug | Ativado (`DEBUG=True`) |
| CSRF | Ativado (`WTF_CSRF_ENABLED=True`) |
| SO | Windows 11 |

---

## 2. Setup Inicial

```bash
# 1. Clonar / entrar no projeto
cd App_Orcamentos_V2

# 2. Criar e ativar venv
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instalar dependências
pip install -r requirements-dev.txt

# 4. Criar .env a partir do template
copy .env.example .env
# Editar .env se necessário (SQLite é o default)

# 5. Rodar
python app_v2.py
# Acessar: http://127.0.0.1:5004
```

---

## 3. `.env` Mínimo para Desenvolvimento

```env
SECRET_KEY=dev-secret-key-not-for-production
FLASK_ENV=development
DATABASE_URL=sqlite:///DB_V2.db
BASE_URL=http://localhost:5004
```

---

## 4. Banco de Dados

### SQLite — Comportamento Específico

- O arquivo `DB_V2.db` é criado automaticamente no primeiro boot
- WAL mode é ativado automaticamente (`PRAGMA journal_mode=WAL`)
- Foreign keys são ativadas (`PRAGMA foreign_keys=ON`)
- `check_same_thread=False` permite acesso multi-thread

### Resetar o Banco (Desenvolvimento)

```bash
# Deletar e recriar
del instance\DB_V2.db
python app_v2.py   # Recria com seed data
```

### Acessar Dados Diretamente

```bash
sqlite3 instance/DB_V2.db
.tables
.schema orders
SELECT * FROM quotes LIMIT 5;
```

---

## 5. Migrações (Alembic)

### Criar nova migração

```bash
flask db migrate -m "descrição da alteração"
```

### Aplicar migrações

```bash
flask db upgrade
```

### Reverter última migração

```bash
flask db downgrade -1
```

### Ver histórico

```bash
flask db history
```

**IMPORTANTE:** As migrações são aplicadas automaticamente no boot (`app_v2.py` chama `_db_upgrade()`). Não é necessário rodar manualmente em dev.

### Schema Patches (Hotfix)

O método `_ensure_schema_columns()` em `app/__init__.py` aplica alterações de coluna via `ALTER TABLE` que o `db.create_all()` não cobre. Use isso apenas para hotfixes em produção; em desenvolvimento, crie uma migração adequada.

---

## 6. Testes

### Rodar todos os testes

```bash
pytest tests/ -v
```

### Rodar um arquivo específico

```bash
pytest tests/test_rbac_routes.py -v
```

### Rodar com cobertura

```bash
pytest tests/ --cov=app --cov-report=html
# Abrir htmlcov/index.html no navegador
```

### Escrever novos testes

- Fixtures compartilhadas em `tests/conftest.py`
- Use `app.config['WTF_CSRF_ENABLED'] = False` (já configurado no `TestingConfig`)
- Use o `test_client` do Flask para simular requests:
  ```python
  def test_my_route(client, auth_user):
      client.post('/login', data={...})
      resp = client.get('/orders/')
      assert resp.status_code == 200
  ```

---

## 7. CSS (Tailwind)

### Build de CSS

```bash
# Usando o binário incluído
build_css.bat

# Ou diretamente
tools\tailwindcss.exe -i app\static\css\tailwind.src.css -o app\static\css\tailwind.css --watch
```

O arquivo `tailwind.config.js` contém as cores da marca (brand dark, gold, light).

---

## 8. Dados de Seed

No primeiro boot, o sistema popula automaticamente:

- **Estados:** SP, RJ
- **Categorias de veículos:** 18 categorias (definidas em `app/models/vehicle.py` → `CATEGORIES`)
- **Serviços e precificações:** Baseados em `tabela_data.py` (tabela Excel convertida)
- **Empresa padrão:** "Executive Car SP"
- **Admin padrão:** `admin@executivecarsp.com` / `admin123`

Para re-seedar: delete o banco e reinicie o app.

---

## 9. Regras para Alterações Seguras

### ✅ PERMITIDO

- Criar novos modelos, blueprints, serviços, templates
- Modificar lógica de negócio nos serviços
- Criar migrações
- Adicionar permissões ao catálogo
- Refatorar código (com testes passando)

### ⚠️ CUIDADO

- Alterar modelos existentes (pode quebrar migrações ou dados)
- Modificar `create_app()` (afeta todos os ambientes)
- Alterar decorators de autorização
- Modificar `_ensure_schema_columns()`

### ❌ PROIBIDO

- Executar `DELETE FROM` ou `DROP TABLE` diretamente
- Hardcodar senhas ou secrets
- Remover `company_id` de queries
- Desabilitar CSRF fora de testes
- Usar `float(str.replace(...))` para parsing monetário (use `parse_brl()`)
- Dar `commit()` dentro de serviços (delegue ao controller)

---

## 10. Checklists Operacionais

### 10.1 Correção de Bugs

Use este checklist para qualquer correção de bug, seja trivial ou complexa.

#### Fase 1: Triagem

- [ ] **Descreva o bug em uma frase:** O que acontece vs. o que deveria acontecer?
- [ ] **Classifique a severidade:**
  - `P0-CRÍTICO`: Corrupção de dados, perda financeira, segurança, sistema offline
  - `P1-ALTO`: Funcionalidade core quebrada, sem workaround
  - `P2-MÉDIO`: Funcionalidade secundária quebrada, com workaround
  - `P3-BAIXO`: Cosmético, melhoria, edge case raro
- [ ] **Reproduza localmente:**
  ```bash
  # 1. Garanta que o banco está limpo ou use um estado conhecido
  python app_v2.py
  # 2. Execute os passos exatos para reproduzir
  # 3. Confirme que o erro acontece
  ```

#### Fase 2: Investigação

- [ ] **Rastreie o fluxo completo** (rota → serviço → modelo):
  ```bash
  # Encontre a rota
  grep -rn "def.*nome_da_rota" app/blueprints/
  # Siga para o serviço
  grep -rn "nome_do_serviço" app/services/
  # Verifique o modelo
  grep -rn "class NomeDoModelo" app/models/
  ```

- [ ] **Verifique suspeitos comuns:**
  - [ ] Falta de `company_id` na query? → Erro de tenant isolation
  - [ ] Falta de `@require_permission`? → Erro 403 indevido
  - [ ] `lazy="joined"` causando N+1? → Performance
  - [ ] `float(str.replace(...))` manual? → Bug de parsing monetário
  - [ ] `db.session.commit()` em lugar errado? → Transação quebrada
  - [ ] Falta de `deleted_at.is_(None)`? → Registro "deletado" aparecendo

- [ ] **Verifique o banco de dados:**
  ```bash
  sqlite3 instance/DB_V2.db
  SELECT * FROM <tabela> WHERE id = <problemático>;
  # O dado está correto no banco?
  ```

- [ ] **Identifique a causa raiz** (não o sintoma):
  ```
  ❌ Sintoma: "O total do pedido está errado"
  ✅ Causa raiz: "parse_brl() não foi usado na rota X, o valor '1500.50'
                  foi parseado como 150050 porque replace('.', '') removeu
                  o ponto decimal"
  ```

#### Fase 3: Correção

- [ ] **Escreva o teste primeiro** (deve FALHAR antes da correção):
  ```python
  def test_bug_X_corrigido(client, auth_user):
      """Verifica que o bug X não ocorre mais."""
      # Setup: criar condições do bug
      # Ação: executar a operação problemática
      # Verificação: resultado correto
      resp = client.post('/rota/problematica', data={...})
      assert b'resultado correto' in resp.data
  ```

- [ ] **Implemente a correção mínima:**
  - Altere apenas o necessário para corrigir a causa raiz
  - Não refatore junto com a correção (a menos que seja trivial)
  - Siga os padrões obrigatórios (AGENTS.md §3)

- [ ] **Verifique se a correção não introduz novos bugs:**
  ```bash
  # Todos os testes devem passar
  pytest tests/ -v

  # Verifique regressão nos módulos relacionados
  pytest tests/test_rbac_routes.py -v
  ```

- [ ] **Verifique se o mesmo bug existe em outros lugares:**
  ```bash
  # Busque padrões similares no código
  grep -rn "mesmo_padrao_problematico" app/
  ```

#### Fase 4: Validação

- [ ] Teste manual no browser (fluxo completo do usuário)
- [ ] Verifique multi-tenant: usuário da empresa A não vê dados da B
- [ ] Verifique RBAC: permissão correta é exigida
- [ ] Se envolve valores: verifique `parse_brl()` com diferentes formatos
- [ ] Se envolve status: verifique transições válidas e inválidas
- [ ] Commit com mensagem descritiva

---

### 10.2 Novas Funcionalidades

Checklist completo do início ao fim.

#### Fase 1: Design

- [ ] **Defina o escopo:**
  - O que a feature faz? (1 parágrafo)
  - Quais usuários/roles a usam?
  - Qual o impacto nos fluxos existentes?

- [ ] **Analise o terreno** (AGENTS.md §7):
  ```bash
  # Existe algo similar que possa ser estendido?
  grep -rn "funcionalidade_similar" app/
  # Quais modelos/serviços/rotas serão afetados?
  ```

- [ ] **Escreva o mini-plano** (AGENTS.md §8.1):
  ```
  ARQUIVOS A CRIAR:
  - app/models/novo_modelo.py
  - app/services/novo_service.py
  - app/blueprints/novo_modulo/__init__.py
  - app/blueprints/novo_modulo/routes.py
  - app/templates/novo_modulo/index.html
  - app/templates/novo_modulo/form.html
  - tests/test_novo_modulo.py

  ARQUIVOS A MODIFICAR:
  - app/models/__init__.py (adicionar import)
  - app/blueprints/__init__.py (registrar blueprint)
  - app/utils/permissions.py (adicionar permissões)
  - migrations/ (nova migração)
  ```

- [ ] **Obtenha aprovação do plano** antes de codificar

#### Fase 2: Implementação — Modelo

- [ ] Criar classe em `app/models/novo_modelo.py`:
  ```python
  from .base import TimestampMixin
  from ..extensions import db
  from ..utils import now_br

  class NovoModelo(TimestampMixin, db.Model):
      __tablename__ = "novo_modelo"

      id = db.Column(db.Integer, primary_key=True)
      company_id = db.Column(db.Integer, db.ForeignKey("companies.id"),
                             nullable=False, index=True)
      nome = db.Column(db.String(200), nullable=False)
      status = db.Column(db.String(30), default="ativo")

      # Relacionamentos (use lazy="select", NUNCA "joined")
      itens = db.relationship("NovoItem", back_populates="novo_modelo",
                              lazy="select", cascade="all, delete-orphan")
  ```

- [ ] Adicionar import em `app/models/__init__.py`
- [ ] Criar migração: `flask db migrate -m "add novo_modelo"`
- [ ] Aplicar migração: `flask db upgrade`

#### Fase 3: Implementação — Serviço

- [ ] Criar `app/services/novo_service.py`:
  ```python
  from ..extensions import db
  from ..models.novo_modelo import NovoModelo
  from ..utils import now_br
  from ..utils.audit import log_activity

  def criar(company_id: int, data: dict, user_id: int) -> NovoModelo:
      """Cria um novo registro. NÃO faz commit."""
      obj = NovoModelo(
          company_id=company_id,
          nome=data["nome"],
          status="ativo",
      )
      db.session.add(obj)
      db.session.flush()  # Gera o ID
      log_activity("novo_modelo", obj.id, company_id,
                   f"Criado: {obj.nome}", user_id)
      return obj

  def listar(company_id: int):
      """Lista registros da empresa."""
      return (NovoModelo.query
              .filter_by(company_id=company_id)
              .order_by(NovoModelo.created_at.desc())
              .all())
  ```

- [ ] **NÃO** chame `db.session.commit()` no serviço
- [ ] Chame `log_activity()` para criação/edição/exclusão

#### Fase 4: Implementação — Blueprint

- [ ] Criar `app/blueprints/novo_modulo/__init__.py`:
  ```python
  from flask import Blueprint
  novo_modulo_bp = Blueprint("novo_modulo", __name__,
                              template_folder="../../templates/novo_modulo")
  from . import routes  # noqa
  ```

- [ ] Criar `app/blueprints/novo_modulo/routes.py`:
  ```python
  from flask import render_template, request, redirect, url_for, flash
  from flask_login import login_required, current_user
  from ...utils.decorators import require_permission, require_any_permission
  from ...utils.helpers import parse_brl
  from ...services import novo_service
  from . import novo_modulo_bp

  @novo_modulo_bp.route("/novo-modulo/")
  @login_required
  @require_permission("novo.view")
  def index():
      items = novo_service.listar(current_user.company_id)
      return render_template("novo_modulo/index.html", items=items)

  @novo_modulo_bp.route("/novo-modulo/new", methods=["GET", "POST"])
  @login_required
  @require_permission("novo.create")
  def new():
      if request.method == "POST":
          obj = novo_service.criar(
              current_user.company_id,
              request.form.to_dict(),
              current_user.id
          )
          db.session.commit()
          flash("Criado com sucesso.", "success")
          return redirect(url_for("novo_modulo.index"))
      return render_template("novo_modulo/form.html")
  ```

- [ ] Registrar blueprint em `app/blueprints/__init__.py`
- [ ] Usar `parse_brl()` para qualquer valor monetário no formulário

#### Fase 5: Implementação — Permissões

- [ ] Adicionar ao `PERMISSION_CATALOG` em `app/utils/permissions.py`:
  ```python
  ("novo.view",   "Novo Módulo", "Visualizar", "Ver registros do novo módulo"),
  ("novo.create", "Novo Módulo", "Criar",      "Criar registros no novo módulo"),
  ("novo.edit",   "Novo Módulo", "Editar",     "Editar registros do novo módulo"),
  ("novo.delete", "Novo Módulo", "Excluir",    "Excluir registros do novo módulo"),
  ```

- [ ] Adicionar ao `ROLE_PERMISSION_MATRIX`:
  ```python
  "ADMIN":       {... , "novo.view", "novo.create", "novo.edit", "novo.delete"},
  "MANAGER":     {... , "novo.view", "novo.create", "novo.edit", "novo.delete"},
  "OPERATIONAL": {... , "novo.view"},
  "FINANCIAL":   {...},
  "VIEWER":      {... , "novo.view"},
  ```

#### Fase 6: Implementação — Templates

- [ ] Template de listagem com tabela
- [ ] Template de formulário com CSRF token
- [ ] Controle de UI com `{% if has_perm(...) %}`
- [ ] Usar Tailwind CSS para estilização consistente

#### Fase 7: Testes

- [ ] Teste de acesso autorizado (admin)
- [ ] Teste de acesso negado (viewer para criar/editar/excluir)
- [ ] Teste de tenant isolation (empresa A não vê dados da B)
- [ ] Teste de validação de formulário (campos obrigatórios)
- [ ] Rodar: `pytest tests/ -v`

#### Fase 8: Finalização

- [ ] Todos os testes passam
- [ ] Validação multi-tenant (AGENTS.md §9)
- [ ] Validação RBAC (AGENTS.md §10)
- [ ] Validação financeira se aplicável (AGENTS.md §11)
- [ ] Teste manual no browser
- [ ] Atualizar documentação se necessário

---

### 10.3 Refatoração

Checklist para alterações que não mudam comportamento externo.

#### Pré-Refatoração

- [ ] **Defina o objetivo claramente:**
  - O que está sendo refatorado?
  - Por quê? (performance, legibilidade, DRY, segurança)
  - Qual o escopo? (1 função, 1 arquivo, múltiplos módulos)

- [ ] **Garanta cobertura de testes antes de começar:**
  ```bash
  pytest tests/ --cov=app --cov-report=term-missing
  # Identifique áreas sem cobertura
  # Se a área a ser refatorada não tem testes, ESCREVA ANTES
  ```

- [ ] **Mapeie todos os callers:**
  ```bash
  grep -rn "funcao_a_ser_refatorada" app/
  grep -rn "ClasseASerRefatorada" app/
  ```

- [ ] **Identifique código duplicado:**
  ```bash
  # Busque padrões similares
  grep -rn "computed_total\|discount_type\|recalculate_margin" app/
  ```

#### Durante a Refatoração

- [ ] Faça alterações pequenas e incrementais (1 commit por etapa lógica)
- [ ] Rode `pytest tests/ -v` após CADA alteração
- [ ] Não altere comportamento externo (assinaturas, retornos, efeitos colaterais)
- [ ] Se extrair lógica duplicada, verifique TODOS os callers

#### Pós-Refatoração

- [ ] Todos os testes existentes passam sem modificação
- [ ] Nenhum novo warning ou erro
- [ ] Cobertura de testes não diminuiu
- [ ] Código removido não era importado por outros módulos
- [ ] `grep` pelo nome antigo não retorna resultados (se renomeou)
- [ ] Documentação atualizada se necessário

#### Checklists Específicos por Tipo

**Extrair função duplicada:**
- [ ] A função extraída está no local correto?
  - Reutilizável entre módulos → `app/utils/`
  - Lógica de negócio → `app/services/`
  - Formatação/apresentação → `app/utils/helpers.py`
- [ ] Todos os callers usam a nova função?
- [ ] A função antiga foi removida (não apenas comentada)?

**Renomear modelo/coluna:**
- [ ] **Criou migração?** (Alembic detecta renomeação automaticamente?)
- [ ] Todos os imports atualizados?
- [ ] Templates atualizados?
- [ ] Testes atualizados?

**Alterar serviço:**
- [ ] A assinatura pública mudou?
- [ ] Todos os controllers que chamam o serviço foram atualizados?
- [ ] O comportamento de commit/rollback permanece equivalente?
- [ ] `log_activity()` continua sendo chamado?

---

## 11. Debugging

### Flask Debug Mode

Com `DEBUG=True`, o servidor mostra tracebacks detalhados no navegador e no console.

### SQLAlchemy Query Log

Adicione temporariamente em `config.py`:
```python
SQLALCHEMY_ECHO = True  # Loga todas as queries SQL
```

### Logging

```python
import logging
log = logging.getLogger(__name__)
log.info("mensagem")
log.warning("alerta")
```

### Perfil comum de erros

| Erro | Causa Provável |
|------|---------------|
| `DetachedInstanceError` | Acessando relacionamento lazy fora da sessão |
| `database is locked` | Concorrência no SQLite (WAL mode mitiga) |
| `IntegrityError` | Violação de unique constraint (ex: email duplicado) |
| `404` em rota existente | Decorator `@login_required` redirecionando para login |

---

## 12. Fluxo de Trabalho Recomendado

```
1. git pull / sync
2. pytest tests/ -v           ← Garantir que tudo passa
3. Implementar feature/fix
4. pytest tests/ -v           ← Verificar regressão
5. Testar manualmente no browser
6. Commit
```
