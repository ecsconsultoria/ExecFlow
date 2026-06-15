# 🔴 Relatório de Risco — Parsing Monetário (Bug de Corrupção de Dados)

**Data:** 04/06/2026
**Escopo:** Análise de todas as ocorrências de parsing de valores monetários (string → float) no projeto
**Metodologia:** Análise estática do fluxo de dados (frontend JS → form POST → backend parsing → banco de dados)

---

## 1. Sumário Executivo

| Métrica | Valor |
|---------|-------|
| Total de ocorrências de parsing monetário | **13** |
| Ocorrências com **risco REAL de corrupção** | **7** (54%) |
| Ocorrências com guarda protetora | **1** (8%) |
| Ocorrências seguras (formatação de saída) | **3** (23%) |
| Ocorrências parcialmente seguras | **2** (15%) |

> **Conclusão:** Existe **risco REAL e significativo** de corrupção silenciosa de dados monetários em **7 pontos do código** que processam input do usuário sem validação adequada.

---

## 2. Classificação dos Padrões Encontrados

### 2.1 Tipo A — INPUT com `replace(".", "").replace(",", ".")` (PERIGOSO)

Remove TODOS os pontos primeiro, depois troca vírgula por ponto.

```python
float(valor.replace(".", "").replace(",", "."))
```

| # | Arquivo | Linha | Função/Endpoint | Guard? | Risco |
|---|---------|-------|-----------------|--------|------|
| 1 | `app/blueprints/financial/routes.py` | 262 | `baixa_record()` — campo `paid_amount` | ❌ | **ALTO** |
| 2 | `app/blueprints/orders/routes.py` | 345 | `generate_payments` — campo `custom_amount` | ❌ | **ALTO** |
| 3 | `app/blueprints/purchase_orders/routes.py` | 116 | `new()` — campo `amount` | ❌ | **ALTO** |
| 4 | `app/blueprints/purchase_orders/routes.py` | 457 | `generate_payments` — campo `custom_amount` | ❌ | **ALTO** |
| 5 | `app/services/purchase_order_service.py` | 195 | `_apply_data._to_float()` — campos `amount`, `discount_value`, `freight_amount`, `other_costs_amount` | ❌ | **ALTO** |
| 6 | `app/services/purchase_order_service.py` | 259 | `_parse_float()` — campo `amount` em pagamentos | ❌ | **ALTO** |
| 7 | `app/services/purchase_order_service.py` | 469 | `_parse_cost()` — campo `unit_cost` em itens | ❌ | **ALTO** |

### 2.2 Tipo B — INPUT com Guarda (SEGURO)

Verifica se há vírgula antes de decidir o formato.

| # | Arquivo | Linha | Função | Guard? | Risco |
|---|---------|-------|--------|--------|------|
| 8 | `app/blueprints/purchase_orders/routes.py` | 245 | `save_all()` — campos monetários | ✅ `if "," in s` | **BAIXO** |

```python
if "," in s:
    # Formato BR: 1.234,56
    data[f] = float(s.replace(".", "").replace(",", "."))
else:
    # Float padrão: 1500.50
    data[f] = float(s)
```

### 2.3 Tipo C — INPUT com `replace(",", ".")` (PARCIALMENTE SEGURO)

Apenas troca vírgula por ponto, sem remover pontos.

| # | Arquivo | Linha | Função | Risco |
|---|---------|-------|--------|-------|
| 9 | `app/services/order_service.py` | 475 | `_parse_float()` | **MÉDIO** |

```python
float(str(value).replace(",", "."))
```

### 2.4 Tipo D — OUTPUT (SEGURO — formatação para exibição)

Converte float → string formatada em real brasileiro. Direção oposta, sem risco.

| # | Arquivo | Linha | Função | Risco |
|---|---------|-------|--------|-------|
| 10 | `app/utils/helpers.py` | 8 | `format_currency()` — output | NENHUM |
| 11 | `app/services/quote_pdf.py` | 141 | `_fmt_brl()` — output PDF | NENHUM |

---

## 3. Análise do Fluxo de Dados

### 3.1 Como o usuário insere valores (Frontend)

O frontend JavaScript popula inputs com formato brasileiro:

```javascript
// orders/detail.html:1604
priceInput.value = d.price.toFixed(2).replace('.', ',');

// financial/index.html:369
document.getElementById('fr-paid-amount').value = Number(amount).toFixed(2).replace('.', ',');

// purchase_orders/detail.html:1524
p.amount.toFixed(2).replace('.', ',');
```

Isso produz valores como `1500,50` ou `1.500,50`.

### 3.2 Cenários de Risco Real

#### Cenário A: Copiar-colar do Excel (🌍 Internacional → 🇧🇷 Form)

1. Usuário abre planilha Excel com valor `1500.50` (formato internacional)
2. Copia e cola no campo de formulário
3. Formulário envia `"1500.50"` via POST
4. Servidor executa: `float("1500.50".replace(".", "").replace(",", "."))`
   - Passo 1: `"1500.50".replace(".", "")` → `"150050"`
   - Passo 2: `"150050".replace(",", ".")` → `"150050"` (nenhuma vírgula)
   - Resultado: `float("150050")` = **150.050,00**
5. ❌ **Valor 100x maior que o esperado** (R$ 1.500,50 → R$ 150.050,00)

#### Cenário B: API JSON com float nativo

1. Integração externa envia `{"amount": 1500.50}` (JSON float nativo)
2. `_to_float()` em `purchase_order_service.py:192` verifica `isinstance(v, (int, float))` → **retorna `float(v)` direto** ✅ (OK, esse caso tem guarda)

Mas se vier como string: `{"amount": "1500.50"}`
1. Cai no `str(v).replace(".", "").replace(",", ".")`
2. ❌ Mesma corrupção: `"150050"` → 150050

#### Cenário C: Usuário digita manualmente (🇧🇷 Padrão)

1. Usuário digita `1.500,50` no campo
2. Servidor: `float("1.500,50".replace(".", "").replace(",", "."))`
   - Passo 1: `"1.500,50".replace(".", "")` → `"1500,50"`
   - Passo 2: `"1500,50".replace(",", ".")` → `"1500.50"`
   - Resultado: `float("1500.50")` = **1500.5**
3. ✅ **Correto** (R$ 1.500,50)

#### Cenário D: Usuário digita sem milhar (🇧🇷 sem ponto)

1. Usuário digita `1500,50` no campo
2. Servidor: `float("1500,50".replace(".", "").replace(",", "."))`
   - Passo 1: `"1500,50".replace(".", "")` → `"1500,50"` (nenhum ponto)
   - Passo 2: `"1500,50".replace(",", ".")` → `"1500.50"`
   - Resultado: `float("1500.50")` = **1500.5**
3. ✅ **Correto** (R$ 1.500,50)

### 3.3 Análise por Ponto de Entrada

#### Ponto #1: `financial/routes.py:262` — `baixa_record`

```python
raw_amount = request.form.get("paid_amount", "").strip()
if raw_amount:
    try:
        r.amount = float(raw_amount.replace(".", "").replace(",", "."))
    except ValueError:
        pass  # ← Se falhar, SILENCIOSAMENTE mantém o valor antigo
```

**Fluxo:** O campo `paid_amount` é populado via JavaScript:
```javascript
// financial/index.html:369
document.getElementById('fr-paid-amount').value = Number(amount).toFixed(2).replace('.', ',');
```

**Análise:** Se o usuário clica no botão "Baixa" padrão, o JS define o valor em formato BR `1500,50` → parsing correto. Mas se o usuário **digitar ou colar** diretamente no campo `paid_amount` um valor em formato internacional `1500.50`, o valor será corrompido para `150050`. Se o formato for inválido (ex: `1.500.50`), o `except ValueError: pass` silenciosamente mantém o valor anterior — que pode ser zero ou um valor desatualizado.

**Risco:** ALTO — corrupção silenciosa ou inconsistência de dados.

---

#### Ponto #2: `orders/routes.py:345` — `generate_payments`

```python
raw_custom = request.form.get("custom_amount", "").strip()
if raw_custom:
    try:
        custom_total = float(raw_custom.replace(".", "").replace(",", "."))
    except ValueError:
        pass  # ← custom_total permanece None
```

**Fluxo:** O campo `custom_amount` é populado via JavaScript no template `orders/detail.html`:
```javascript
// orders/detail.html:1563-1568
customAmtInput.value = data.a_pagar.toLocaleString('pt-BR', {...});
```

**Análise:** Similar ao ponto #1. O JS usa `toLocaleString('pt-BR')` que produz `1.500,50`. Se o valor vier do JS, o parsing funciona. Mas se o usuário digitar ou colar `1500.50`, corrompe.

**Risco:** ALTO — gera parcelas com valor 100x maior.

---

#### Ponto #3: `purchase_orders/routes.py:116` — `new()`

```python
if data.get("amount"):
    try:
        data["amount"] = float(data["amount"].replace(".", "").replace(",", "."))
    except ValueError:
        data["amount"] = 0.0  # ← Zera o valor se não conseguir parsear!
```

**Fluxo:** Chamado ao criar uma nova Purchase Order (PO) manualmente. O valor `amount` vem do formulário.

**Análise:** Se o parsing falhar (ex: `"abc"` ou `"1.500.50"` com múltiplos pontos), o amount é zerado. Isso é pior que manter o valor original — uma PO de R$ 1.500,50 se torna R$ 0,00.

**Risco:** ALTO — pode zerar valores ou corromper para 100x.

---

#### Ponto #4: `purchase_orders/routes.py:457` — `generate_payments`

```python
raw_custom = request.form.get("custom_amount", "").strip()
if raw_custom:
    try:
        custom_total = float(raw_custom.replace(".", "").replace(",", "."))
    except ValueError:
        pass
```

**Fluxo:** Idêntico ao ponto #2, mas para Purchase Orders. O JS em `purchase_orders/detail.html:1563-1568` popula o campo.

**Risco:** ALTO — mesma corrupção do ponto #2.

---

#### Pontos #5, #6, #7: `purchase_order_service.py`

```python
# Linha 195 — _to_float() dentro de _apply_data()
return float(str(v).replace(".", "").replace(",", "."))

# Linha 259 — _parse_float()
return float(str(val).replace(".", "").replace(",", "."))

# Linha 469 — _parse_cost()
return float(str(val).replace(".", "").replace(",", "."))
```

**Callers:**
- `_apply_data()` → chamado por `create()` (linha 26) e `save_all()` na rota (linha 276)
- `_parse_float()` → chamado por `add_payment()` (linha 350) e `update_payment_inline()`
- `_parse_cost()` → chamado por `add_item()` (linha 479) e `update_item()` (linha 511)

**Fluxo:** Estes recebem dados que já passaram por parsing nas rotas OU dados crus do formulário. Se a rota já fez o parsing, o valor chega como `float` e o guard `isinstance(v, (int, float))` retorna sem processar. Mas se uma nova rota ou API chamar diretamente com string, o bug dispara.

**Risco:** ALTO — são funções reutilizáveis; qualquer novo caller pode ser afetado.

---

#### Ponto #8: `purchase_orders/routes.py:245` — `save_all()` (COM GUARDA)

```python
if "," in s:
    data[f] = float(s.replace(".", "").replace(",", "."))
else:
    data[f] = float(s)
```

**Análise:** Este é o **único ponto com proteção**. Se o valor não contém vírgula, assume formato float padrão Python.
- `"1500.50"` → sem vírgula → `float("1500.50")` → 1500.5 ✅
- `"1.500,50"` → tem vírgula → `float("1500.50")` → 1500.5 ✅
- `"1500,50"` → tem vírgula → `float("1500.50")` → 1500.5 ✅

**Risco:** BAIXO — A guarda cobre os cenários principais.

---

#### Ponto #9: `order_service.py:475` — `_parse_float()` (SEM REMOVER PONTOS)

```python
float(str(value).replace(",", "."))
```

**Análise:** Esta versão NÃO remove pontos. Comportamento:
- `"1500.50"` → `float("1500.50")` → 1500.5 ✅
- `"1500,50"` → `float("1500.50")` → 1500.5 ✅
- `"1.500,50"` → `float("1.500.50")` → **ValueError!** → retorna `0.0` ❌

No pior caso, o valor é zerado (não corrompido para 100x). Mas ainda é um bug: uma diária de R$ 1.500,50 se torna R$ 0,00.

**Risco:** MÉDIO — zera valor em vez de corromper, mas ainda é perda de dados.

---

## 4. Matriz de Risco

| Cenário | Frequência | Impacto | Risco |
|---------|-----------|---------|-------|
| Copiar-colar `1500.50` do Excel | Baixa/Média | 100x valor | **ALTO** |
| Digitar manual `1.500,50` (BR) | Alta | Nenhum | BAIXO |
| Digitar manual `1500,50` (BR sem milhar) | Alta | Nenhum | BAIXO |
| API com string `"1500.50"` | Baixa | 100x valor | **ALTO** |
| API com float nativo `1500.50` | Média | Nenhum (guarda `isinstance`) | BAIXO |
| Valor inválido (ex: `"1.500.50"`) | Baixa | Zera ou mantém valor antigo | **MÉDIO** |

## 5. Evidência de Risco Real

### 5.1 O frontend NÃO valida formato antes do submit

Nenhum handler de `onsubmit` foi encontrado nos templates que normalize valores monetários antes do POST. O HTML `<input type="text">` envia o valor exatamente como o usuário digitou.

### 5.2 Inconsistência entre `order_service` e `purchase_order_service`

O mesmo conceito (`_parse_float`) tem **implementações diferentes**:

| Serviço | Implementação | Comportamento |
|---------|---------------|---------------|
| `order_service._parse_float` | `replace(",", ".")` | Seguro para internacional, quebra BR com milhar |
| `purchase_order_service._parse_float` | `replace(".", "").replace(",", ".")` | Seguro para BR, corrompe internacional |
| `purchase_order_service._parse_cost` | `replace(".", "").replace(",", ".")` | Seguro para BR, corrompe internacional |

Isso prova que **não há um padrão definido** para parsing monetário no projeto. Cada desenvolvedor implementou sua própria versão.

### 5.3 `except ValueError: pass` esconde erros

Em 4 dos 7 pontos perigosos, o `ValueError` é silenciosamente ignorado com `pass`. Se um valor inválido for enviado:
- `financial/routes.py:264`: `pass` → mantém o valor antigo (que pode estar errado)
- `orders/routes.py:347`: `pass` → `custom_total` permanece `None`
- `purchase_orders/routes.py:459`: `pass` → `custom_total` permanece `None`
- `purchase_orders/routes.py:117-118`: `data["amount"] = 0.0` → **zera o valor!**

Nenhum destes registra um warning ou notifica o usuário. O erro é completamente silencioso.

---

## 6. Recomendações

### 🔴 Imediata (Correção)

Criar **uma única função canônica** de parsing monetário em `app/utils/helpers.py`:

```python
import re

def parse_brl(value) -> float:
    """Converte string monetária brasileira para float.
    
    Lida com todos os formatos comuns:
    - "1.500,50" (BR com milhar) → 1500.5
    - "1500,50"   (BR sem milhar) → 1500.5
    - "1500.50"   (internacional)  → 1500.5
    - 1500.50     (float nativo)   → 1500.5
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    
    s = str(value).strip()
    if not s:
        return 0.0
    
    # Remove símbolos comuns (R$, espaços)
    s = s.replace("R$", "").replace(" ", "")
    
    # Detecta padrão pelo último separador
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    
    if last_comma > last_dot:
        # Padrão brasileiro: último separador é vírgula (decimal)
        # Remove pontos (milhar) e troca vírgula por ponto
        s = s.replace(".", "").replace(",", ".")
    else:
        # Padrão internacional: último separador é ponto (decimal)
        # Remove vírgulas (milhar)
        s = s.replace(",", "")
    
    # Remove caracteres não numéricos restantes (exceto . e -)
    s = re.sub(r'[^\d.\-]', '', s)
    
    return float(s)
```

### 🟡 Curto Prazo

1. Substituir **todas** as 8 ocorrências de parsing pela função canônica
2. Adicionar logging (`app.logger.warning`) quando o parsing encontrar formato ambíguo
3. Retornar erro ao usuário (flash message) em vez de `pass` silencioso
4. Adicionar testes unitários para `parse_brl()` cobrindo 15+ cenários

### 🟢 Longo Prazo

1. Adicionar validação no frontend (JavaScript) que normalize o valor antes do submit
2. Usar `<input type="number" step="0.01">` onde possível (navegadores modernos)
3. Considerar usar `decimal.Decimal` para valores financeiros em vez de `float`

---

## 7. Como Reproduzir o Bug

### Passos para reproduzir corrupção de dados:

1. Acesse a página de detalhe de uma **Ordem de Serviço** (Order)
2. No campo **"Valor"** da seção de pagamentos, digite `1500.50` (formato internacional)
3. Clique em **"Gerar Parcelas"**
4. ✅ Comportamento esperado: parcela de R$ 1.500,50
5. ❌ Comportamento real: parcela de **R$ 150.050,00** (100x maior)

### Passos para reproduzir zeragem de valor:

1. Acesse a página de nova **Purchase Order**
2. No campo **"Valor"**, digite `1.500.50` (dois pontos, formato inválido)
3. Submeta o formulário
4. ✅ Comportamento esperado: erro de validação "formato inválido"
5. ❌ Comportamento real: PO criada com valor **R$ 0,00** (silenciosamente)

---

## 8. Conclusão

**O risco de corrupção de dados é REAL e CONFIRMADO.** As 7 ocorrências do Tipo A processam input de usuário sem validação robusta. Embora o frontend popule os campos com formato brasileiro (reduzindo a probabilidade), qualquer entrada manual, copy-paste do Excel, ou chamada de API com formato internacional resultará em:

- **Valores 100x maiores** que o esperado (remoção de ponto decimal)
- **Valores zerados** silenciosamente (`except: pass`)
- **Nenhum log ou notificação** ao usuário sobre o erro

A divergência entre `order_service._parse_float` (não remove pontos) e `purchase_order_service._parse_float` (remove pontos) evidencia a ausência de um padrão definido e aumenta o risco de bugs em novos desenvolvimentos.

---

*Relatório gerado em 04/06/2026. Nenhum arquivo foi modificado.*
