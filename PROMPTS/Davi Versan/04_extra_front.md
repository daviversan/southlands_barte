# Nível Extra e front

Pessoa A · 2 sessões · 16:01–17:13 · `PLANO.md` §6.6. Commits `09e72fa` (Extra) e `23d27b5` (front).

Resultado: conferência automática que falha o comando se algo não fechar (31 checagens), pendências com motivo em linguagem de negócio e coluna `sugestao`, solução parametrizada para outubro, front Streamlit sem regra de negócio. 201 testes. **Nenhum número do Alvo mudou.**

---

## Sessão `4d13c32d` · 16:01–17:02 · Opus 5.5 / Sonnet 5.5

| # | Horário | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|---|
| 1 | 16:01 | "Implemente o nível Extra descrito em @PLANO.md, conforme os requisitos e estado atual do projeto" | E1: `core/conferencia.py` relê os CSVs gravados e cruza com as entradas. E2: motivos reescritos para o financeiro, `quem_decide` de lista fechada, coluna `sugestao`. E3: nada fixo no código, teste com data pack alterado. E5: `app.py`. Comparou `saida/` antes × depois: comissões, divergências, notas, lançamentos e rastro **idênticos byte a byte**. Mudou a repetida da Ponte para `quem_decide = Ponte`. Repetiu o erro do `Counter(dict)` num script e corrigiu. | Aceito. |
| 2 | 16:24 | "Verifique a validade desses números e o que cada um significa" (cartões do front) | Recontou a partir dos arquivos brutos. **A primeira leitura do Aurora usou as colunas erradas**; a IA percebeu, refez e confirmou os 5 totais. Apontou que só 3 fazem sentido como total único. | Pedimos para tirar do front o que não faz sentido. |
| 3 | 16:31 | "explique por que lançamentos está negativo" | É a variação de caixa das duas contas (−R$ 1,4 mi): os repasses aos lojistas saem antes das TEDs da Orbe. Reflete os dados, não é erro. | Entrou como ponto do pitch (saldo negativo do Aurora). |
| 4 | 16:38 | "remova as informações sem sentido e faça os cartões mostrarem os números inteiros. remova o campo pasta de entrada para pegar automaticamente do repo e o campo pasta de saída, que deve ser mostrada diretamente no front" (enviado duas vezes; a primeira foi interrompida) | Cartões com o valor completo e detalhe checkout/remessa; só o campo de competência na barra lateral. 201 testes. Avisou que não viu a tela renderizada. | Conferimos no navegador. |
| 5 | 16:46 | "o que significa Divergências de taxa e pendências" | Definições com exemplo (Rota Global: contrato 3,59%, aplicado 4,09%). | Linguagem reaproveitada no pitch. |
| 6 | 16:51 | "como os motivos das pendências estão sendo escritos?" | Modelos de frase por código, um por módulo. Nada gerado por IA em execução; a mesma situação dá sempre o mesmo texto. | — |
| 7 | 16:53 | "mostre os padrões de texto predefinidos para a geração dos motivos" | Listou os modelos de cada módulo. | Revisão de linguagem dos motivos. |
| 8 | 16:57 | "18 notas de checkout 1 nota de remessa confira esses valores e o que significam" | Recálculo independente das 18 notas: todas batem ao centavo, R$ 191.464,34. **Errou a coluna de vigência da planilha na primeira tentativa** e refez. Nota de remessa: R$ 39.543,45 para a Ponte (CNPJ do e-mail). | Conferência das notas registrada. |
| 9 | 17:02 | "explique o que cada card significa" | Explicação de cada cartão em linguagem do financeiro, inclusive que a comissão real será maior quando as 4 pendências de cadastro forem resolvidas. | Texto base do pitch. |

## Sessão `5f03a1f6` · 17:08–17:13 · Opus 5.5 · plano de evolução

| Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|
| "com base na estrutura atual do projeto, elabore um plano de como implementar LLM para gerar motivos de pendências que não são mapeados e uma análise de histórico comparado a outros meses" | Leu o código, fez uma pergunta de esclarecimento e escreveu um plano em modo de planejamento, sem alterar código. | Fora do escopo do dia. Vira resposta para "o que faria com mais um mês" no pitch. |
