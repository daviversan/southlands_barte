# Histórico de uso de IA

Sessões de IA usadas na preparação e na construção da solução do case Tarvo, organizadas pelas fases do `PLANO.md`.

- **Ferramentas:** A usou Claude Code (extensão do VS Code), com os modelos registrados abaixo. B usou Codex; os sumários disponíveis não comprovam o identificador de modelo de cada sessão.
- **Pessoa A:** sessões em `Davi Versan/`. **Pessoa B:** sumários em `Igor Passo/`, complementados a partir da conversa disponível e das evidências do repositório.
- **Horários de A:** hora local de Brasília (BRT), 17/10/2026, a partir do registro de cada sessão. Para B, quando indicado, o horário é de commit, não de início/fim de conversa.
- **Identificador de A:** os 8 primeiros caracteres do id da sessão do Claude Code. Não foram inventados IDs para B.

> **Transcript × sumário.** Os **transcripts originais, sem edição**, estão em
> [`Davi Versan/transcripts/`](Davi%20Versan/transcripts/): um arquivo JSONL por sessão do Claude Code, com o nome igual ao
> id da sessão. Foram copiados como estavam. Uma varredura não achou chave de API nem token, então
> nada foi removido. Os arquivos `.md` desta pasta são **sumários** para leitura rápida: prompt quase
> literal, o que a IA devolveu e o que fizemos com isso. Em caso de dúvida, vale o transcript.

## Sessões, por fase

| Fase | Sessão | Horário | Modelo | Prompts | Sumário |
|---|---|---|---|---|---|
| Preparação (véspera) | `8167f221` | 00:27–00:30 | Opus 5.5 | 1 | [Davi Versan/00_preparacao.md](Davi%20Versan/00_preparacao.md) |
| Preparação: entender o case | `c41731a8` | 08:38–10:58 | Sonnet 5.5 / Haiku 5.5 | 7 | [Davi Versan/00_preparacao.md](Davi%20Versan/00_preparacao.md) |
| Preparação: Slack | `c2084350` | 10:59 | Sonnet 5.5 | 1 | [Davi Versan/00_preparacao.md](Davi%20Versan/00_preparacao.md) |
| Preparação: perguntas ao financeiro | `61646267` | 11:11–11:19 | Sonnet 5.5 | 4 | [Davi Versan/00_preparacao.md](Davi%20Versan/00_preparacao.md) |
| Preparação: plano para 2 pessoas | `3dd212e8` | 11:40–12:12 | Sonnet 5.5 | 3 | [Davi Versan/00_preparacao.md](Davi%20Versan/00_preparacao.md) |
| Fase 0: fundação | `18e4b96b` | 12:55–13:20 | Sonnet 5.5 | 6 | [Davi Versan/01_fase0_fundacao.md](Davi%20Versan/01_fase0_fundacao.md) |
| Mínimo (lado A) | `93ea5563` | 13:46–14:18 | Sonnet 5.5 | 6 | [Davi Versan/02_minimo.md](Davi%20Versan/02_minimo.md) |
| Alvo: verificação do Mínimo e specs | `300d01e3` | 14:37–15:08 | Sonnet 5.5 | 6 | [Davi Versan/03_alvo.md](Davi%20Versan/03_alvo.md) |
| Alvo (lado A) | `b0dd5359` | 15:11–15:59 | Opus 5.5 / Sonnet 5.5 | 8 | [Davi Versan/03_alvo.md](Davi%20Versan/03_alvo.md) |
| Extra + front | `4d13c32d` | 16:01–17:02 | Opus 5.5 / Sonnet 5.5 | 9 | [Davi Versan/04_extra_front.md](Davi%20Versan/04_extra_front.md) |
| Pós-Extra: plano de evolução, teste e retirada do LLM | `5f03a1f6` | 17:08–18:08 | Opus 5.5 | 7 | [Davi Versan/04_extra_front.md](Davi%20Versan/04_extra_front.md) |
| Deploy da tela no Streamlit Cloud | `c2fa2d57` | 17:38–17:58 | Opus 5.5 | 5 | só transcript |
| B: contexto, contratos e fundação | não disponível | não aferido | Codex, modelo não aferido | não aferido | [Igor Passo/00_contexto_fundacao.md](Igor%20Passo/00_contexto_fundacao.md) |
| B: Mínimo | não disponível | commit às 14:37 | Codex, modelo não aferido | agrupados por pedido | [Igor Passo/01_minimo.md](Igor%20Passo/01_minimo.md) |
| B: Alvo e integração | não disponível | commits às 15:35 e 15:39 | não aferido por sessão | não aferido | [Igor Passo/02_alvo_integracao.md](Igor%20Passo/02_alvo_integracao.md) |
| B: suporte, validação e correções do front | não disponível | não aferido | Codex na conversa disponível | agrupados por pedido | [Igor Passo/03_validacao_front.md](Igor%20Passo/03_validacao_front.md) |
| Consolidação deste histórico | sessão atual | sem horário de sessão aferido | Codex | pedido atual | [Igor Passo/04_documentacao.md](Igor%20Passo/04_documentacao.md) |

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

## Cobertura e limites dos registros de B

Os arquivos de B são **sumários complementares, não transcripts**. Implementação
observada nesta conversa, reconstrução por Git e relato de outra sessão são
identificados separadamente. Os transcripts integrais de B ainda precisam ser
anexados ou vinculados; o enunciado exige o histórico original de todas as sessões,
inclusive construção e preparação, sem edição além de chaves e dados pessoais.
Ter sumário de cada fase não elimina essa pendência.

O Extra tem registro original em A (`04_extra_front.md` e transcripts); não foi
atribuído a B só por constar de sua coluna no plano. Correções posteriores de front
e permissões são relacionadas no sumário de suporte de B. Pitch e checkpoints
devem ser comprovados por seus próprios registros; referências ao pitch nos
sumários não comprovam o envio do material final.
