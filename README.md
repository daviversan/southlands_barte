# Fechamento Tarvo — nível Alvo

Interface de operação: CLI e CSVs. Um comando lê os arquivos do mês **como vêm** e gera os seis
CSVs do enunciado: comissões de checkout e remessa, divergências de taxa, notas a emitir,
lançamentos bancários classificados, pendências e rastro. Não precisa de `ANTHROPIC_API_KEY`.

Na raiz do projeto, com Python 3.12 e as dependências de `requirements.txt` instaladas num venv:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m pytest -q
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/
```

Outro mês é o mesmo comando com outra pasta e outra competência. `--regras` e `--cadastro`
aceitam caminhos alternativos; os padrões são `config/regras.yaml` e `config/lojistas.yaml`.

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

O comando imprime o resumo de conservação: Orbe por tipo e por arquivo, reconciliação do rodapé da
Ponte, bancos por regra e pendências por tipo e por `quem_decide`.

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
- `pendencias`: o valor de uma linha bloqueada é o **bruto assinado** (Orbe), o `Spread R$`
  (Ponte) ou o valor do lançamento (bancos), não a comissão perdida. A operação repetida da Ponte
  aparece como `<Nº Operação>#2`.

## Limitações conhecidas

- Sem fallback de IA e sem interface gráfica (nível Extra): linha bancária sem regra vira
  pendência `HUMANO`; a analista usa a CLI e abre os CSVs.
- Perguntas abertas ao financeiro (spread padrão, Horizonte/Kiwi, ressalva, provisão de folha,
  tomador da NF de checkout, `ref_origem` do Aurora) estão parametrizadas e listadas em `HIPOTESES.md`.
