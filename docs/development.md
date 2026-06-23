# Development Guide — ExecFlow_ERP_V2

> Guia completo para desenvolvimento local.

---

## 1. Pré-Requisitos

| Ferramenta | Versão | Verificação |
|-----------|--------|-------------|
| Python | 3.11+ | `python --version` |
| pip | 23+ | `pip --version` |
| Git | 2.x | `git --version` |

---

## 2. Setup Inicial

```bash
# 1. Clonar o projeto
git clone <repo-url> ExecFlow_ERP_V2
cd ExecFlow_ERP_V2

# 2. Criar virtual environment
python -m venv venv

# 3. Ativar
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / Mac

# 4. Instalar dependências de desenvolvimento
pip install -r requirements-dev.txt

# 5. Criar arquivo .env
copy .env.example .env       # Windows
# cp .env.example .env       # Linux / Mac

# 6. Executar
python app_v2.py
```

O app estará disponível em `http://127.0.0.1:5004`.

---

## 3. Configuração do `.env`

```env
# Mínimo para desenvolvimento
SECRET_KEY=dev-secret-key
FLASK_ENV=development
DATABASE_URL=sqlite:///DB_V2.db
BASE_URL=http://localhost:5004

# Opcionais
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@email.com
SMTP_PASS=sua-senha-app
```

Com `DATABASE_URL` vazio ou `sqlite:///DB_V2.db`, o sistema cria automaticamente o banco SQLite em `instance/DB_V2.db`.

---

## 4. Comandos Úteis

### Executar o App

```bash
python app_v2.py
# Servidor em http://127.0.0.1:5004
# Login: admin@executivecarsp.com / admin123
```

### Testes

```bash
# Todos os testes
pytest tests/ -v

# Um arquivo específico
pytest tests/test_rbac_routes.py -v

# Com cobertura
pytest tests/ --cov=app --cov-report=html

# Com cobertura (terminal)
pytest tests/ --cov=app --cov-report=term-missing
```

### Migrações

```bash
# Ver status das migrações
flask db current
flask db history

# Criar nova migração (após alterar modelos)
flask db migrate -m "descrição da alteração"

# Aplicar migrações
flask db upgrade

# Reverter uma migração
flask db downgrade -1
```

### Banco de Dados

```bash
# Acessar SQLite diretamente
sqlite3 instance/DB_V2.db

# Dentro do sqlite3:
.tables                    # Listar tabelas
.schema orders             # Ver schema da tabela
SELECT * FROM quotes;      # Query
.exit                      # Sair
```

### CSS (Tailwind)

```bash
# Build único
build_css.bat

# Watch mode (desenvolvimento)
tools\tailwindcss.exe -i app\static\css\tailwind.src.css -o app\static\css\tailwind.css --watch
```

### Dependências

```bash
# Instalar nova dependência
pip install <pacote>
pip freeze > requirements.txt        # Produção
pip freeze > requirements-dev.txt    # Dev (inclui pytest, etc.)
```

---

## 5. Estrutura de Testes

### Arquivos de Teste

| Arquivo | Escopo |
|---------|--------|
| `conftest.py` | Fixtures compartilhadas (app, client, auth_user, db) |
| `test_rbac_routes.py` | Testes de acesso às rotas com RBAC (55 testes) |
| `test_permissions_catalog.py` | Validação do catálogo de permissões (4 testes) |
| `test_security_hardening.py` | Rate limiter e headers de segurança (11 testes) |
| `test_tenant_isolation.py` | Isolamento multi-tenant (4 testes) |
| `test_decorators_and_audit.py` | Decorators e auditoria (11 testes) |

### Fixtures Importantes

```python
# conftest.py
@pytest.fixture
def app():          # Flask app em modo testing (SQLite :memory:)
@pytest.fixture
def client(app):    # Test client do Flask
@pytest.fixture
def auth_user(app): # Usuário admin autenticado
```

### Escrevendo um Novo Teste

```python
def test_minha_feature(client, auth_user):
    """Testa se a feature X funciona."""
    # Login
    client.post('/login', data={
        'email': 'admin@executivecarsp.com',
        'password': 'admin123'
    })

    # Ação
    resp = client.get('/minha-rota/')
    assert resp.status_code == 200

    # Verificação
    assert b'texto esperado' in resp.data
```

---

## 6. Criando uma Nova Feature

### Passo a Passo

1. **Modelo** (`app/models/novo_modelo.py`):
   ```python
   from .base import TimestampMixin
   from ..extensions import db

   class NovoModelo(TimestampMixin, db.Model):
       __tablename__ = "novo_modelo"
       id = db.Column(db.Integer, primary_key=True)
       company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
       nome = db.Column(db.String(200), nullable=False)
       status = db.Column(db.String(30), default="ativo")
   ```

2. **Migração:**
   ```bash
   flask db migrate -m "add novo_modelo table"
   flask db upgrade
   ```

3. **Serviço** (`app/services/novo_service.py`):
   ```python
   from ..extensions import db
   from ..models.novo_modelo import NovoModelo

   def criar_novo(company_id, data):
       obj = NovoModelo(company_id=company_id, nome=data["nome"])
       db.session.add(obj)
       db.session.flush()
       return obj
   ```

4. **Blueprint** (`app/blueprints/novo/routes.py`):
   ```python
   from flask import render_template, request, redirect, url_for, flash
   from flask_login import login_required, current_user
   from ...utils.decorators import require_permission
   from . import novo_bp

   @novo_bp.route("/")
   @login_required
   @require_permission("novo.view")
   def index():
       items = NovoModelo.query.filter_by(company_id=current_user.company_id).all()
       return render_template("novo/index.html", items=items)
   ```

5. **Template** (`app/templates/novo/index.html`):
   ```html
   {% extends "base.html" %}
   {% block content %}
   <h1>Novo Módulo</h1>
   {% for item in items %}
     <p>{{ item.nome }}</p>
   {% endfor %}
   {% endblock %}
   ```

6. **Permissões** (`app/utils/permissions.py`):
   Adicionar ao `PERMISSION_CATALOG` e `ROLE_PERMISSION_MATRIX`.

7. **Testes** (`tests/test_novo.py`):
   ```python
   def test_novo_index(client, auth_user):
       resp = client.get('/novo/')
       assert resp.status_code == 200
   ```

---

## 7. Debugging

### Flask Debug Mode

Com `FLASK_ENV=development`, o servidor Flask exibe tracebacks detalhados no navegador.

### SQLAlchemy Query Log

Adicionar temporariamente em `config.py`:
```python
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True  # ← Loga todas as queries SQL no console
```

### Logging na Aplicação

```python
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug info")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Erros Comuns e Soluções

| Erro | Causa | Solução |
|------|-------|---------|
| `DetachedInstanceError` | Acessando relacionamento lazy fora da sessão | Use `joinedload()` ou acesse dentro do `with app.app_context()` |
| `database is locked` | Concorrência SQLite | WAL mode mitiga; feche outras conexões |
| `IntegrityError: UNIQUE constraint failed` | Email/número duplicado | Verifique antes de inserir |
| `404 Not Found` | Rota não registrada | Verifique `register_blueprints()` em `__init__.py` |
| `405 Method Not Allowed` | Método HTTP errado | Verifique `methods=["GET", "POST"]` |
| `CSRF token missing` | Form sem `{{ csrf_token() }}` | Adicione no template ou use `WTF_CSRF_ENABLED=False` em testes |

---

## 8. Resetar o Ambiente de Desenvolvimento

```bash
# Deletar banco de dados
del instance\DB_V2.db

# Limpar cache Python
del /s /q app\__pycache__

# Recomeçar
python app_v2.py  # Recria banco com seed data
```

---

## 9. Convenções de Código

### Nomenclatura

| Elemento | Convenção | Exemplo |
|----------|-----------|---------|
| Modelos | PascalCase singular | `PurchaseOrder` |
| Tabelas | snake_case plural | `purchase_orders` |
| Blueprints | snake_case + `_bp` | `purchase_orders_bp` |
| Rotas | kebab-case URL | `/purchase-orders/` |
| Serviços | snake_case | `purchase_order_service.py` |
| Funções | snake_case | `generate_payments()` |

### Imports

```python
# Ordem: stdlib → third-party → app
import os
from datetime import date

from flask import render_template
from flask_login import login_required

from ...models.order import Order
from ...utils.decorators import require_permission
```

### Docstrings

```python
def funcao(param: str) -> bool:
    """Faz X com Y. Retorna True se sucesso."""
```

---

## 10. CI/CD Local

Não há pipeline CI configurado. Para validação manual:

```bash
# Antes de cada commit
pytest tests/ -v                    # Testes
python -m py_compile app_v2.py     # Sintaxe Python
```
