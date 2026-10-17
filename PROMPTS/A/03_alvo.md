# Nível Alvo: duas linhas, divergências, notas e lançamentos

Pessoa A · 2 sessões · 14:37–15:59 · `PLANO.md` §6.5 e `CONTRATO_TECNICO_ALVO.md`.

B implementou o seu lado do Alvo em outra máquina (commits `ea48b0f` e `559c6af`; ver `../B/`).

---

## Sessão `300d01e3` · 14:37–15:08 · Sonnet 5.5 · verificação do Mínimo e spec do Alvo

| # | Horário | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|---|
| 1 | 14:37 | "Elabore os specs para o desenvolvimento da etapa Nível ALVO para A e B nos moldes de @CONTRATO_TECNICO_MINIMO.md" | Começou a ler o plano. | **Interrompemos** para checar o Mínimo antes (gate M). |
| 2 | 14:39 | "Verifique o estado atual do projeto com base no escopo do Nível MÍNIMO. Verifique que as integrações das entregas de A e B estão funcionando corretamente e retorne o output dessa etapa" | Confirmou a integração A + B pela CLI de B. Apontou o que faltava formalmente: tag `minimo`, `saida/` não commitada e registro da revisão cruzada (M7). | Gate M considerado verde. |
| 3 | 14:42 | "Gere apenas os arquivos de saída por enquanto e verifique se os números estão corretos. também explique como eu rodo manualmente os scripts para gerar o output" | Gerou os 6 CSVs e conferiu com um recálculo independente: os 18 lojistas batem ao centavo, R$ 180.006,23. | — |
| 4 | 14:57 | "volte para a criação do spec para a fase alvo A e B" | Escreveu `CONTRATO_TECNICO_ALVO.md`: divisão A/B, tipos novos em `contratos.py`, números de referência para os testes. Única dependência entre os lados: `notas.py`. | Spec usado por A e B em paralelo. |
| 5 | 15:05 | "registre as novas hipóteses" | 18 hipóteses (H1–H18) em `HIPOTESES.md` §5, com etiqueta e parâmetro. Destaque: **H1, arredondamento da remessa por operação** (R$ 39.543,45 e não 39.542,88). | Decididas pelo time antes de implementar. |
| 6 | 15:07 | "tire os arquivos de saída do commit e dê push do resto" | Refez o commit local sem os CSVs (`--amend`, ainda não enviado) e deu push (`e8359f4`). | — |

## Sessão `b0dd5359` · 15:11–15:59 · Opus 5.5 / Sonnet 5.5 · implementação do Alvo (lado A)

| # | Horário | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|---|
| 1 | 15:11 | "Com base em @PLANO.md implemente o Nível Alvo A conforme os specs definidos em @CONTRATO_TECNICO_ALVO.md" | Checkout completo (estorno pela taxa da venda original, antecipação, reversão), divergências de checkout e `notas.py`. Todos os números de referência do contrato bateram ao centavo; 166 testes; duas execuções geram arquivos idênticos. Errou um `Counter(dict)` num script de conferência e disse isso ("bug meu"). | Aceito. Números do Alvo: checkout R$ 191.464,34 (18 lojistas), 92 divergências de checkout (R$ 1.576,23). |
| 2 | 15:30 | [erro colado: `ModuleNotFoundError: No module named 'yaml'` ao rodar `python -m src.main`] | O README não dizia para criar e ativar o venv. Corrigiu o README. | Ajuda a cumprir "instalar e rodar do zero". |
| 3 | 15:32 | "tire os arquivos de saída do commit e adicione-os ao git ignore" | `saida/*.csv` no `.gitignore`. Avisou que o plano previa `saida/` commitada nas tags, como entrega de reserva. | Decisão revista no fim: o enunciado exige `saida/` no repositório. |
| 4 | 15:33 | "tire novamente os arquivos de saída e dê push do resto" | Push até `5e7d151`. Avisou que o commit `0bffad5` ainda contém os CSVs e que só reescreveria o histórico se pedido. | — |
| 5 | 15:43 | "quais são as tasks do nível extra em @PLANO.md ?" | Resumo de E1–E5 com os critérios de aceite. | — |
| 6 | 15:48 | "explique quais arquivos serão alterados / criados durante a etapa extra e qual será o output final" | Previsão de arquivos por item, sem alterar nada. | — |
| 7 | 15:54 | "explique de acordo com o plano: Quais são as interfaces e features do app streamlit? Qual a função do LLM nesse projeto?" | Explicou as 4 telas e o fallback de LLM para lançamentos sem regra. | Concluímos que o LLM não agregava: todos os 184 lançamentos já fecham por regra. |
| 8 | 15:58 | "Elimine a implantação do LLM do Plano e de outros arquivos de planejamento em que esteja sendo mencionada" | Removeu o LLM do `PLANO.md` e dos demais documentos de planejamento; 176 testes verdes. | **Decisão nossa:** a solução roda sem chave de API e a IA fica na construção, não na execução. |
