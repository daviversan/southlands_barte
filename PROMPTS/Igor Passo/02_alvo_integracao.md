# B — Alvo: remessa, bancos e integração

**Natureza:** implementação reconstruída por commits `ea48b0f` e `559c6af`, contrato,
código/testes e `HIPOTESES.md` §5.2. Os prompts originais dessa implementação não
estão nesta conversa. A revisão posterior do rastro está na conversa disponível.

## Escopo e implementação verificáveis

- Leitura do anexo xlsx do `.eml` da Ponte, dos extratos Aurora/Meridiano e do plano
  de contas analíticas.
- Remessa identificada por CNPJ: comissão de 50% do spread realizado; repetida conta
  uma vez; spread negativo vira contestação; spread contratado ausente impede só a divergência.
- Classificação bancária por regras ordenadas; conta não inventada quando falta regra;
  conferência de contrapartidas e pendências de lançamentos sem identificação.
- CLI integra checkout, remessa, notas e bancos; conserva as entradas e confere
  relação das notas com comissões e origens antes de publicar.
- Correção dos temporários dos testes para reduzir conflitos de permissões no Windows.

## Evidências de resultado

`HIPOTESES.md` §5.2 registra: checkout R$ 191.464,34; remessa R$ 39.543,45;
92 divergências de checkout e 41 de remessa; 184 lançamentos por regra; 19 notas;
302 pendências. Duas execuções geram arquivos idênticos.

Na Ponte, 233 linhas = 228 válidas + 4 contestações + 1 repetida. A repetida usa
referência `PC-0926-0162#2`; o valor da comissão segue arredondamento por operação,
em vez do preliminar de metade da soma. Decisões em H1/H2 de `HIPOTESES.md`.

Esses números são evidência registrada da implementação, não constantes do algoritmo
nem um recálculo manual novo feito nesta consolidação.

## Revisão dirigida pelo usuário na conversa disponível

O usuário pediu explicar o nível de rastro existente no Alvo e o previsto para o
Extra. A IA leu código, plano, README e executou **176 testes, todos passando**.
Explicou que todas as categorias COM/DIV/NF/LAN/PEN já têm origens monetárias e
conferência em memória/disco, mas que o CSV não registra cada passo da fórmula.

A IA apontou a exceção de `NF_NAO_EMITIDA`: essa pendência pode ter várias origens,
como a comissão, embora o plano propusesse PEN 1:1. O Extra depois explicitou a
exceção em X2. Isso evita descartar contribuições só para cumprir a cardinalidade.

## Limites

Os recálculos independentes de scripts não equivalem à revisão cruzada humana A↔B,
que permanece pendente no registro consultado. A etapa Extra inicial e suas
conversas estão em `../Davi Versan/04_extra_front.md`; não foram atribuídas a B por suposição.
