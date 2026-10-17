# Fechamento Tarvo — Mínimo e Alvo B

O escopo B do Alvo implementa ingestão da Ponte e dos bancos, remessa,
classificação contábil, tipos compartilhados, conservação e integração.
As regras bancárias ordenadas ficam em `config/regras.yaml`. Nenhuma API é necessária.

```powershell
python -m pytest -q
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/alvo
```

O pytest usa uma pasta `.pytest_tmp-<uuid>/` exclusiva por execução no projeto.
Isso evita reutilizar pastas privadas criadas por outra conta do Windows
(por exemplo, o sandbox do agente). As pastas são ignoradas pelo Git e ficam
disponíveis para inspeção após os testes. `--basetemp` explícito continua sendo
respeitado. A antiga `.pytest_tmp/` não é mais utilizada.

O Alvo é o padrão da CLI. A publicação real completa depende da entrega de A:
`ler_taxas` com `spread_remessa_pct`, checkout com todos os tipos e divergências,
e `src/regras/notas.py` com `gerar_notas`. Essas partes ainda não estão disponíveis
neste checkout. Sua ausência encerra a execução sem publicar resultados parciais.
O teste de integração substitui essas interfaces de A por exemplos controlados;
isso não atesta o gate completo do Alvo nem a revisão cruzada por outra pessoa.

Validação de B com as fontes reais: 233 operações (228 válidas, 4 contestações,
1 repetida), comissão de remessa R$ 39.543,45 e 41 divergências somando R$ 1.419,05;
184 lançamentos bancários por regra, com crédito não identificado de R$ 7.350 e
transferência sem contrapartida de −R$ 300.000. Para validar a remessa enquanto
A não entrega o leitor estendido, os testes leem a coluna de spread diretamente
da planilha original.

O Alvo descobre os arquivos obrigatórios por padrão, valida competência,
conserva cada linha de entrada e confere valores e rastro antes de publicar.
Escreve os seis CSVs em pasta temporária e reconfere em disco. A substituição
final é individual por arquivo; falha de sistema durante essa etapa pode deixar
arquivos de execuções distintas.

## Execução do Mínimo

Interface de operação: CLI e CSVs. Somente vendas de checkout entram no cálculo
mínimo; os demais tipos são contados como fora do escopo.

Na raiz do projeto, com Python 3.12 e as dependências de `requirements.txt`:

```powershell
python -m pytest -q
python -m src.main --nivel minimo --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/minimo
```

`--regras` e `--cadastro` aceitam caminhos alternativos. Os padrões são os arquivos
de `config/` relativos à raiz do projeto, independentemente do diretório de execução.
Os caminhos fornecidos pelo usuário são relativos ao diretório de execução.

O comando lê YAML com `safe_load`, exige uma planilha `02_*.xlsx` e usa as interfaces
de leitores e cálculo definidas em `CONTRATO_TECNICO_MINIMO.md`. Transação fora da
competência e arquivo ausente/ilegível encerram a execução com erro.

São publicados seis CSVs UTF-8 com separador `;`. Comissões, pendências e rastro
contêm os registros mínimos; divergências, notas e lançamentos têm somente cabeçalho.
Os valores de pendências de venda representam bruto bloqueado, não comissão perdida.
Pendências cadastrais usam zero e uma referência à planilha.

Antes da publicação, a execução exige cada venda exatamente uma vez em comissão ou
pendência, confere o resumo e grava os arquivos em uma pasta temporária junto ao
destino. O gravador valida o rastro em memória e em disco. Erros nessa preparação
preservam a saída anterior. A publicação substitui cada CSV individualmente; uma
falha de sistema durante a substituição pode deixar arquivos de execuções distintas.

## Histórico do Mínimo

A implementação de B publica os tipos em `src/core/contratos.py`, valida pendências
em `src/regras/pendencias.py` e integra a execução em `src/main.py`, reutilizando
`Saida` e `Origem`. Os testes de integração usam exemplos sintéticos nas interfaces
de A, sem recalcular comissões na CLI.

Os módulos de A (`src/ingest/orbe.py`, `src/ingest/taxas.py`,
`src/regras/checkout.py`), o cadastro e os tipos compartilhados foram recebidos
do remoto antes do commit de B. A integração entre as entregas e sua validação
ficam para tarefas futuras. Os testes de B usam exemplos sintéticos; esta entrega
não atesta o fechamento real, a revisão de cinco vendas nem os critérios M1–M8
completos. Não há resultados reais ou tag `minimo` nesta entrega de B.
