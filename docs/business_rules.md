# Business Rules — App_Orcamentos_V2

> Regras de negócio extraídas do código real. Nada foi inventado.

---

## 1. Fluxo de Negócio Principal

```
┌─────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Quote  │────▶│  Order   │────▶│ ServiceOrder │────▶│  Financeiro  │
│Orçamento│     │Pedido    │     │  (Despacho)  │     │RevenueEntry  │
│         │     │Venda (SO)│     │              │     │OperationCost │
└─────────┘     └──────────┘     └──────────────┘     └──────────────┘
                      │
                      ▼
               ┌──────────────┐
               │PurchaseOrder │
               │Ordem Compra  │
               │  (PO)        │
               └──────────────┘
```

### 1.1 Descrição do Fluxo

1. **Quote (Orçamento):** Vendedor cria orçamento para cliente com itens de serviço. Envia PDF. Cliente aprova ou rejeita.
2. **Quote → Order:** Ao aprovar, o vendedor converte o orçamento em um Pedido de Venda (Sales Order).
3. **Order → ServiceOrder:** O pedido gera uma Ordem de Serviço para despacho (motorista, veículo, rota).
4. **Order → PurchaseOrder:** Se o serviço for terceirizado, gera Ordem de Compra para fornecedor.
5. **Financeiro:** Receitas, custos e pagamentos são registrados vinculados à ServiceOrder.

---

## 2. Máquinas de Estado

### 2.1 Quote (Orçamento)

```
pendente ──────▶ aprovado ──────▶ reserva_confirmada
   │                  │
   └──▶ reprovado ◀───┘
```

| Status | Significado | Ação |
|--------|-------------|------|
| `pendente` | Aguardando resposta do cliente | Editável |
| `aprovado` | Cliente aprovou | Pode gerar Order/Booking |
| `reprovado` | Cliente rejeitou | Fim do fluxo |
| `reserva_confirmada` | Booking/OS criados | Bloqueado para edição |

**Campos de rastreamento:**
- `approved_at` / `approved_by`
- `rejected_at` / `rejected_by` / `rejection_reason`
- `valid_until` (validade do orçamento)

### 2.2 Order (Pedido de Venda)

```
novo ──▶ aberto ──▶ faturado ──▶ concluido
              │                      ▲
              └──▶ cancelado ────────┘ (reabrir)
```

| Status | Significado | Ação |
|--------|-------------|------|
| `novo` | Criado, não iniciado | Editável |
| `aberto` | Em andamento | Pode faturar |
| `faturado` | Nota fiscal emitida | Pode concluir |
| `concluido` | Finalizado com sucesso | Bloqueado |
| `cancelado` | Cancelado | Pode reabrir |

**Regras:**
- Ao faturar, gera `OrderPayment` (parcelas) baseado em `payment_terms`
- `computed_total` = subtotal − desconto + frete + outros custos
- Desconto pode ser percentual (`%`) ou valor fixo (`R$`)
- Margem = receita − custo total dos POs vinculados

**Campos de rastreamento (6 timestamps + 6 users):**
- `created_at` / `created_by`
- `opened_at` / `opened_by`
- `invoiced_at` / `invoiced_by`
- `closed_at` / `closed_by`
- `cancelled_at` / `cancelled_by`
- `reopened_at` / `reopened_by`

### 2.3 PurchaseOrder (Ordem de Compra)

```
rascunho ──▶ aberto ──▶ enviado ──▶ aprovado ──▶ em_execucao ──▶ concluido
                                                     │
                                                     └──▶ cancelado
```

| Status | Significado |
|--------|-------------|
| `rascunho` | Sendo editado |
| `aberto` | Formalizado |
| `enviado` | Enviado ao fornecedor |
| `aprovado` | Fornecedor aprovou |
| `em_execucao` | Serviço em andamento |
| `concluido` | Finalizado |
| `cancelado` | Cancelado |

**Regras:**
- `faturar`: exige fornecedor definido e pagamentos gerados
- `conclude`: recalcula margem do Order pai
- Mesma lógica de desconto do Order (`%` ou `R$`)

### 2.4 ServiceOrder (Ordem de Serviço)

```
criado ──▶ agendado ──▶ atribuido ──▶ em_execucao ──▶ finalizado
                                         │
                                         └──▶ cancelado
                           (confirmado_cliente: opcional)
```

| Status | Significado |
|--------|-------------|
| `criado` | OS gerada automaticamente |
| `agendado` | Data/hora definidos |
| `atribuido` | Motorista ou fornecedor designado |
| `confirmado_cliente` | Cliente confirmou dados |
| `em_execucao` | Serviço iniciado (`executed_at`) |
| `finalizado` | Concluído (`closed_at`) |
| `cancelado` | Cancelado |

**Regras de atribuição:**
- Pode ser `internal` (motorista + veículo próprio) ou `external` (fornecedor)
- Apenas uma atribuição ativa por vez (`is_current=True`)
- Atribuir fornecedor cria automaticamente `SupplierPayment` e `OperationCost`

### 2.5 Booking (Legado)

```
pendente ──▶ confirmado ──▶ em_andamento ──▶ concluido
```

Em processo de substituição pelo modelo ServiceOrder.

---

## 3. Regras Financeiras

### 3.1 Margem

Definido em [`margin_service.py`](../app/services/margin_service.py):

```
margin_amount = order.computed_total − sum(po.computed_total for non-cancelled POs)
```

- Calculado para Order (Sales Order)
- POs cancelados são excluídos do cálculo
- Armazenado denormalizado em `order.margin_amount` e `order.total_po_cost`
- ServiceOrder também tem `margin_amount` = `revenue_amount − total_cost_amount − supplier_amount`

### 3.2 Precificação de Serviços

Definido em [`ServicePricing.effective_price()`](../app/models/service.py):

| Tipo | Cálculo |
|------|---------|
| `recibo` | `price_base` |
| `nf` | `price_nf` = `price_base × 1.10` |
| `cartao` | `price_cartao` = `price_base × 1.065` |
| `nf_cartao` | `price_nf_cartao` = `price_base × 1.165` |

Taxas configuráveis via env: `NF_RATE` (default 0.10), `CARD_RATE` (default 0.065).

### 3.3 Billing Types

| Código | Descrição |
|--------|-----------|
| `recibo` | Recibo simples |
| `nf` | Nota Fiscal |
| `cartao` | Cartão de crédito/débito |
| `nf_cartao` | NF + Cartão |

### 3.4 Payment Terms

Formatos aceitos: `"À VISTA"`, `"30 DIAS"`, `"30/60/90 DIAS"`, `"ENTRADA + 30 DIAS"`, etc.

Ao faturar um Order ou PO, o sistema gera parcelas automaticamente baseado no `payment_terms`.

### 3.5 Baixa de Pagamentos

Quando um pagamento é liquidado:
1. Atualiza `paid_amount` e `paid_at` no `OrderPayment`/`POPayment`
2. Cria/atualiza `FinancialRecord` (legado) ou `FinancialEntry` (V4) como espelho
3. Se todos os pagamentos foram pagos, transiciona Order para `concluido` ou PO para `concluido`
4. Recalcula margem

---

## 4. Regras de Autorização (RBAC)

### 4.1 Roles do Sistema

| Role | Código | Acesso |
|------|--------|--------|
| Admin | `ADMIN` | Todas as permissões (shortcut `ALL_PERMS`) |
| Manager | `MANAGER` | CRUD completo, sem reset de dados |
| Operational | `OPERATIONAL` | Despacho, OS, drivers, veículos |
| Financial | `FINANCIAL` | Financeiro, relatórios, faturamento |
| Viewer | `VIEWER` | Apenas leitura |

### 4.2 Categorias de Permissão

| Categoria | Permissões |
|-----------|-----------|
| `quote` | view, create, edit, approve, delete |
| `so` | view, create, edit, invoice, close, cancel, reopen, delete |
| `po` | view, create, edit, close, cancel, delete |
| `dispatch` | view, edit |
| `booking` | view, edit |
| `clients` | view, edit, delete |
| `drivers` | view, edit, delete |
| `vehicles` | view, edit, delete |
| `suppliers` | view, edit, delete |
| `catalog` | view, manage |
| `financial` | view, manage |
| `reports` | view |
| `users` | manage |
| `settings` | manage |
| `audit` | view |

---

## 5. Regras de Soft Delete

Modelos com `SoftDeleteMixin`:

- Client, Driver, Supplier, Vehicle, ServiceOrder, Booking, FinancialRecord

**Comportamento:**
- `soft_delete()` define `deleted_at = now()`
- Queries devem filtrar `deleted_at.is_(None)` para excluir registros deletados
- `is_deleted` property retorna `bool(deleted_at)`
- Registros não são removidos fisicamente (preserva integridade referencial e histórico)

---

## 6. Regras de Numeração

| Entidade | Prefixo | Formato Data | Escopo |
|----------|---------|-------------|--------|
| Quote | `RFQ-` | YYMMDD | company_id |
| Order | `SO-` | YYMMDD | company_id |
| ServiceOrder | `OS-` | YYMMDD | company_id |
| PurchaseOrder | `PO-` | YYMMDD | company_id |
| Booking | `RES-` | YYYY | company_id |

**Algoritmo:** Busca último registro da empresa com `LIKE "PREFIX-*"`, extrai sequência, incrementa.

---

## 7. Regras de Multi-Tenancy

- Cada `User` pertence a uma `Company`
- Toda entidade de negócio tem `company_id`
- Queries sempre filtram por `current_user.company_id`
- Tabelas globais (sem company_id): `Permission`, `Role`, `State`, `VehicleCategory`
- Serviços (`Service`) podem ser globais (`company_id IS NULL`) ou específicos

---

## 8. Regras de Auditoria

- `AuditLog` registra: entidade, entity_id, company_id, user_id, ação, IP, user_agent
- Operações que geram auditoria: criar, editar, excluir, transições de status, baixa financeira
- Função: `log_activity(entity, entity_id, company_id, action, user_id)`
- O caller é responsável pelo `db.session.commit()`

---

## 9. Categorias de Veículos

18 categorias definidas em `VehicleCategory` (constante `CATEGORIES` em [`vehicle.py`](../app/models/vehicle.py)):

```
Executivo, Sedan, Premium, Black, Van, Micro-Ônibus, Ônibus,
Helicóptero, Avião, Barco, Blindado, Moto, Caminhão,
Van Cargo, Caminhonete, Pickup, Bicicleta, Outros
```

Cada categoria pode ter `category_type`: `transport`, `cargo`, `special`, `water`, `air`, `other`.

---

## 10. Tipos de Motorista

| Tipo | Significado |
|------|-------------|
| `Monolíngue` | Motorista que fala apenas português |
| `Bilíngue` | Motorista bilíngue (português + inglês) |

Afeta o preço do serviço (ServicePricing tem `driver_type` como parte da chave única).

---

## 11. Idiomas Suportados

| Código | Idioma | Uso |
|--------|--------|-----|
| `pt` | Português | Padrão |
| `en` | Inglês | PDFs para clientes estrangeiros |

Tradução de serviços e observações via `deep-translator` (Google Translate) em tempo de geração de PDF.

---

## 13. Validação de Impacto Financeiro

> **Use esta seção ao modificar qualquer código que afete cálculos financeiros.**

### 13.1 Pontos Sensíveis

Estes arquivos exigem validação financeira extra quando modificados:

| Arquivo | Função/Campo Crítico | O Que Validar |
|---------|---------------------|---------------|
| `models/order.py` | `computed_total`, `margin_pct` | Fórmula de desconto, subtotal, frete |
| `models/purchase_order.py` | `computed_total` | Idêntico ao Order — consistência |
| `models/service_order.py` | `recalculate_margin()` | revenue − cost − supplier |
| `models/service.py` | `effective_price()` | Multiplicadores NF/cartão |
| `services/margin_service.py` | `calculate_order_margin()` | revenue = computed_total, cost = sum(POs) |
| `services/order_service.py` | `baixa()`, `faturar()` | Geração de parcelas, auto-close |
| `services/purchase_order_service.py` | `baixa()`, `faturar()` | Idem |
| `utils/helpers.py` | `parse_brl()` | Parsing correto de todos os formatos |

### 13.2 Procedimento de Validação

Sempre que modificar um dos arquivos acima:

1. **Execute os testes existentes:**
   ```bash
   pytest tests/ -v
   ```

2. **Teste manualmente os cenários financeiros críticos:**
   - Criar orçamento com 3 itens → Verificar `computed_total`
   - Aplicar desconto % e R$ → Verificar cálculo correto
   - Gerar parcelas → Verificar soma = `computed_total`
   - Dar baixa em pagamento → Verificar status transiciona
   - Dar baixa no último pagamento → Verificar auto-close
   - Verificar margem → `revenue − po_cost = margin`

3. **Teste `parse_brl()` com formatos variados:**
   ```python
   from app.utils.helpers import parse_brl
   # Deve retornar 1500.50 para todos estes:
   assert parse_brl("1.500,50") == 1500.50
   assert parse_brl("1500,50") == 1500.50
   assert parse_brl("1500.50") == 1500.50
   assert parse_brl("R$ 1.500,50") == 1500.50
   ```

### 13.3 Como Auditar Consistência Financeira

Use estas queries para verificar consistência no banco:

```sql
-- Orders com total inconsistente (soma dos itens ≠ total_amount)
SELECT o.id, o.number, o.total_amount,
       (SELECT COALESCE(SUM(oi.total_price), 0) FROM order_items oi WHERE oi.order_id = o.id) AS items_sum
FROM orders o
WHERE o.total_amount != (SELECT COALESCE(SUM(oi.total_price), 0) FROM order_items oi WHERE oi.order_id = o.id);

-- POs com status 'concluido' mas sem pagamentos
SELECT po.id, po.number, po.status
FROM purchase_orders po
WHERE po.status = 'concluido'
  AND (SELECT COUNT(*) FROM po_payments pop WHERE pop.po_id = po.id) = 0;

-- ServiceOrders com margem inconsistente
SELECT os.id, os.code, os.revenue_amount, os.total_cost_amount, os.supplier_amount, os.margin_amount,
       (os.revenue_amount - os.total_cost_amount - os.supplier_amount) AS calculated_margin
FROM service_orders os
WHERE os.margin_amount != (os.revenue_amount - os.total_cost_amount - os.supplier_amount);

-- Pagamentos pagos com paid_amount > amount
SELECT p.id, p.amount, p.paid_amount
FROM order_payments p
WHERE p.paid_amount > p.amount;

SELECT p.id, p.amount, p.paid_amount
FROM po_payments p
WHERE p.paid_amount > p.amount;
```

---

## 14. Fuso Horário

Todo o sistema usa horário de Brasília (UTC-3) via `now_br()` em [`app/utils/__init__.py`](../app/utils/__init__.py). Datetimes são armazenados como naive (sem `tzinfo`).
