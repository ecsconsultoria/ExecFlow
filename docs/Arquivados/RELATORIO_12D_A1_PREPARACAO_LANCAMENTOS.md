# RELATÓRIO ETAPA 12D-A1 — PREPARAÇÃO PARA LANÇAMENTOS FINANCEIROS REAIS

**Data**: 29/08/2026 — **Modo**: SOMENTE ANÁLISE (leitura de código e de produção). **Nenhuma categoria, centro de custo, despesa, pró-labore, baixa, pagamento ou commit foi criado/executado. Nenhum INSERT/UPDATE/DELETE. Nenhuma alteração de código.**

---

## Resumo executivo

O sistema está preparado para receber despesas reais. O fluxo correto para pró-labore e despesas administrativas é: **Despesa Geral** (`type='expense'` do FinancialRecord) com **categoria tipo `expense`** (raiz "Pessoal" para pró-labore; raiz "Despesas Administrativas" para os demais) e **centro de custo obrigatório**. A despesa entra na **DRE por competência (emissão)** imediatamente, no **AP e Caixa Previsto por vencimento (due_date)** enquanto pendente, e no **Caixa Realizado por pagamento (paid_date)** após a baixa — sem duplicidade (status único + índice UNIQUE por referência). **Não existe recorrência** — lançamentos repetidos serão manuais.

---

## 1. Estado atual

- Código `a9950b0` ativo em produção (validado na 12C-A8, classificação B).
- `financial_categories` e `cost_centers` **vazias** em produção (telas com estado vazio "Criar a primeira...").
- `financial_records` tipo `expense`: **0 registros** (Despesas R$ 0,00 no Dashboard/AP/DRE).
- Saldo Inicial do Caixa: **não configurado** (R$ 0,00, com aviso de que nunca é calculado automaticamente).

## 2. Categorias (modelo `FinancialCategory` — `financial_categories`)

| Campo | Tipo | Obrigatório | Observações |
|---|---|---|---|
| `name` | string(100) | ✅ | Nome da categoria |
| `type` | enum | ✅ | **`revenue`** (Receita) · **`direct_cost`** (Custo Direto) · **`expense`** (Despesa) — `direct_cost` ≠ `expense` |
| `parent_id` | FK própria | ❌ | Hierarquia opcional; **pai deve ter o MESMO tipo** |
| `description` | string(255) | ❌ | |
| `active` | bool | — | Toggle ativar/desativar (desativada some dos formulários) |
| `company_id` | FK | ✅ | Isolamento multiempresa em todas as consultas |

**Influência na DRE**: a DRE agrupa despesas pela **categoria-RAIZ** (`_expense_group` em `dre_service.py`): o nome da raiz vira o título da linha. Grupos fixos da DRE: `Despesas Operacionais`, `Despesas Administrativas`, `Pessoal`, `Impostos`, `Despesas Financeiras` + `Despesas Não Classificadas` (sem categoria ou sem raiz). **Uma raiz com nome fora dessa lista aparece como linha própria na DRE.**

**Influência no lançamento de despesa**: o formulário de despesa só oferece categorias `type='expense'` e ativas. A validação rejeita categoria de outro tipo ou de outra empresa.

## 3. Centros de Custo (modelo `CostCenter` — `cost_centers`)

| Campo | Tipo | Obrigatório | Observações |
|---|---|---|---|
| `name` | string(100) | ✅ | |
| `description` | string(255) | ❌ | |
| `active` | bool | — | Toggle |
| `company_id` | FK | ✅ | Multiempresa |

- **Obrigatório na despesa** (validação: "Centro de custo é obrigatório"; deve ser da mesma empresa).
- **Na DRE**: não altera a agregação (a DRE agrupa por categoria-raiz); aparece no detalhamento do Caixa (`movement_info.cost_center`).
- **No Caixa**: exibido por movimento ("Categoria/Centro de Custo").
- Não existe lista fixa — os centros são criados livremente pela empresa (ex.: Administrativo, Operação, Frota).

## 4. Despesas (`FinancialRecord` tipo `expense` — rota `/financial/expenses`)

Campos do formulário (`expense_form.html`):

| Campo | Obrigatório | Validação |
|---|---|---|
| Descrição | ✅ | texto não vazio |
| Valor (R$) | ✅ | `parse_brl`; > 0 |
| Emissão | ✅ | data ISO válida (= competência da DRE) |
| Vencimento | ✅ | data ISO válida (= AP / previsto) |
| Categoria | ✅ | `type='expense'`, mesma empresa |
| Centro de Custo | ✅ | mesma empresa |
| Fornecedor | ❌ | mesma empresa, não excluído |
| SO | ❌ | mesma empresa, não excluído/cancelado |
| PO | ❌ | idem |
| Observação | ❌ | texto livre |

Na criação: `type='expense'`, `category='outro'` (legado), `status='pendente'`, `reference='expense:{id}'` (única), auditoria via `log_activity`. **Despesa paga não pode ser editada nem cancelada** (histórico preservado); pendente pode ser **cancelada** (`status='cancelado'`, nunca soft-delete). Pagamento = **Baixa** (`/record/<id>/baixa`): define `paid_date`, `payment_method` (PIX, TRANSFERÊNCIA, BOLETO, DINHEIRO, CARTÃO, CHEQUE) e `status='pago'` em transação atômica. A Baixa está disponível tanto no Lançamentos quanto na própria tela de Despesas (botão ✓ Pagar).

## 5. Fluxo DRE (confirmado em `dre_service.py` — Etapa 5)

```
DESPESA CRIADA (emission_date = competência)
        ↓
DRE (status != cancelado, emission_date no período, agrupada pela categoria-RAIZ)
```

- Despesa **pendente** JÁ entra na DRE (DRE ≠ Caixa — docstring do service).
- Receita = SO faturado (`invoiced_at`); Custos Diretos = POs válidas **vinculadas a SO** (competência: service_date → delivery_date → created_at).
- Margem Bruta = Receita − Custos Diretos. Resultado Operacional = Margem Bruta − Despesas Gerais.
- **Pró-labore e despesas administrativas NUNCA entram em Custos Diretos** — vão para a seção "Despesas Gerais" (grupo por categoria-raiz). Despesa sem `emission_date` nunca entra na DRE (vira pendência "competência indeterminada").

## 6. Fluxo AP (confirmado em `ar_ap_service.py` — Etapa 8B)

```
DESPESA NÃO PAGA (status='pendente', due_date no período)
        ↓
AP — origem "DESPESA" (valor, vencimento, descrição, fornecedor; vencido se due_date < hoje)
```

- AP = Custos de Serviços (POPayment não paga) **+** Despesas Gerais pendentes. Canceladas fora; pagas fora do saldo.
- Ao pagar (status='pago'), a despesa **sai do AP** e passa a contar em "Pagos no Período" (`paid_in_period` por `paid_date`).

## 7. Fluxo Caixa (confirmado em `cash_flow_service.py` — Etapas 4 e 9B)

```
ANTES DO PAGAMENTO:  PREVISTO  (saída prevista por due_date, via ar_ap_service)
DEPOIS DO PAGAMENTO: REALIZADO (saída por paid_date, FR status='pago')
```

- **Nunca simultâneo**: o `status` é único (`pendente` → previsto; `pago` → realizado; `cancelado` → fora de ambos). Não existe segunda tabela de movimentos — o FR é o espelho 1:1.
- Saldo Inicial: configurado manualmente em `/financial/cash-flow/settings` (JSON em `companies.settings`), **nunca inferido**.

## 8. Tratamento do pró-labore

**Forma correta no sistema atual: DESPESA GERAL** (`FinancialRecord type='expense'`).

- **Categoria**: raiz **"Pessoal"** (tipo `expense`) com filha **"Pró-Labore"** — assim a DRE o exibe na linha fixa "Pessoal". (Criar a raiz com nome diferente faria o pró-labore virar uma linha própria da DRE — funciona, mas foge do desenho.)
- **Centro de custo**: "Administrativo" (recomendado; ou "Pessoal", conforme preferência).
- **Emissão**: último dia do mês de competência (ex.: 31/08/2026) — define em qual mês aparece na DRE.
- **Vencimento**: data prevista de pagamento (ex.: 05/09/2026) — define AP e Caixa Previsto.
- **Comportamento**: pendente → DRE (competência) + AP + Caixa Previsto; pago → Caixa Realizado na data do pagamento; permanece na DRE do mês da emissão. **Não afeta Custos Diretos nem margem bruta.**
- **Recomendação fiscal/contábil**: confirmar com o contador se o pró-labore deve ter fornecedor (sócio como pessoa física) ou ficar sem vínculo — o sistema aceita ambos.

## 9. Tratamento das despesas administrativas

**Todas como DESPESA GERAL** (nunca `direct_cost` — custo direto é exclusivo de PO vinculada a SO na DRE):

| Despesa | Categoria (raiz → filha) | Tipo |
|---|---|---|
| Aluguel | Despesas Administrativas → Aluguel | expense |
| Energia | Despesas Administrativas → Energia | expense |
| Internet | Despesas Administrativas → Internet | expense |
| Contabilidade | Despesas Administrativas → Contabilidade | expense |
| Telefone | Despesas Administrativas → Telefone | expense |
| Material de escritório | Despesas Administrativas → Material de Escritório | expense |
| Software | Despesas Administrativas → Software | expense |
| Serviços administrativos | Despesas Administrativas → Serviços Administrativos | expense |

Centro de custo: **"Administrativo"** para todas (criar uma vez).

## 10. Campos obrigatórios (despesa)

**Descrição, Valor (> 0), Categoria (expense, mesma empresa), Centro de Custo (mesma empresa), Emissão, Vencimento.** Opcionais: Fornecedor, SO, PO, Observação. No pagamento (baixa): data do pagamento (default hoje) e método de pagamento; valor pago opcional (recomendado pagar o valor exato — ver riscos).

## 11. Modelo do primeiro lançamento (pró-labore) — NÃO CRIADO

Pré-requisitos (próxima etapa, quando autorizado):
1. Criar categoria raiz **"Pessoal"** (tipo Despesa) e filha **"Pró-Labore"**.
2. Criar centro de custo **"Administrativo"**.

Preenchimento do formulário (conceitual — nada foi lançado):

| Campo | Exemplo |
|---|---|
| Descrição | `Pró-labore — competência 08/2026` |
| Categoria | Pessoal → Pró-Labore |
| Centro de Custo | Administrativo |
| Valor | `3.000,00` (valor a definir com o contador) |
| Emissão | `31/08/2026` |
| Vencimento | `05/09/2026` |
| Fornecedor | (vazio — ou sócio se cadastrado como fornecedor) |
| Observação | `Pró-labore sócio — mês 08/2026` |

Ao salvar: despesa pendente → aparece em Despesas, AP, Caixa Previsto e DRE (linha Pessoal). No dia do pagamento: botão Pagar ✓ com data real e método (ex.: PIX) → migra para Caixa Realizado.

## 12. Recorrência

**Não existe** (nenhum recurso de recorrência/repetição no código). Documentado — não criar. Lançamentos mensais (pró-labore, aluguel etc.) serão manuais; usar descrição padronizada com mês (ex.: `Pró-labore — competência MM/AAAA`) para facilitar conferências.

## 13. Riscos

| Risco | Detalhe | Mitigação |
|---|---|---|
| Classificação errada | Criar categoria tipo `direct_cost` para despesa administrativa — a DRE trataria como custo direto só via PO; no formulário de despesa é **impossível** (só oferece `expense`) — risco baixo | Usar sempre Despesas → categorias `expense` |
| DRE errada por categoria-raiz | Raiz com nome fora da lista fixa vira linha própria; sem categoria → "Despesas Não Classificadas" | Criar raízes com os nomes dos grupos da DRE (Pessoal, Despesas Administrativas...) |
| DRE × mês errado | Emissão errada desloca a competência | Revisar emissão antes de salvar (despesa paga não é editável) |
| AP/Caixa × data errada | Vencimento errado desloca previsto/vencido | Revisar vencimento antes de salvar |
| Duplicidade manual | Não há detecção de conteúdo duplicado (só de `reference` — índice UNIQUE); digitar a mesma despesa duas vezes cria dois registros | Conferir a lista de Despesas antes de criar |
| Baixa com valor diferente | Na baixa é possível alterar o valor (`paid_amount`) — para despesas isso reescreve o `amount` e distorce a DRE | **Pagar sempre o valor exato** (deixar valor pago em branco) |
| Despesa paga travada | Paga não edita/não cancela (sem estorno no fluxo atual) | Conferir tudo antes da baixa |
| Float para moeda | `Float` em vez de `Numeric` (débito técnico conhecido — arredondamentos) | Valores com 2 casas; conferir somas |
| Sem recorrência | Esquecer lançamento mensal | Checklist mensal fixo |
| Saldo inicial não configurado | Caixa mostra realizado sem o ponto de partida | Configurar em Caixa → Saldo Inicial (com data de referência) quando autorizado |

## 14. Recomendações

1. **Criar o catálogo mínimo primeiro** (próxima etapa, autorizada): raízes "Pessoal" e "Despesas Administrativas" (tipo Despesa) + filhos da seção 9; centro de custo "Administrativo".
2. **Configurar o Saldo Inicial do Caixa** (valor + data de referência) antes de interpretar o realizado do mês.
3. Padronizar descrições com competência (`... — MM/AAAA`).
4. Pagar sempre o valor exato da despesa (não usar baixa com valor diferente em despesas).
5. Conferir mensalmente: Despesas pendentes do mês anterior (vencidas) antes de fechar o caixa.
6. Confirmar com o contador: valor do pró-labore, competência e necessidade de fornecedor (sócio).

## 15. Próximo passo

Aguardar autorização para a **etapa de criação do catálogo** (categorias + centro de custo) e, em seguida, a dos **primeiros lançamentos reais** (pró-labore e despesas administrativas). Nada foi criado nesta etapa.

---

**Nenhuma escrita realizada. Nenhum dado alterado. Nenhum commit. PARADO — aguardando próxima instrução.**
