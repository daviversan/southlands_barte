# Preparação: entender o case, perguntar e planejar

Pessoa A · 5 sessões · da véspera até 12h12 de 17/10 · nenhuma linha de código de produção.

Objetivo das sessões: entender de onde vem cada número e o que ainda não se sabe, antes de construir (o primeiro erro listado pelo enunciado).

---

## Sessão `8167f221` · 00:27–00:30 · Opus 5.5 · primeiro plano

| Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|
| "Estou participando de um hackathon da empresa Barte AI em um time de 3 pessoas. O contexto da competição, incluindo case e dados de referência, estão na pasta @context/. Preciso que você gere um plano de implementação passo a passo que solucione o case e divida as tarefas entre os 3 membros do grupo. Atente-se aos critérios de avaliação, incluindo o histórico de uso de IA solicitado pelos organizadores. Em seu plano, defina a arquitetura da solução, separando a lógica de [dados, back e front] […]" | Leu o enunciado e perfilou os 6 arquivos (inclusive o anexo xlsx da Ponte, lido pelo XML cru). Escreveu o primeiro `PLANO.md`: causa raiz com exemplos dos dados (sem chave comum entre fontes, planilha frágil, regras na cabeça das pessoas) e arquitetura em 3 camadas. | Base do plano. Foi reescrito depois para 2 pessoas (sessão `3dd212e8`). |

## Sessão `c41731a8` · 08:38–10:58 · Sonnet 5.5 / Haiku 5.5 · entender o case

| # | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|
| 1 | "explique quais são as entidades envolvidas no case e como elas se relacionam entre si (ex: Tarvo, Orbe etc)" | Tabela de entidades (Tarvo, lojistas, Orbe, Ponte, bancos, ERP) e como cada fonte identifica o lojista. Declarou que **não abriu** o CSV da Orbe, o xlsx nem os extratos. | Entendimento do domínio. |
| 2 | "explique o fluxo de dinheiro entre as entidades" | Fluxo aluno → Orbe → Aurora → lojistas, e Aurora → Meridiano → Ponte → exterior, confirmado nos extratos. Avisou que leu só o início dos arquivos. | Base do diagrama. |
| 3 | "explique de forma objetiva por que a operação quebra, por que o fechamento é lento e erra, qual o principal problema desse case e o que se espera que a solução seja capaz de resolver" | Causa raiz em 3 pontos: sem chave comum, regras tácitas, ninguém compara taxa aplicada × contratada. | Virou a seção 1 do `PLANO.md` e o texto do Checkpoint 1. |
| 4 | "gere um diagrama do fluxo do dinheiro com as entidades envolvidas e taxas cobradas em cada etapa." | Gerou `fluxo-dinheiro-tarvo.html`. **A publicação como Artifact falhou** (sessão sem login no claude.ai); a IA disse isso e entregou o arquivo local. | Copiamos para `context/fluxo-dinheiro-tarvo.html`. |
| 5 | "consolide perguntas relevantes para eu fazer ao time financeiro para embasar as decisões de negócio e desenvolvimento da solução" | 13 perguntas em blocos, cada uma com a decisão que destrava e o que assumir sem resposta. | Lote 1 e lote 2 do `PLANO.md` §5. |
| 6 | "gere um dicionário de dados explicando as entidades dos arquivos em tarvo_data_pack" | Perfilou os arquivos (encoding, volume, colunas, padrões de lançamento) e escreveu `DICIONARIO_DADOS.md`. | Referência do time. **Continha um erro** (par duplicado da Ponte), achado na Fase 0. |
| 7 | "Dado que a entrega mínima é a comissão de checkout por lojista, com rastro, explique como podemos desenvolver o cálculo da comissão do checkout e aplicar a rastreabilidade das transações" | Rodou uma análise descartável nos dados reais e propôs: comissão = soma de comissões **por transação**; o rastro é a própria lista de parcelas; toda linha da Orbe termina em comissão **ou** pendência. | Desenho adotado no contrato de saída (`core/saida.py`) e no Mínimo. |

## Sessão `c2084350` · 10:59 · Sonnet 5.5 · Slack

| Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|
| "como integrar o canal do slack para puxar contexto das perguntas e respostas que estão sendo enviados nas mensagens? [link de convite do Slack]" | Explicou que o link é só um convite, sem acesso por API, e que não ia usá-lo para entrar no canal. Listou 3 alternativas. | Seguimos copiando as respostas do canal manualmente para o prompt. |

## Sessão `61646267` · 11:11–11:19 · Sonnet 5.5 · perguntas ainda abertas

| # | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|
| 1 | "essas foram as respostas enviadas para perguntas de outros membros da competição […] Elabore perguntas que ainda não foram respondidas pelo time financeiro para eu enviar no canal do slack" | **As respostas não tinham sido coladas.** Em vez de inventar o que já fora respondido, a IA parou e pediu o texto. | Colamos as respostas no prompt seguinte. |
| 2 | "respostas: [respostas do financeiro coladas: base da comissão, estornos, antecipações, remessa, NFs…]" | Cruzou as respostas com as 13 perguntas: 12 respondidas. Gerou perguntas novas sobre lacunas que as respostas abriram, ordenadas por impacto no número. | — |
| 3 | "sumarize em 5 perguntas objetivas e de fácil legibilidade" | 5 perguntas, ainda presas a lojistas específicos (Atlas, Casa do Estudante, Rota Global). | Pedimos para generalizar. |
| 4 | "prefira perguntas que orientem a regras gerais de funcionamento do fluxo ao invés de casos específicos de clientes" | 5 perguntas sobre regras gerais (estorno de mês anterior, lojista sem contrato, cobrança acima do contrato…). | Enviadas no #tarvo-financeiro. |

## Sessão `3dd212e8` · 11:40–12:12 · Sonnet 5.5 · plano para 2 pessoas

| # | Prompt | O que a IA fez | O que fizemos com isso |
|---|---|---|---|
| 1 | "Atualize o @PLANO.md para o case em @context/ considerando agora um time de 2 pessoas. Delimite as etapas de desenvolvimento conforme os níveis de entrega (mínimo, alvo e extra), definindo critérios de aceite e definições de pronto para cada uma" | Reescreveu o `PLANO.md`: A = checkout e fiscal, B = remessa, bancos e plataforma; critérios M1–M8, A1–A17, E1–E5; gates de go/no-go. Avisou que não testou o plano contra os dados. | Plano usado no resto do dia. |
| 2 | "gere um diagrama para essa nova arquitetura proposta considerando os três níveis de entrega similar ao formato de @context/fluxo-dinheiro-tarvo.html" | `context/arquitetura-niveis-tarvo.html`, com etiquetas MÍN/ALVO/EXTRA por módulo. | Referência visual da arquitetura. |
| 3 | "atualize o @PLANO.md com as respostas das perguntas que foram geradas a partir das suposições: [respostas da Helena coladas]" (a primeira tentativa falhou por erro de autenticação; o prompt foi reenviado) | Marcou cada regra como [CONFIRMADO], [PARCIAL] ou [ASSUMIDO] e atualizou o status das perguntas. | Regras de negócio confirmadas entram no plano **antes** do código. |
