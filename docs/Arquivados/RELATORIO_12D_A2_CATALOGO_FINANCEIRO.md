# RELATÓRIO ETAPA 12D-A2 — CATALOGAÇÃO FINANCEIRA MÍNIMA

**Data**: 29/08/2026 — **Modo**: SOMENTE INSPEÇÃO/LEITURA. Inspeção do catálogo em produção via GET autenticado (sessão admin, logout ao final). **Nenhuma categoria, centro de custo, despesa, lançamento ou baixa criada. Nenhum INSERT/UPDATE/DELETE. Nenhum commit.**

---

## Resumo executivo

O catálogo financeiro de produção está **completamente vazio**: 0 categorias financeiras, 0 centros de custo, 0 despesas. Portanto **nenhuma estrutura do catálogo mínimo existe ainda** — não há duplicidade, não há estrutura incorreta. A ação necessária (na próxima etapa, quando autorizada) é **criar** as estruturas listadas abaixo, todas escopadas à empresa da sessão admin (única empresa do deployment).

---

## 1. Estado atual do catálogo

| Tabela | Registros em produção | Evidência |
|---|---|---|
| `financial_categories` | **0** | Tela `/financial/categories` → "Nenhuma categoria ainda. Criar a primeira." |
| `cost_centers` | **0** | Tela `/financial/cost-centers` → "Nenhum centro de custo ainda. Criar o primeiro." |
| Despesas (`financial_records` type='expense') | **0** | `/financial/expenses` → No Período R$ 0,00 · Pendentes R$ 0,00 · Vencidas R$ 0,00 · Pagas R$ 0,00 |

## 2. Categorias existentes

Nenhuma.

## 3. Centros existentes

Nenhum.

## 4. Estruturas necessárias (para os lançamentos planejados)

Para o **primeiro pró-labore** (prioridade máxima):

- Categoria raiz **"Pessoal"** (tipo `expense`)
- Categoria filha **"Pró-Labore"** (tipo `expense`, pai = Pessoal)
- Centro de custo **"Administrativo"**

Para as **despesas administrativas** (quando os lançamentos dessas naturezas forem iniciados):

- Categoria raiz **"Despesas Administrativas"** (tipo `expense`)
- Filhas conforme a necessidade real de cada lançamento (seção 7)

## 5. Estruturas ausentes

Todas as do catálogo mínimo estão ausentes (catálogo vazio — seção 1).

## 6. Estruturas incorretas

Nenhuma (não há nada para estar incorreto).

## 7. Catálogo mínimo recomendado × situação

| Estrutura | Existe? | Empresa | Tipo | Status | Ação |
|---|---|---|---|---|---|
| Pessoal (raiz) | ❌ | — (criar na empresa da sessão) | `expense` | — | **Criar** (autorizado na próxima etapa) |
| Pessoal → Pró-Labore | ❌ | idem | `expense` | — | **Criar** |
| Despesas Administrativas (raiz) | ❌ | idem | `expense` | — | **Criar quando houver 1º lançamento desse grupo** |
| Despesas Administrativas → Aluguel | ❌ | idem | `expense` | — | Criar **somente se** houver lançamento de aluguel |
| Despesas Administrativas → Energia | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Internet | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Contabilidade | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Telefone | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Material de Escritório | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Software | ❌ | idem | `expense` | — | idem |
| Despesas Administrativas → Serviços Administrativos | ❌ | idem | `expense` | — | idem |
| Centro de custo Administrativo | ❌ | idem | — | — | **Criar** |

## 8. Estrutura para Pró-Labore

- **Categoria raiz "Pessoal"** (tipo Despesa) — necessária para a DRE exibir o pró-labore na linha fixa "Pessoal".
- **Filha "Pró-Labore"** (tipo Despesa, pai "Pessoal") — é a categoria selecionada no lançamento.
- **Centro de custo "Administrativo"** — obrigatório no formulário de despesa.
- Nada mais é necessário: o lançamento em si usa Descrição + Valor + Emissão + Vencimento (relatório 12D-A1, seção 11).

## 9. Estrutura para Despesas Administrativas

- **Categoria raiz "Despesas Administrativas"** (tipo Despesa).
- **Filhas**: criar apenas as que corresponderem aos lançamentos iniciais de fato. O sistema não exige granularidade — uma despesa pode usar diretamente a raiz (a DRE agrupa pela raiz de qualquer forma). **As 8 filhas da 12D-A1 são sugestão; sem definição do usuário sobre quais despesas serão lançadas primeiro, as filhas ficam como "aguardando definição".**
- **Centro de custo "Administrativo"** (mesmo centro do pró-labore).

## 10. Impacto na DRE

- Raiz "Pessoal" → linha **"Pessoal"** da DRE (grupo fixo de `dre_service.DRE_EXPENSE_GROUPS`).
- Raiz "Despesas Administrativas" → linha **"Despesas Administrativas"**.
- Categorias-filhas não alteram a linha: o agrupamento é sempre pela **categoria-raiz** (`_expense_group`: `cat.parent if cat.parent else cat`).
- Competência = **emission_date** do lançamento; despesa pendente já entra na DRE.
- Sem categoria (impossível — campo obrigatório) iria para "Despesas Não Classificadas".
- **A DRE não é alterada por esta catalogação** — as raízes propostas simplesmente usam grupos já existentes.

## 11. Impacto no AP

- Despesa pendente (vencimento = due_date) entra em Contas a Pagar com origem "DESPESA" — valor, vencimento, descrição e fornecedor (se houver). Após a baixa, sai do saldo pendente e conta em "Pagos no Período" por paid_date. Nenhuma mudança decorrente do catálogo.

## 12. Impacto no Caixa

- Pendente → **PREVISTO** (saída por due_date). Paga → **REALIZADO** (saída por paid_date). Nunca simultâneo (status único). Nenhuma mudança decorrente do catálogo. Observação: **Saldo Inicial continua não configurado** (R$ 0,00 com aviso) — configurar quando autorizado para o realizado do mês fazer sentido.

## 13. Multiempresa

- Código: toda criação de categoria/centro grava `company_id=current_user.company_id`; toda listagem filtra pela mesma empresa; validações de despesa rejeitam categoria/centro de outra empresa ("outra empresa").
- Produção: deployment de **empresa única** (sem switcher de empresa na UI; a sessão admin opera a própria empresa). Não há como criar estrutura global que vaze entre empresas pela interface.
- Isolamento confirmado por inspeção de código (`app/blueprints/financial/routes.py`, `app/models/financial_catalog.py`) + comportamento da UI.

## 14. RBAC

- Criar/editar/alternar **categoria** (`/financial/categories/new`, `/edit`, `/toggle`): requer **`financial.manage`** ✓
- Criar/editar **centro de custo** (`/financial/cost-centers/new`, `/edit`): requer **`financial.manage`** ✓
- Admin autenticado possui a permissão (vê os botões gerenciados na tela de Lançamentos — validado na 12C-A8).
- Nenhuma permissão alterada.

## 15. Riscos

| Risco | Detalhe | Mitigação |
|---|---|---|
| Criar raiz com nome fora da lista fixa da DRE | Vira linha própria em vez de cair em "Pessoal"/"Despesas Administrativas" | Usar exatamente os nomes propostos |
| Criar filha com tipo ≠ pai | Validação rejeita (pai deve ter o MESMO tipo) — risco baixo | Usar tipo Despesa em todas |
| Criar duplicata manual | Não há UNIQUE por nome — digitar duas vezes cria dois registros | Catálogo estava vazio (confirmado); conferir a lista antes de criar |
| Categoria desativada depois | Sai dos formulários, histórico preservado (não quebra DRE/AP de lançamentos existentes — o vínculo permanece) | Não desativar categorias em uso |
| Despesa sem categoria/centro | Impossível — campos obrigatórios na validação | — |
| Multiempresa | Sem risco prático (empresa única) | — |

## 16. Plano de criação (quando autorizado — NÃO executado nesta etapa)

1. Criar centro de custo **"Administrativo"**.
2. Criar categoria raiz **"Pessoal"** (tipo Despesa) e filha **"Pró-Labore"**.
3. Quando definidas as despesas administrativas iniciais: criar raiz **"Despesas Administrativas"** e apenas as filhas correspondentes aos primeiros lançamentos.
4. (Opcional, autorizado à parte) Configurar o Saldo Inicial do Caixa.
5. Lançar o primeiro pró-labore conforme modelo da 12D-A1.

## 17. Próximo passo

Aguardar autorização para a **etapa de criação** (itens 1–2 do plano acima no mínimo; item 3 conforme definição do usuário de quais despesas administrativas serão lançadas primeiro — **pendente de definição: quais filhas criar**). Nada foi criado nesta etapa.

---

**Nenhuma escrita realizada. Nenhum dado alterado. Nenhum commit. PARADO — aguardando próxima instrução.**
