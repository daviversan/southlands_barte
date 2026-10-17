# Sessão Claude Code: Fase 0 (Fundação)

> **Isto é um sumário, não o transcript.** O transcript original da sessão (JSONL do Claude Code) está em
> `~/.claude/projects/<projeto>/<id-da-sessao>.jsonl`
> e deve ser exportado sem edição (só chaves removidas) para esta pasta antes da entrega.
> Esta sessão executou as colunas A e B da Fase 0 do `PLANO.md` (seção 6.3).

## Prompts do usuário, em ordem

| # | Prompt | Resultado |
|---|---|---|
| 1 | "exclua o southlands_barte.code-workspace do repo remoto" | Arquivo removido do índice e do remoto (commit `2d78ff4`); mantido localmente |
| 2 | "Implemente a fase 0 - fundação do @PLANO.md" | Esqueleto, `normalize`, `saida`, configs, `HIPOTESES.md`, 45 testes verdes |
| 3 | "Salve um sumario das sessoes em Prompts [...] adicione o .gitignore e explique [...]" | Este arquivo, `MOMENTOS.md`, `.gitignore` atualizado |
| 4 | "Um novo arquivo `06_orbe_ajustes_tardios_set2026.csv` foi adicionado [...] verifique seus dados e se isso deveria adaptar algo no plano" | 14 linhas cruzadas com a Orbe e as taxas; `PLANO.md` (contagens, `ingest/orbe`) e `HIPOTESES.md` (§3.5, pergunta 17) atualizados |
| 5 | "verifique se a fase 0 esta pronta para eu dar push" | Checagem: testes verdes, sem segredos, pendências listadas; commit autorizado, push não |

## Passos da IA no prompt 2

1. Leu `PLANO.md`, `DICIONARIO_DADOS.md`, o LEIA-ME e o contrato de saída do enunciado (colunas dos 6 CSVs).
2. Criou o esqueleto e o ambiente (Python 3.12 via uv; o 3.11 do plano não existe na máquina).
3. Implementou `core/normalize.py` com `Decimal` e `ROUND_HALF_UP`, e `core/saida.py` com a regra "Σ rastro = valor reportado".
4. Escreveu os testes (`test_normalize`, `test_saida`, `test_config`): 45 passando.
5. Rodou scripts descartáveis (em `/tmp`, fora do repo) para confirmar as regras contra os dados reais.
6. Registrou os achados em `HIPOTESES.md`.

## Regras dadas à IA (não pedidas a ela)

- Arredondamento: `ROUND_HALF_UP` por linha, nunca `round()` do Python nem truncamento.
- Percentual sempre em pontos percentuais (Orbe já vem assim; planilha em fração é convertida).
- Rastro conferido ao centavo; falha se não fechar.
- Nenhuma chamada de API: a Fase 0 não usa IA em runtime.

## Verificado à mão / contra os dados (3+ conferências)

- `valor_taxa` da Orbe é truncado em 1.840/1.840 vendas.
- Aurora: 84 lançamentos (L9 a L92); Meridiano: 100 FITIDs únicos.
- Ponte: 233 linhas, 232 `Nº Operação`, Σ spread = 78.073,59 = rodapé.

## Pendente fora da IA

Mensagens no Slack (lote 1 e dúvida do `ref_origem` Aurora), horários em `HIPOTESES.md`, Checkpoint 1.
