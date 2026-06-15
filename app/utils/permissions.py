"""RBAC — catálogo canônico de permissões e matriz role→permissões.

Único ponto de verdade. Usado pelo seed (`_seed_rbac`) e pela UI admin
de gestão de roles. Não duplicar essas constantes em outros lugares.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo de permissões: (code, category, label_pt, description)
# ─────────────────────────────────────────────────────────────────────────────
PERMISSION_CATALOG = [
    # dashboard
    ("dashboard.view",     "dashboard", "Ver dashboard",              "Acessar painel inicial"),

    # cadastros básicos
    ("clients.view",       "clients",   "Clientes — ver",             "Listar e visualizar clientes"),
    ("clients.edit",       "clients",   "Clientes — editar",          "Criar/editar clientes"),
    ("clients.delete",     "clients",   "Clientes — remover",         "Soft delete de clientes"),

    ("suppliers.view",     "suppliers", "Fornecedores — ver",         "Listar e visualizar fornecedores"),
    ("suppliers.edit",     "suppliers", "Fornecedores — editar",      "Criar/editar fornecedores"),
    ("suppliers.delete",   "suppliers", "Fornecedores — remover",     "Soft delete de fornecedores"),

    ("drivers.view",       "drivers",   "Motoristas — ver",           "Listar e visualizar motoristas"),
    ("drivers.edit",       "drivers",   "Motoristas — editar",        "Criar/editar motoristas"),
    ("drivers.delete",     "drivers",   "Motoristas — remover",       "Soft delete de motoristas"),

    ("vehicles.view",      "vehicles",  "Veículos — ver",             "Listar e visualizar veículos"),
    ("vehicles.edit",      "vehicles",  "Veículos — editar",          "Criar/editar veículos"),
    ("vehicles.delete",    "vehicles",  "Veículos — remover",         "Soft delete de veículos"),

    # catálogo (serviços/categorias)
    ("catalog.view",       "catalog",   "Catálogo — ver",             "Ver serviços e categorias"),
    ("catalog.manage",     "catalog",   "Catálogo — gerenciar",       "Criar/editar/remover serviços e categorias"),

    # quotes
    ("quote.view",         "quote",     "Orçamentos — ver",           "Listar e visualizar orçamentos"),
    ("quote.create",       "quote",     "Orçamentos — criar",         "Criar novos orçamentos"),
    ("quote.edit",         "quote",     "Orçamentos — editar",        "Editar orçamentos existentes"),
    ("quote.delete",       "quote",     "Orçamentos — remover",       "Soft delete de orçamentos"),
    ("quote.approve",      "quote",     "Orçamentos — aprovar",       "Aprovar orçamentos / converter em SO"),


    # sales orders
    ("so.view",            "so",        "SO — ver",                   "Listar e visualizar Sales Orders"),
    ("so.create",          "so",        "SO — criar",                 "Criar Sales Orders"),
    ("so.edit",            "so",        "SO — editar",                "Editar Sales Orders"),
    ("so.cancel",          "so",        "SO — cancelar",              "Cancelar Sales Orders"),
    ("so.close",           "so",        "SO — fechar",                "Fechar Sales Orders"),
    ("so.reopen",          "so",        "SO — reabrir",               "Reabrir Sales Orders fechadas"),
    ("so.invoice",         "so",        "SO — faturar",               "Emitir/faturar Sales Orders"),
    ("so.delete",          "so",        "SO — remover",               "Soft delete de Sales Orders"),

    # purchase orders
    ("po.view",            "po",        "PO — ver",                   "Listar e visualizar Purchase Orders"),
    ("po.create",          "po",        "PO — criar",                 "Criar Purchase Orders"),
    ("po.edit",            "po",        "PO — editar",                "Editar Purchase Orders"),
    ("po.cancel",          "po",        "PO — cancelar",              "Cancelar Purchase Orders"),
    ("po.close",           "po",        "PO — fechar",                "Fechar Purchase Orders"),
    ("po.delete",          "po",        "PO — remover",               "Soft delete de Purchase Orders"),

    # dispatch
    ("dispatch.view",      "dispatch",  "Despacho — ver",             "Acessar centro de despacho"),
    ("dispatch.edit",      "dispatch",  "Despacho — editar",          "Atribuir/alterar despachos"),

    # financial
    ("financial.view",     "financial", "Financeiro — ver",           "Visualizar dados financeiros"),
    ("financial.manage",   "financial", "Financeiro — gerenciar",     "CRUD financeiro, baixas e pagamentos"),

    # reports
    ("reports.view",       "reports",   "Relatórios — ver",           "Acessar relatórios"),

    # admin
    ("users.manage",       "admin",     "Usuários — gerenciar",       "CRUD de usuários e atribuição de roles"),
    ("roles.manage",       "admin",     "Roles — gerenciar",          "Criar/editar roles customizadas"),
    ("settings.manage",    "admin",     "Configurações — gerenciar",  "Editar configurações da empresa"),
    ("audit.view",         "admin",     "Auditoria — ver",            "Visualizar logs de auditoria"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Roles canônicas (system roles, is_system=True — não editáveis na UI)
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_ROLES = [
    ("ADMIN",       "Administrador",     "Acesso total ao sistema"),
    ("MANAGER",     "Gerente",           "Acesso operacional + financeiro, sem gestão de usuários"),
    ("OPERATIONAL", "Operacional",       "Acesso ao comercial e operacional, sem financeiro"),
    ("FINANCIAL",   "Financeiro",        "Acesso ao financeiro e relatórios"),
    ("VIEWER",      "Consulta",          "Acesso somente leitura (sem financeiro)"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Matriz Role → Permissões (códigos canônicos)
#
# ADMIN não precisa ser listado: tem shortcut em User.has_permission()
# (sempre True). Mantido em ALL_PERMS para inspeção/UI.
# ─────────────────────────────────────────────────────────────────────────────
ALL_PERMS = {code for (code, *_rest) in PERMISSION_CATALOG}

_PERMS_BY_CATEGORY = {}
for _code, _cat, *_ in PERMISSION_CATALOG:
    _PERMS_BY_CATEGORY.setdefault(_cat, set()).add(_code)


# MANAGER: tudo exceto admin (users/roles/settings/audit)
_MANAGER_EXCLUDE = {"users.manage", "roles.manage", "settings.manage", "audit.view"}
_MANAGER_PERMS   = ALL_PERMS - _MANAGER_EXCLUDE


# OPERATIONAL: comercial + operacional, SEM financeiro, SEM admin, SEM delete-massa
_OPERATIONAL_PERMS = {
    "dashboard.view",
    "clients.view", "clients.edit",
    "suppliers.view",
    "drivers.view",
    "vehicles.view",
    "catalog.view",
    "quote.view", "quote.create", "quote.edit", "quote.approve",
    "so.view", "so.create", "so.edit", "so.close", "so.reopen",
    "po.view", "po.create", "po.edit",
    "dispatch.view", "dispatch.edit",
    "reports.view",
}


# FINANCIAL: financeiro completo + leitura de SO/PO/clients/suppliers + faturar SO
_FINANCIAL_PERMS = {
    "dashboard.view",
    "clients.view",
    "suppliers.view",
    "so.view", "so.invoice",
    "po.view",
    "financial.view", "financial.manage",
    "reports.view",
}


# VIEWER: somente .view universal, SEM financial (ajuste aprovado pelo usuário)
_VIEWER_PERMS = {
    code for code in ALL_PERMS
    if code.endswith(".view")
    and not code.startswith("financial.")
    and code not in {"audit.view"}
}


ROLE_PERMISSION_MATRIX = {
    "ADMIN":       ALL_PERMS,           # shortcut em código, mas semeado completo
    "MANAGER":     _MANAGER_PERMS,
    "OPERATIONAL": _OPERATIONAL_PERMS,
    "FINANCIAL":   _FINANCIAL_PERMS,
    "VIEWER":      _VIEWER_PERMS,
}


# ─────────────────────────────────────────────────────────────────────────────
# Mapa de migração: User.role legado (string) → role canônico
# ─────────────────────────────────────────────────────────────────────────────
LEGACY_ROLE_MAP = {
    "superadmin": "ADMIN",
    "admin":      "ADMIN",
    "manager":    "MANAGER",
    "operator":   "OPERATIONAL",
}
