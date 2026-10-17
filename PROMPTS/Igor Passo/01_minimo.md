# B — Mínimo: saída, pendências e CLI

**Fonte:** conversa disponível com Codex e commit `5859b6a`. Este é um sumário,
não o histórico integral. Modelo e ID da sessão não foram aferidos.

## Pedidos, respostas e condução humana

| Pedido do usuário | O que a IA entregou | O que o usuário fez com isso |
|---|---|---|
| Implementar as tarefas de B do Mínimo conforme plano e contrato | Tipos compartilhados, validação de pendências, CLI, testes sintéticos e README | Pediu explicação de arquivos e funções para validar |
| Resumir o implementado e a serventia das pastas | Explicou responsabilidades de core, regras, leitores, configurações e testes | Prosseguiu com revisão e publicação |
| Fazer add, commit e push | Conferiu status e preparou a publicação | Corrigiu a sequência: pull primeiro, integração em tarefa futura |
| Usar mensagem de commit mais significativa, indicando o nível do plano | Commit com descrição da infraestrutura B do nível Mínimo | Commit e push concluídos em `main` |

## Implementação

- Reutilizou `Saida` e `Origem`, sem criar gravador paralelo.
- `src/regras/pendencias.py`: campos obrigatórios, responsável, Decimal finito,
  origem relativa e soma do rastro.
- `src/main.py`: YAML com safe_load, competência, chamada às interfaces de A,
  conservação das vendas, ordenação dos IDs e publicação após preparação/conferência.
- `src/core/saida.py`: rejeição adicional de NaN/infinito.
- Testes de formato, rastro, bruto assinado em bloqueios, arredondamento e
  preservação da saída anterior quando a preparação falha.

## Correções e verificação

Inicialmente os módulos de A não estavam no checkout local. A IA trabalhou com
exemplos sintéticos nas interfaces previstas, sem assumir o escopo de A.
O pull solicitado trouxe `66e0275`, incluindo `contratos.py` mais completo. A IA
preservou essa versão e restaurou somente os sete arquivos de B; atualizou o README.

O commit foi `5859b6a`:
`feat(minimo): implementa infraestrutura de saída, pendências e CLI do membro B`.
A descrição explicita que integração e validação completa ficam para tarefas futuras.

Na implementação inicial, sintaxe e diff foram conferidos, mas a suíte estava
bloqueada por dependências ausentes. A IA relatou a limitação, sem afirmar testes
verdes. A instalação e a execução posteriores estão em `03_validacao_front.md`.
