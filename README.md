# Fechamento Tarvo — nível mínimo

Interface de operação: CLI e CSVs. Somente vendas de checkout entram no cálculo
mínimo; os demais tipos são contados como fora do escopo.

Na raiz do projeto, com Python 3.12 e as dependências de `requirements.txt`:

```powershell
python -m pytest -q
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/minimo
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

## Estado da integração

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
