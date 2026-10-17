# Fechamento Tarvo — setembro/2026

Solução do case Tarvo (Desafio Barte AI). Um comando lê os arquivos do mês **como vêm**, sem
limpeza manual, e gera os seis CSVs do enunciado em `saida/`:

1. comissões de cada lojista, por linha de negócio (checkout e remessa);
2. divergências entre taxa contratada e aplicada, transação por transação;
3. notas fiscais a emitir;
4. lançamentos dos dois extratos classificados no plano de contas;
5. pendências que exigem uma pessoa, com motivo e quem decide;
6. o rastro, que liga cada número às linhas de origem.

Nível entregue: **Alvo + Extra** (rastro completo com conferência automática, pendências
explicadas e execução para outubro sem retrabalho). Interface: CLI e CSVs, mais uma tela opcional
em Streamlit.

## Instalar e rodar do zero

Python 3.12. De um clone limpo:

```bash
git clone https://github.com/daviversan/southlands_barte.git && cd southlands_barte
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/
```

Testes: `python -m pytest -q`.

## Chaves necessárias

**Nenhuma.** Todo número sai de regra determinística, sem chamada a API externa. Não é preciso
configurar `ANTHROPIC_API_KEY` nem outra credencial.

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `README.md` | este arquivo |
| `HIPOTESES.md` | premissas assumidas, perguntas ao financeiro e respostas recebidas |
| `PROMPTS/` | histórico das sessões de IA (transcripts e sumários) + `MOMENTOS.md` |
| `saida/` | os seis CSVs gerados a partir do data pack |
| `src/` | código: `ingest/` (leitura das fontes), `regras/` (cálculos), `core/` (contrato de saída e conferência), `main.py` (CLI), `app.py` (tela) |
| `config/` | regras e cadastro mestre de lojistas (`regras.yaml`, `lojistas.yaml`) |
| `tests/` | testes automáticos |
| `context/tarvo_data_pack/` | entrada do case, intocada |
| `PLANO.md`, `DICIONARIO_DADOS.md`, `CONTRATO_TECNICO_*.md` | plano por nível de entrega, dicionário de dados e specs usados na construção |

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
streamlit run src/app.py
```

O `streamlit` já vem no `requirements.txt`. O pipeline não depende dele.

A tela não tem regra de negócio: chama o mesmo `main.run()` da CLI e só lê `saida/`.

## Limitações conhecidas

- Linha bancária sem regra vira pendência `HUMANO` para o Contador; não há classificação por IA.
  Em setembro, os 184 lançamentos fecham por regra.
- A tela Streamlit não tem teste automático de interface: a lógica que ela usa é testada, mas a
  renderização só foi conferida à mão.
- Fora do escopo: conciliação das TEDs da Orbe com o líquido das transações, emissão real de NF e
  integração com o ERP Fênix.
- Perguntas abertas ao financeiro (spread padrão, Horizonte/Kiwi, ressalva, provisão de folha,
  tomador da NF de checkout, `ref_origem` do Aurora) estão parametrizadas e listadas em `HIPOTESES.md`.
