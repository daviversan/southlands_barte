# Histórico de uso de IA

Sessões de IA usadas na preparação e na construção da solução do case Tarvo, organizadas pelas fases do `PLANO.md`.

- **Ferramenta:** Claude Code (extensão do VS Code), modelos Claude Sonnet 5.5, Opus 5.5 e Haiku 5.5.
- **Pessoa A:** sessões desta pasta (`A/`). **Pessoa B:** sessões em `B/`, que rodaram em outra máquina.
- **Horários:** hora local de Brasília (BRT), 17/10/2026, a partir do registro de cada sessão.
- **Identificador:** os 8 primeiros caracteres do id da sessão do Claude Code.

> **Transcript × sumário.** Os **transcripts originais, sem edição**, estão em
> [`A/transcripts/`](A/transcripts/): um arquivo JSONL por sessão do Claude Code, com o nome igual ao
> id da sessão. Foram copiados como estavam. Uma varredura não achou chave de API nem token, então
> nada foi removido. Os arquivos `.md` desta pasta são **sumários** para leitura rápida: prompt quase
> literal, o que a IA devolveu e o que fizemos com isso. Em caso de dúvida, vale o transcript.

## Sessões, por fase

| Fase | Sessão | Horário | Modelo | Prompts | Sumário |
|---|---|---|---|---|---|
| Preparação (véspera) | `8167f221` | 00:27–00:30 | Opus 5.5 | 1 | [A/00_preparacao.md](A/00_preparacao.md) |
| Preparação: entender o case | `c41731a8` | 08:38–10:58 | Sonnet 5.5 / Haiku 5.5 | 7 | [A/00_preparacao.md](A/00_preparacao.md) |
| Preparação: Slack | `c2084350` | 10:59 | Sonnet 5.5 | 1 | [A/00_preparacao.md](A/00_preparacao.md) |
| Preparação: perguntas ao financeiro | `61646267` | 11:11–11:19 | Sonnet 5.5 | 4 | [A/00_preparacao.md](A/00_preparacao.md) |
| Preparação: plano para 2 pessoas | `3dd212e8` | 11:40–12:12 | Sonnet 5.5 | 3 | [A/00_preparacao.md](A/00_preparacao.md) |
| Fase 0: fundação | `18e4b96b` | 12:55–13:20 | Sonnet 5.5 | 6 | [A/01_fase0_fundacao.md](A/01_fase0_fundacao.md) |
| Mínimo (lado A) | `93ea5563` | 13:46–14:18 | Sonnet 5.5 | 6 | [A/02_minimo.md](A/02_minimo.md) |
| Alvo: verificação do Mínimo e specs | `300d01e3` | 14:37–15:08 | Sonnet 5.5 | 6 | [A/03_alvo.md](A/03_alvo.md) |
| Alvo (lado A) | `b0dd5359` | 15:11–15:59 | Opus 5.5 / Sonnet 5.5 | 8 | [A/03_alvo.md](A/03_alvo.md) |
| Extra + front | `4d13c32d` | 16:01–17:02 | Opus 5.5 / Sonnet 5.5 | 9 | [A/04_extra_front.md](A/04_extra_front.md) |
| Pós-Extra: plano de evolução, teste e retirada do LLM | `5f03a1f6` | 17:08–18:08 | Opus 5.5 | 7 | [A/04_extra_front.md](A/04_extra_front.md) |
| Deploy da tela no Streamlit Cloud | `c2fa2d57` | 17:38–17:58 | Opus 5.5 | 5 | só transcript |
| Lado B (Mínimo e Alvo) | — | — | — | — | [B/README.md](B/README.md) |

- A sessão `18e4b96b` continuou depois da Fase 0 para gerar estes sumários.
- A sessão `3dd212e8` continuou depois do plano: diagrama de arquitetura por nível, aplicação das respostas do financeiro no `PLANO.md` e, no fim, este README e o da raiz.
- Os horários da tabela são do primeiro e do último registro de cada transcript. Os sumários `.md` cobrem até 17h13; o que veio depois está só nos transcripts.

## Como dirigimos a IA (padrão das sessões)

1. **Entender antes de construir.** As 5 primeiras sessões não escrevem código: entidades, fluxo do dinheiro, causa raiz, dicionário de dados e perguntas ao financeiro.
2. **Dar a regra, não pedir a regra.** As regras de negócio vieram das respostas do financeiro (Helena) e foram coladas nos prompts. A IA só as transcreveu para o `PLANO.md`, o `HIPOTESES.md` e o código.
3. **Spec antes de cada nível.** `CONTRATO_TECNICO_MINIMO.md` e `CONTRATO_TECNICO_ALVO.md` foram escritos antes da implementação, para A e B trabalharem em paralelo contra a mesma interface.
4. **Verificar com recálculo independente.** Depois de cada nível pedimos um recálculo que não importa nada de `src/`, a partir dos arquivos brutos. Comissões, notas e totais foram conferidos ao centavo dessa forma.
5. **Cortar o que a IA propunha e não servia.** O fallback de LLM na classificação bancária foi retirado do plano antes do Extra (sessão `b0dd5359`). Depois, um LLM para redigir motivos de pendência foi implementado e testado, mas nenhuma linha de setembro precisava dele, e ele foi removido (sessão `5f03a1f6`).

Os momentos mais importantes, incluindo erros da IA, estão em [MOMENTOS.md](MOMENTOS.md).
