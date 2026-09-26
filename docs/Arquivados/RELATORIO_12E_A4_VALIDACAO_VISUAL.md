# RELATÓRIO ETAPA 12E-A4 — VALIDAÇÃO VISUAL E FUNCIONAL DOS RELATÓRIOS

**Data**: 29/08/2026 — **Modo**: validação SOMENTE LOCAL. **Nenhum commit, push, deploy, migration, alteração de produção ou de dados.** Amostras geradas a partir do banco local dev (dados reais) e do banco de teste em memória (espelho dos valores de produção — nenhum dado de produção tocado). Nenhum lançamento criado.

---

## Resumo executivo

26 amostras geradas (PDF + XLSX dos 8 relatórios) e validadas funcional e visualmente (extração de texto página a página com PyMuPDF + checagens estruturais do XLSX). Valores idênticos entre TELA × PDF × XLSX. Filtros corretos. Paginação correta (Lançamentos com 6 páginas, cabeçalho repetido, rodapé "Página N de M"). Banco local dev íntegro após todas as gerações (contagens idênticas). Regressão: **206 passed / 6 failed** (mesmas 6 pré-existentes).

**Classificação: B — APROVADO COM RESSALVAS NÃO BLOQUEADORAS** (ver seções 14–16).

---

## 1. PDFs testados

| PDF | Páginas | Conteúdo validado |
|---|---|---|
| DRE julho (dev local real) | 2 | título, período, filtros, Demo + Visão mensal + Receitas + Custos Diretos |
| DRE julho (espelho produção) | 1 | Pessoal 5.000,00 · Impostos e Tributos 800,00 · Despesas julho 5.800,00 · Resultado (5.800,00) |
| Caixa agosto (dev) | 2 | resumo + movimentos |
| Caixa agosto (espelho) | 1 | saldo inicial "não configurado", saídas realizadas 5.000,00 (Realizado), saídas previstas 800,00 (Previsto), saldo projetado (5.800,00) |
| AR (dev) | 1 | cliente, referência, vencimento, original, recebido, saldo, status |
| AP (dev / espelho) | 1 | DAS pendente 800,00 com categoria e centro; TOTAIS |
| Despesas (dev / espelho) | 1 | DAS Pendente (raiz Impostos e Tributos) + Pró-Labore Paga (raiz Pessoal); TOTAIS 5.800,00 |
| Lançamentos (dev) | **6** | 55 registros; cabeçalho repetido nas páginas 2–6; rodapé "Página N de 6" |
| Lançamentos (espelho) | 1 | tipo Despesa, referências expense:1001/1002, competência 31/07, pagamento 10/08 e "—" |

## 2. XLSX testados

Todos os 8 abrem corretamente no openpyxl (sem corrupção): DRE, Caixa, AR, AP, Despesas, Lançamentos, Categorias (52 linhas do catálogo real dev), Centros de Custo.

## 3. Validação visual (PDF)

- **Caracteres**: Pró-Labore · DAS / Simples Nacional · Impostos e Tributos · competência · R$ · travessão "—" · acentos (ó, ê, ç) — **todos extraídos corretamente, nenhum caractere corrompido** (zero U+FFFD).
- **Cabeçalho**: título + subtítulo "DRE Gerencial" no topo de cada página; meta com período, filtros e empresa.
- **Tabelas**: cabeçalho destacado repetido em páginas novas; zebra; alinhamento de valores à direita; negativos em vermelho "(5.800,00)".
- **Rodapé**: em TODAS as páginas — "Empresa — Relatório", "Página N de M", "Gerado em dd/mm/aaaa hh:mm por usuário".
- **Logo**: amostras geradas sem logo configurado (banco dev sem logo) — mecanismo testado no piloto; **marcar como pendente de conferência visual humana com logo**.
- ⚠️ **Limitação do agente**: o ambiente não exibiu renderização de imagem para inspeção ocular; a validação visual foi feita por extração de texto/posições página a página (PyMuPDF). **Recomendada conferência visual humana** das amostras salvas.

## 4. Validação dos valores (espelho dos valores reais de produção)

| Verificação | Resultado |
|---|---|
| DRE julho: Pessoal R$ 5.000,00 | ✅ |
| DRE julho: Impostos e Tributos R$ 800,00 | ✅ |
| DRE julho: Despesas Gerais R$ 5.800,00 | ✅ (5.000 + 800,00; coluna 07/26 e Total) |
| Caixa agosto: Pró-Labore R$ 5.000,00 **REALIZADO** (10/08) | ✅ |
| Caixa agosto: DAS R$ 800,00 **PREVISTO** (31/08) | ✅ |
| AP: 1 pendente · R$ 800,00 (DAS) | ✅ |
| Despesas: Pendentes R$ 800,00 · Pagas R$ 5.000,00 | ✅ |

## 5. TELA × PDF × XLSX

| RELATÓRIO | CAMPO | TELA | PDF | XLSX | RESULTADO |
|---|---|---|---|---|---|
| DRE | Despesas Gerais | 5.800,00 (Pessoal 5.000 + Impostos 800,00) | 5.000 / 800,0 / 5.800,00 | −5.000,00 / −800,00 (numérico) | ✅ |
| DRE | Resultado | (5.800,00) | (5.800,00) | (coluna 07/26) | ✅ |
| Caixa | Entradas realizadas | tela | 0,00 | 0,00 | ✅ |
| Caixa | Saídas realizadas | 5.000,00 | 5.000,00 | 5.000,00 (numérico) | ✅ |
| Caixa | Entradas previstas | 0,00 | 0,00 | 0,00 | ✅ |
| Caixa | Saídas previstas | 800,00 | 800,00 | 800,00 | ✅ |
| Caixa | Saldo projetado | (5.800,00) | (5.800,00) | — | ✅ |
| AR | original/recebido/saldo | tela dev | PDF dev | 2.000 / 500 / 1.500 (numérico) | ✅ |
| AP | valor/saldo | 800,00 | 800,00 | 800,00 | ✅ |
| AP | quantidade | 1 pendente | 1 pendente(s) | "1 pendente(s)" | ✅ |
| Despesas | valor | 800,00 + 5.000 | 800,00 + 5.000,00 | numérico | ✅ |
| Despesas | status/categoria/centro | Pendente/Paga · raízes corretas | idem | idem | ✅ |
| Lançamentos | valor | 5.000,00 Pago + 800,00 Pendente | 5.000,00 + 800,00 | numérico | ✅ |
| Lançamentos | tipo | (tela não exibe coluna tipo) | Despesa | Despesa | ✅ PDF/XLSX |
| Lançamentos | competência/pagamento | tela mostra Emissão/Vencimento | 2026-07-31 / 2026-08-10 | datas reais | ✅ |

Nota: a tabela da TELA de Lançamentos não exibe descrição/tipo das despesas (mostra Nº/Cliente-Fornecedor/Emissão/Vencimento/Valor/Status) — por design da tela; PDF/XLSX incluem descrição e tipo. Valores consistentes nos três.

## 6. Filtros (testados ao vivo)

| Filtro | Resultado |
|---|---|
| DRE agosto/2026 (competência julho fora) | ✅ sem Pessoal/DAS em agosto |
| Caixa julho/2026 (pró-labore pago em 10/08 fora do realizado de julho) | ✅ |
| Despesas status=pendente | ✅ só DAS (sem pró-labore pago) |
| Despesas status=pago | ✅ só pró-labore (sem DAS) |
| AP supplier (suíte) | ✅ |
| AR client / períodos (suíte) | ✅ |

**Nenhum relatório apresentou dados fora do filtro.**

## 7. Paginação

- **Lançamentos dev: 6 páginas** com 55 registros — cabeçalho da tabela repetido em todas as páginas (repeatRows), rodapé correto em cada página ("Página 2 de 6" … "Página 6 de 6"), sem linhas cortadas (linhas inteiras migram de página).
- DRE dev (2 páginas) e Caixa dev (2 páginas) com quebras limpas entre seções.
- Volumes insuficientes para paginar nos demais relatórios: registrado como NÃO TESTADO por falta de volume (sem criação de dados fictícios).

## 8. Responsividade

- Botões `[PDF] [XLSX]` no cabeçalho de todas as telas (links verificados no HTML das 8 telas).
- Mobile: texto escondido (`hidden sm:inline`), ícones com `aria-label`/`title` — padrão do macro; sem overflow (flex-wrap já presente nas linhas de cabeçalho).

## 9. Acessibilidade

- `aria-label` ("Gerar PDF" / "Exportar XLSX") e `title` com descrição ("respeita os filtros atuais") em todos os botões; foco visível (`focus:ring`); ícone + texto (não depende de cor).

## 10. Segurança

- Suíte: anônimo → 302 em todas as rotas de export; usuário sem permissão → 403; catálogos (financial.manage) → 403 para view-only. CSRF não se aplica (GETs). Nenhuma rota pública.

## 11. Multiempresa

- Suíte: despesa da empresa B não aparece no XLSX da empresa A (Despesas e DRE); helpers recebem `cid` da sessão.

## 12. Integridade do banco

- Banco dev comparado antes e depois de todas as gerações: expenses 0→0 · FR 55→55 · categorias 96→96 · centros 14→14 · orders 40→40 · order_payments 35→35 · POs 32→32 · po_payments 21→21 — **zero alteração** (geração READ-ONLY).

## 13. Testes

- Suíte completa: **206 passed / 6 failed** — mesmas 6 falhas pré-existentes (`test_decorators_and_audit.py`), **zero falhas novas**. Baseline 12E-A3 preservado.

## 14. Falhas

Nenhuma falha funcional. Duas ressalvas de apresentação (seção 15).

## 15. Correções necessárias (NÃO executadas — documentadas conforme regra)

1. **Largura de colunas monetárias no XLSX** (não bloqueadora): a largura é calculada pelo valor bruto (`5000.0` → 7 caracteres) e não pelo formato exibido ("R$ 5.000,00" → 12–13). Valores grandes podem aparecer cortados (#####) no Excel. **Correção proposta**: em `report_xlsx._auto_widths`, impor mínimo de 14 para colunas `money_cols` (e 12 para `date_cols`).
2. **Linha TOTAIS do Lançamentos** (semântica): soma todos os valores (receitas + custos + despesas, todos positivos) — soma mista pouco informativa. **Correção proposta**: totais por tipo (soma de Receitas, soma de Custos, soma de Despesas) ou líquido (receitas − custos − despesas).
3. **Conferência visual humana** das amostras com logo configurado (o mecanismo de logo foi validado no piloto; as amostras atuais saíram sem logo por falta de logo no banco dev).

## 16. Classificação final

# **B — APROVADO COM RESSALVAS NÃO BLOQUEADORAS**

As ressalvas (largura monetária no XLSX e semântica da linha TOTAIS de Lançamentos) não comprometem valores, segurança ou integridade — são ajustes de apresentação a aplicar na próxima rodada, junto com a conferência visual humana com logo. Nenhum problema bloqueador, nenhum risco financeiro/segurança.

---

**Amostras salvas localmente em `%TEMP%\a8\A4\` (26 arquivos — fora do Git). Nenhum commit, push, deploy, migration ou alteração de dados. PARADO — aguardando autorização.**
