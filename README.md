# Fechamento Tarvo — níveis Alvo e Extra

Interface de operação: CLI e CSVs (e, opcionalmente, uma tela em Streamlit). Um comando lê os
arquivos do mês **como vêm** e gera os seis CSVs do enunciado: comissões de checkout e remessa,
divergências de taxa, notas a emitir, lançamentos bancários classificados, pendências e rastro.
Não usa API externa nem chave.

De um clone limpo, com Python 3.12:

```bash
git clone <url-do-repositorio> southlands_barte && cd southlands_barte
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/
```

Testes: `python -m pytest -q`.

Os testes usam uma pasta `.pytest_tmp-<uuid>/` exclusiva por execução, ignorada
pelo Git. Isso evita conflitos de permissões entre o usuário e a conta do
sandbox no Windows. Um `--basetemp` explícito continua sendo respeitado.
Os documentos gerados em `saida/` são ignorados; apenas `.gitkeep` é preservado.
Na publicação, a pasta de preparação usa as permissões herdadas da pasta pai.
Isso permite ler os CSVs no front mesmo quando o fechamento é executado pela
conta do sandbox no Windows; uma pasta temporária privada transferia sua ACL
restritiva para os arquivos ao movê-los.

## Outro mês (outubro em diante)

É o mesmo comando com outra pasta e outra competência; não há data, EC, CNPJ ou nome de lojista no
código (um teste varre `src/` atrás deles):

```bash
python -m src.main --entrada <pasta-de-outubro> --competencia 2026-10 --saida saida/
```

- Os arquivos são achados pelo **padrão do nome** (tabela abaixo) e o cabeçalho de cada um pelo
  **conteúdo**, não pelo número da linha. O arquivo de ajustes da Orbe (`06_`) é opcional.
- Lojista novo, sem cadastro, vira **pendência**, nunca erro. Para liberar: confirmar o EC e
  registrá-lo em `config/lojistas.yaml`; taxa nova vai na aba "Taxas vigentes" da planilha. Depois,
  rodar de novo.
- Linha de um mês diferente do `--competencia` interrompe a execução sem tocar na saída anterior.
- `tests/test_extra.py` roda o data pack inteiro deslocado para outubro, sem mudar código.

`--regras` e `--cadastro` aceitam caminhos alternativos; os padrões são `config/regras.yaml` e
`config/lojistas.yaml`.

## Entradas (descobertas por padrão de nome)

| Papel | Padrão | Obrigatório |
|---|---|---|
| Orbe | `01_orbe_*.csv` + `06_orbe_ajustes_*.csv` | 01 sim, 06 não |
| Taxas contratadas | `02_*.xlsx` (só a aba "Taxas vigentes") | sim, exatamente um |
| Ponte Câmbio | `03_*.eml` (anexo xlsx lido em memória) | sim, exatamente um |
| Plano de contas | `04_*.csv` | sim, exatamente um |
| Aurora | `05a_*.csv` | sim, exatamente um |
| Meridiano | `05b_*.ofx` | sim, exatamente um |

## O que o comando garante antes de publicar

- Cada linha da Orbe, da Ponte e dos extratos aparece **exatamente uma vez**: numa comissão, num
  lançamento ou numa pendência bloqueante. Pendências cadastrais e sinalizações são adicionais.
- Σ rastro por `id_saida` = valor publicado, ao centavo, em memória e de novo em disco.
- Σ NF = Σ comissões por linha de negócio (com as mesmas origens no rastro); `conta_codigo` só de
  contas analíticas do plano (`ACEITA_LANCTO = S`), vazio apenas para `metodo = HUMANO`.
- Linha fora da competência, arquivo ausente/ambíguo, configuração inválida ou conta inexistente
  encerram a execução com erro e **preservam a saída anterior** (grava em pasta temporária e só
  então substitui os CSVs).

- **Conferência automática** (`src/core/conferencia.py`): antes de publicar, os CSVs gravados são
  relidos e cruzados com as entradas — Σ de cada arquivo × Σ do rastro, rastro 1:1 de divergências,
  lançamentos e pendências, toda origem do rastro existe numa entrada, cada linha da Orbe, da Ponte
  e dos extratos aparece uma vez, totais de bruto, spread e extrato fecham, NF = comissões. Se uma
  checagem falhar, o comando termina com erro e a saída anterior fica intacta.

O comando imprime o resumo de conservação (Orbe por tipo e por arquivo, reconciliação do rodapé da
Ponte, bancos por regra, pendências por tipo e por `quem_decide`) e o relatório da conferência,
uma linha por checagem com `[ok]`, `[aviso]` ou `[FALHA]`.

## Onde estão as regras

Nenhum CNPJ, EC, nome de lojista, padrão de extrato ou conta contábil está no código:

- `config/regras.yaml` — parâmetros de checkout, remessa, notas e a lista **ordenada** de regras
  bancárias (padrão → conta). Folha e impostos de 08: `bancos.folha_e_impostos_de_08`
  (`baixa_provisao` | `despesa`). Numeração do Aurora: `bancos.aurora_ref_offset` (0 = `L9`).
- `config/lojistas.yaml` — cadastro mestre EC → CNPJ, gerado da planilha por EC exato e completado
  só com confirmação humana.
- `HIPOTESES.md` — o que é confirmado pelo financeiro, assumido ou decidido pelo time.

## Leitura das saídas

- `comissoes_por_lojista`: CHECKOUT (taxa contratada; estornos e reversões abatem o mês em que
  ocorrem) e REMESSA (50% do `Spread R$` realizado, por CNPJ, arredondado por operação).
- `divergencias_taxa`: positivo = o lojista pagou a mais; estorno de venda divergente é negativo.
  Remessa usa o valor cheio. Divergência é só reportada; não é restituição.
- `pendencias`: `motivo` em linguagem de negócio, `quem_decide` de uma lista fechada (Financeiro,
  Comercial, Ponte, Contador) e a coluna extra `sugestao` com o próximo passo. O catálogo por tipo
  fica em `config/regras.yaml` (`pendencias.tipos`). O valor de uma linha bloqueada é o valor bruto
  da transação (Orbe), o spread (Ponte) ou o valor do lançamento (bancos), não a comissão perdida.
  A operação repetida da Ponte aparece como `<Nº Operação>#2`.
- `rastro`: cada número publicado aponta para as linhas de origem (`arquivo_origem`, `ref_origem`)
  e a soma do rastro é igual ao valor publicado, ao centavo.

## Tela (opcional)

Para quem prefere não abrir CSVs: rodar o fechamento, ver os totais e a conferência, escolher um
`id_saida` e ver as linhas de origem, e a fila de pendências por `quem_decide`.

```bash
pip install streamlit
streamlit run src/app.py
```

A tela não tem regra de negócio: chama o mesmo `main.run()` da CLI e só lê `saida/`.

## Limitações conhecidas

- Linha bancária sem regra vira pendência `HUMANO` para o Contador; não há classificação por IA.
- A tela Streamlit foi testada com um Streamlit simulado (o pacote não pôde ser instalado no
  ambiente de desenvolvimento); falta abrir e conferir visualmente.
- Perguntas abertas ao financeiro (spread padrão, Horizonte/Kiwi, ressalva, provisão de folha,
  tomador da NF de checkout, `ref_origem` do Aurora) estão parametrizadas e listadas em `HIPOTESES.md`.
