# Nível Mínimo: comissão de checkout por lojista, com rastro (lado A)

Pessoa A · sessão `93ea5563` · 13:46–14:18 · Sonnet 5.5 · `PLANO.md` §6.4 e `CONTRATO_TECNICO_MINIMO.md`.

O contrato técnico do Mínimo foi escrito por B (commit `51ece5f`) antes desta sessão; A implementou contra ele. Commit `66e0275`.

Resultado: `ingest/orbe.py`, `ingest/taxas.py`, cadastro mestre por EC exato, `regras/checkout.py` (só `VENDA`) e `core/contratos.py`. 87 testes. 18 lojistas, **R$ 180.006,23**, 1.574 vendas calculadas e 267 em pendência (Kiwi, Horizonte Viagens, Horizonte Intercâmbio e Atlas).

## Prompts

| # | Horário | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|---|
| 1 | 13:46 | "Implemente as tasks do membro A do nível mínimo de @PLANO.md seguindo os specs definidos em @CONTRATO_TECNICO_MINIMO.md" | Leitor da Orbe (lê `01_` e `06_`, cabeçalho achado pelo conteúdo, id repetido = erro), leitor da planilha (só a aba vigente, `'2,59%'` e fração, CNPJ de 13 dígitos, vigência dupla da Bridge), cadastro mestre só por EC exato e cálculo por transação. Integrou com o `Saida` de B e confirmou que o rastro fecha ao centavo. | Aceito. A integração completa esperou o `main.py` de B. |
| 2 | 14:03 | "explique qual é o output do nível mínimo A implementado e um resumo dos arquivos gerados nessa etapa com suas respectivas funções" | Explicou o `ResultadoCheckout` em memória (comissões, pendências, resumo de conservação). | — |
| 3 | 14:07 | "como posso verificar se ResultadoCheckout e os valores das comissões são corretos?" | **Recálculo independente** só com `csv`, `openpyxl` e `Decimal`, sem importar `src/`: 1.574 vendas, 267 bloqueadas, 18 lojistas, R$ 180.006,23, tudo batendo. | Primeira conferência independente do dia; o padrão se repetiu nos níveis seguintes. |
| 4 | 14:11 | "verifique se a estrutura atual do repo (mínimo A) está pronto para push" | 87 testes; nenhum EC, CNPJ ou nome de lojista em `src/` (regra 6 do plano); arquivos não rastreados listados. | Commit e push. |
| 5 | 14:14 | "como posso verificar manualmente se os resultados de ResultadoCheckout fazem sentido?" | Script que despeja comissões, vendas comissionadas e pendências em CSV para abrir no Excel, com um roteiro de conferência (conservação 1.574 + 267 = 1.841, Bridge antes e depois de 15/09…). | Revisão manual de linhas contra a origem (critério M7). |
| 6 | 14:17 | "explique como eu acesso essas planilhas" | Caminho dos CSVs e cuidados com `;` e decimal no Excel. | — |

## Regras dadas à IA

- Lojista casado **só por EC exato** da planilha. Zero fuzzy match de nome; o que não casa vira pendência com `quem_decide`.
- Atlas não é faturada até o Comercial confirmar a taxa (resposta da Helena).
- Estornos, antecipações e reversões ficam fora do Mínimo e são contados no log, sem virar pendência (seriam alarme falso).
