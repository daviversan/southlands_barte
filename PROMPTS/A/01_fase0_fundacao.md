# Fase 0: fundação

Pessoa A · sessão `18e4b96b` · 12:55–13:20 · Sonnet 5.5 · `PLANO.md` §6.3 (colunas A e B).

Resultado: esqueleto do repositório, `core/normalize.py`, contrato de saída `core/saida.py`, `config/regras.yaml`, `HIPOTESES.md` e 45 testes verdes. Commits `a2fe310` e `9378773`.

## Prompts

| # | Horário | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|---|
| 1 | 12:55 | "exclua o southlands_barte.code-workspace do repo remoto" | `git rm --cached`, commit e push (`2d78ff4`); arquivo mantido localmente. | — |
| 2 | 12:57 | "Implemente a fase 0 - fundação do @PLANO.md" | Leu plano, dicionário e o contrato de saída do enunciado. Criou o esqueleto e o venv (Python 3.12; o 3.11 do plano não existe na máquina). Escreveu `normalize.py` (`Decimal`, `ROUND_HALF_UP`, percentual sempre em pontos percentuais), `saida.py` (gera `id_saida`, valida formato e **falha se Σ rastro ≠ valor**) e os testes. Rodou scripts descartáveis fora do repositório para conferir as regras contra os dados. | Aceito. Os achados foram para `HIPOTESES.md` §3. |
| 3 | 13:08 | "Salve um sumário das sessões em Prompts formatado conforme instruções. adicione o .gitignore e explique […]" | Primeiro sumário e rascunho de `MOMENTOS.md`; `.gitignore` com o workspace e `.DS_Store`. | Substituído por esta pasta. |
| 4 | 13:14 | "Um novo arquivo @context/tarvo_data_pack/06_orbe_ajustes_tardios_set2026.csv foi adicionado ao contexto. verifique seus dados e se isso deveria adaptar algo no plano" | Cruzou as 14 linhas com a Orbe e as taxas: sem id repetido, 13 negativos apontando para vendas do `01_` e nenhum estorno em dobro, 1 venda da Kiwi (sem contrato). Atualizou as contagens do plano (1.943 → **1.957** linhas) e definiu que `ingest/orbe.py` lê todos os arquivos Orbe da pasta. | Mudança de plano aplicada antes do Mínimo. Pergunta 17 criada. |
| 5 | 13:19 | "verifique se a fase 0 está pronta para eu dar push conforme estado atual do repo" | Testes, segredos e `.gitignore` conferidos; listou o que faltava (Slack, transcripts, Checkpoint 1). | — |
| 6 | 13:19 | "sim" | Dois commits; **não** deu push (o push ficou com a pessoa). | Push feito por nós. |

## Regras dadas à IA, não pedidas a ela

- Arredondamento: `ROUND_HALF_UP` por linha. Nunca o `round()` do Python (arredonda para o par) e nunca truncamento (a Orbe trunca, a Tarvo não).
- Percentual sempre em pontos percentuais. A Orbe já vem assim; a planilha vem em fração e é convertida antes de comparar.
- Nenhum número sai sem rastro, e a soma do rastro é conferida pelo código, não visualmente.

## Conferências contra os dados

| Conferência | Resultado |
|---|---|
| `valor_taxa` da Orbe é truncado? | Sim, em 1.840 de 1.840 vendas. Não serve de base nem de comparação. |
| Aurora e Meridiano | 84 lançamentos (L9 a L92) e 100 `FITID` únicos. |
| Ponte | 233 linhas, 232 `Nº Operação`, Σ spread = 78.073,59 = rodapé. |
| Taxas "inexistentes" na planilha | 4 de 5 são da Atlas (sem contrato); 4,09 é divergência real da Rota Global. |
| Par duplicado da Ponte | O "segundo par" do dicionário é a própria `PC-0926-0162`. **O dicionário estava errado.** |

## Onde a IA errou nesta sessão

- Usou o índice da coluna errada ao conferir `Valor ME × PTAX × Spread %` na Ponte e o script quebrou. Corrigiu e refez.
- Uma lista de "taxas fora da planilha" saiu inflada por comparar `Decimal` como texto (`2.1900` × `2.19`). A divergência por EC e faixa, feita em seguida, mostrou o quadro certo.
- Calculou a comissão preliminar da remessa como 50% × Σ (R$ 39.542,88). O Alvo arredonda **por operação** (regra do contrato de saída) e o valor final é **R$ 39.543,45** (`HIPOTESES.md` §5, H1).
