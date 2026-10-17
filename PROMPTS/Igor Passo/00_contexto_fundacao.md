# B — contexto, fundação e contratos

**Natureza:** sumário documental, sem reconstrução de diálogo literal. Os prompts
originais de elaboração do contrato por B não estão na conversa disponível.

## Direção do time

O plano separa A (checkout/fiscal) de B (remessa/bancos/plataforma) e exige regras
determinísticas, identidade exata, premissas explícitas e rastro monetário conferido.
O contrato fixa a fronteira: A calcula registros em memória; B valida e grava.

## Evidências e artefatos

- Preparação, causa raiz e perguntas ao financeiro: registros originais em
  `../Davi Versan/00_preparacao.md` e `../Davi Versan/transcripts/`.
- Fundação compartilhada: `../Davi Versan/01_fase0_fundacao.md`, sessão `18e4b96b`, commit
  `9378773`; normalização com Decimal, gravador e testes. Esse trabalho não é
  apresentado como sessão separada de B sem evidência.
- Contrato mínimo de B: `CONTRATO_TECNICO_MINIMO.md`, commit `51ece5f`.
- Contrato Alvo: `CONTRATO_TECNICO_ALVO.md`, commit `e8359f4`, com elaboração e
  revisão registradas nas sessões de A em `../Davi Versan/03_alvo.md`.

## Regras que guiaram a IA

Comissão pela taxa contratada, sem descontar custo da Orbe; ROUND_HALF_UP por
transação; EC/CNPJ exatos, sem fuzzy match; venda bloqueada como pendência, sem
inventar comissão. Configuração e hipóteses guardam as regras mutáveis.

Os números preliminares foram corrigidos quando necessário. Exemplo: remessa
arredondada por operação soma R$ 39.543,45; metade do spread total daria R$ 39.542,88.
É decisão técnica documentada em H1, não nova confirmação do financeiro.

## Verificação e limites

O registro de A documenta scripts contra os arquivos brutos e erros corrigidos.
Não se atribuiu horário de conversa a partir do horário de commit. O histórico
integral de B para a preparação e o contrato continua pendente de exportação/link.
