# Plano de implementação — Case Tarvo (fechamento set/2026)

Time de **2 pessoas (A e B)** · janela 9h–18h30 · ≈ 6–7h de trabalho efetivo por pessoa (dev + pitch).
Princípio: **regra determinística primeiro, IA só onde há texto livre, pessoa onde há decisão.** Todo número sai com rastro.
Organização: o trabalho é fatiado pelos **níveis de entrega do enunciado (Mínimo → Alvo → Extra)**. Cada nível tem escopo, critérios de aceite, definição de pronto e um **gate** de go/no-go (seção 6). Não se começa o nível seguinte com o anterior vermelho.

---

## 1. Causa raiz (o que vai no pitch e no Checkpoint 1)

O fechamento não é lento porque é manual. É lento porque **não existe uma chave comum entre as fontes** e **as regras estão na cabeça das pessoas**:


| Sintoma                                      | Evidência no data pack                                                                                                                                                                                                                                                                      |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Não há chave única do lojista                | Orbe usa EC + nome (22 ECs com 31 grafias; `Mundo Aberto`, `MUNDO ABERTO INTERC LTDA`…); Ponte usa CNPJ em 2 formatos e nome truncado em 20 caracteres; bancos usam só nome truncado; planilha tem 5 lojistas sem EC (`Kiwi: EC pendente`, Horizonte, Novo Horizonte, Ponte Aérea, Nórdica) |
| Planilha de taxas frágil                     | Taxas como fração **e** como texto (`'2,59%'`), CNPJ como número (perde zero à esquerda), vigência dupla (Bridge muda em 15/09), spread `padrão`/em branco, aba antiga "não usar" que contém um lojista ativo (Atlas)                                                                       |
| Ninguém confere taxa aplicada × contratada   | A Orbe traz a taxa aplicada linha a linha; 5 taxas observadas (0,99; 1,99; 3,99; 4,09; 4,49) não existem na aba vigente e só se descobre quando o lojista reclama                                                                                                                           |
| Relatório do parceiro é aceito sem validação | Ponte: 233 linhas para 232 `Nº Operação` (+ um par com mesmo CNPJ/valor/moeda/data), 4 spreads negativos, 16 "APROVADO C/ RESSALVA", spread realizado × estimado D-1; o rodapé (233 / R$ 78.073,59) **inclui** repetida e negativos                                                         |
| Exceções sem dono                            | Crédito PIX de CNPJ desconhecido (R$ 7.350), devolução PIX, TED de R$ 300 mil sem contrapartida, lojista sem contrato vigente                                                                                                                                                               |


**Tese:** a solução cria o **cadastro mestre de lojistas (EC ↔ CNPJ)**, transforma regras tácitas em **configuração escrita** e separa automaticamente o que fecha sozinho do que **precisa de uma pessoa**.

---



## 2. Arquitetura

```
entrada/ (arquivos como vêm)          config/                     saida/
 01 orbe.csv ─┐                    regras.yaml  ◄── respostas    comissoes_por_lojista.csv
 02 taxas.xlsx┤                    lojistas.yaml     do financeiro divergencias_taxa.csv
 03 ponte.eml ┤  ┌──────────────┐  (EC↔CNPJ, spread padrão,     notas_a_emitir.csv
 04 plano.csv ┼─►│ DADOS        │   regex banco→conta)          lancamentos_classificados.csv
 05a aurora   ┤  │ ingest/*     │─────────┐                     pendencias.csv
 05b meridiano┘  └──────────────┘         ▼                     rastro.csv
                                   ┌──────────────┐                  ▲
                                   │ BACK         │  core/saida.py ──┘ (escreve saída + rastro
                                   │ regras/*     │  e valida soma = total)
                                   │ ia/llm.py    │◄─ [EXTRA] fallback de classificação bancária
                                   └──────┬───────┘
                                          ▼
                                   ┌──────────────┐
                                   │ FRONT        │  [EXTRA] Streamlit fino: rodar, ver resultados,
                                   │ app.py       │  clicar no número → rastro, fila de pendências
                                   └──────────────┘  (até lá, a interface é a CLI + os CSVs)
```



### Camada de dados (`src/ingest/`, `src/core/normalize.py`)

Lê cada arquivo **sem limpeza manual** e devolve DataFrames com colunas padronizadas + `arquivo_origem` + `ref_origem`. Cada fonte tem encoding próprio (Orbe ASCII, Aurora UTF-8, Plano ISO-8859-1, OFX CP1252): **um leitor por fonte, encoding explícito**.

- `normalize.py`: `cnpj()` (só dígitos, `zfill(14)`), `brl()` (`"1.234,56"` → float), `pct()` (aceita `0.0259`, `'2,59%'`; **Orbe vem em pontos percentuais, planilha em fração** → tudo vira o mesmo ponto percentual antes de comparar), `data()` (pt-BR e serial Excel → `AAAA-MM-DD`).
- `orbe.py`: CSV `;` decimal vírgula. `ref_origem = id_transacao`. **Lê todos os arquivos Orbe da pasta** (`01_orbe_*` e `06_orbe_ajustes_*`, mesmo layout) e concatena; `arquivo_origem` é o arquivo **real** da linha (rastro de um estorno tardio aponta para o `06_`). Descoberta por padrão de nome, não por lista fixa; ajuste ausente em outro mês não é erro. Id repetido entre arquivos = erro (hoje não há).
- `taxas.py`: só aba **Taxas vigentes**, cabeçalho achado pelo conteúdo (não pelo nº da linha), ignora rodapé; explode vigências (Bridge) em `(cnpj, ec, vigencia_ini, vigencia_fim, taxas…)`.
- `ponte.py`: `email` stdlib → anexo xlsx → `openpyxl`; cabeçalho achado pelo conteúdo, ignora linhas de total; datas serial Excel. `ref_origem = Nº Operação`.
- `bancos.py`: Aurora CSV (cabeçalho de 7 linhas; `ref_origem = L<nº linha física>`; ignora SALDO ANTERIOR/FINAL e o aviso); Meridiano OFX via regex em `<STMTTRN>` (SGML, não é XML; `ref_origem = FITID`; ignora SALDO).
- `plano.py`: plano de contas (ISO-8859-1), só contas `ACEITA_LANCTO = S`.
- Cadastro mestre `config/lojistas.yaml`: EC → CNPJ, **gerado por regra exata** (EC da planilha) e completado **só com confirmação humana** (nunca fuzzy match automático).



### Camada de back / regras (`src/regras/`)

Python puro, determinístico, testável. Cada função devolve linhas de saída já com a lista de origens.

- `checkout.py` — comissão e divergência por transação (seção 4).
- `remessa.py` — dedupe, spread, comissão 50%, divergência.
- `notas.py` — agrega comissões em NFs.
- `classificacao.py` — regex → conta (REGRA, confiança 1.0); sem match → pendência `HUMANO` (no Extra, antes disso passa por `ia/llm.py`).
- `pendencias.py` — coleta exceções levantadas por todos os módulos (tipo, ref, valor, motivo, quem_decide).
- `core/saida.py` — **contrato comum**: `emitir(arquivo, linha, origens=[(arquivo, ref, valor)])`. Gera `id_saida`, escreve CSV no formato exigido e `rastro.csv`, e **falha se a soma do rastro ≠ valor reportado**.
- `main.py` — CLI: `python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/`. Outubro = mesmo comando com outra pasta.



### IA (`src/ia/llm.py`, nível Extra) — onde atua e onde não atua


| Atua                                                                                                                                            | Não atua                                                         |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Classificar lançamento bancário que nenhuma regra pegou (Claude API, saída JSON com `conta_codigo` restrita às contas analíticas + `confianca`) | Calcular comissão, taxa, spread, NF (aritmética é regra)         |
| Sugerir correspondência de nome → lojista **como pendência**, nunca aplicada sozinha                                                            | Decidir regra de negócio sem pergunta ao financeiro              |
|                                                                                                                                                 | Aceitar sugestão com `confianca < 0.8` → vira pendência `HUMANO` |


Nos níveis Mínimo e Alvo **nenhuma chamada de API é necessária**: o que a regra não pega vira pendência. A solução tem que rodar sem `ANTHROPIC_API_KEY`.

### Camada de front (`app.py`, Streamlit, nível Extra)

Sem lógica de negócio: chama `main.run()` e lê `saida/`. Telas: (1) selecionar pasta/competência e rodar; (2) tabelas das saídas com totais; (3) selecionar `id_saida` → linhas de origem do rastro; (4) fila de pendências com "quem decide". Se o Extra for cortado, a analista usa a CLI e abre os CSVs (declarar no README).

---



## 3. Contrato de saída (definir nos primeiros 30 min — destrava o paralelismo)

Formato fixo do enunciado: `;`, decimal ponto, `AAAA-MM-DD`, CNPJ 14 dígitos, `linha_negocio ∈ {CHECKOUT, REMESSA}`, `banco ∈ {AURORA, MERIDIANO}`, `metodo ∈ {REGRA, IA, HUMANO}`.
Prefixos de `id_saida`: `COM-`, `DIV-`, `NF-`, `LAN-`, `PEN-`. Arredondamento: somar com precisão total, arredondar a 2 casas só na escrita, e o rastro leva os mesmos valores arredondados por linha (para a soma bater exatamente). **[CONFIRMADO]** A Orbe trunca os centavos e a Tarvo arredonda normalmente: usar `Decimal` com `ROUND_HALF_UP`, nunca o `round()` do Python (arredonda para o par) e nunca truncamento.
Teste obrigatório (`tests/test_saida.py`): para cada arquivo, `Σ rastro.valor por id_saida == valor reportado`.

---



## 4. Regras de negócio — o que sabemos × o que assumimos

Etiquetas: **[SABEMOS]** vem dos arquivos ou do e-mail da Ponte · **[CONFIRMADO]** respondido pela Helena (financeiro da Tarvo) · **[PARCIAL]** respondido em parte; o resto segue como assumido · **[ASSUMIDO]** sem resposta; vai para `HIPOTESES.md` e vira pergunta (seção 5). Implementar tudo como parâmetro em `config/regras.yaml` para trocar sem mexer no código.

### Checkout

- **[SABEMOS]** Faixas: Débito, Crédito à vista, 2–6x, 7–12x, Pix; Antecipação 2,10%. Bridge muda crédito à vista de 2,59% para 2,19% a partir de 15/09.
- **[CONFIRMADO]** Comissão Tarvo = `valor_bruto × taxa_contratada`, a taxa inteira, **sem desconto do custo da Orbe** e sem usar o `valor_taxa` aplicado.
- **[CONFIRMADO]** Divergência = `valor_bruto × (aplicada − contratada)`, comparando **taxas**, não o valor truncado: a Orbe trunca os centavos, a Tarvo arredonda normalmente, e diferença de centavo por truncamento **não é** divergência.
- **[ASSUMIDO]** Limiar de divergência `|diferença| ≥ 0,01`. A Helena não falou de limite (pergunta 13 segue aberta); como a comparação é entre taxas, o limiar é só uma guarda contra ruído e fica em `regras.yaml`.
- **[PARCIAL]** Vigência: para **estorno** vale a taxa da data da venda original (confirmado). Para venda normal, **[ASSUMIDO]** a `data_movimento`; é coerente com o tratamento que a Helena deu a Rota, Casa do Estudante e Atlas, sempre por data de início da condição.
- **[CONFIRMADO]** ESTORNO devolve a taxa ao lojista e **abate a comissão do mês em que ocorre**: venda de agosto estornada em setembro entra em setembro, agosto **não é reaberto**. Taxa vigente na data da venda original (`id_referencia` → `data_venda_original`).
- **[CONFIRMADO]** ANTECIPACAO entra na comissão de checkout, **na mesma nota** do MDR. REVERSAO ANTECIPACAO anula **só a taxa da antecipação que ela reverte** (via `id_referencia`). As 44 linhas sem modalidade/parcelas/bandeira são vazio estrutural (fato dos dados, não comentado pela Helena).
- **Exceções → pendência:** EC sem contrato vigente (Atlas Idiomas `1076801732` só na aba 2025; `HORIZONTE INTERCAMBIO 1043300981` — Horizonte Viagens ou Novo Horizonte? **não adivinhar**); Kiwi (`EC pendente` na planilha); Globo Trotter (inativo). **[CONFIRMADO]** A Atlas **não é faturada** até o Comercial confirmar a taxa: pendência com `quem_decide = Comercial`.



### Remessa

- **[SABEMOS]** Tarvo recebe **50% do spread realizado** (e-mail da Ponte). Spread contratado por lojista; em branco/`padrão` = padrão. `APROVADO C/ RESSALVA` segue para liquidação (e-mail).
- **[CONFIRMADO]** Comissão = 50% do `Spread R$` **realizado** (como no e-mail da Ponte), não do `Spread Estimado D-1`.
- **[CONFIRMADO]** Operação repetida (mesmo `Nº Operação`, que é único) conta **uma vez** no fechamento e entra na **lista para a Ponte corrigir o relatório**. **[ASSUMIDO]** A regra de "mesmos campos" (mesmo CNPJ/valor/moeda/data com `Nº Operação` diferente) não foi comentada: só **sinalizar** como pendência, sem descartar a linha da comissão.
- **[CONFIRMADO]** Spread negativo fica **fora da comissão e fora da nota** e é **pendência de contestação, não divergência**, porque a trava de 2 horas do contrato foi excedida. A contestação ainda não foi aberta: considerar que estamos dentro do prazo de 5 dias úteis (o fechamento é esta semana). `tipo = CONTESTACAO`, `quem_decide = Financeiro`.
- **[CONFIRMADO]** Divergência de remessa é o **valor cheio**, não a metade: quem pagou a mais foi o lojista, e é o total que o financeiro contesta com a Ponte. Fórmula em reais: `Valor ME × PTAX Ref. × (spread aplicado − spread contratado)`.
- **[DECIDIDO PELO TIME]** A Helena orientou escolher um critério para a diferença de ~R$ 0,03 entre calcular pelo percentual (`Spread %`, só 5 casas) e pelo valor do relatório (`Spread R$`). Critério: `diferenca_brl = Spread R$ − Valor ME × PTAX Ref. × spread contratado` (usa o realizado do relatório, a mesma base da comissão, então a soma fecha com o rastro). Uma operação só entra em divergências se `Spread %` diferir do contratado além da precisão do relatório (5 casas), para a diferença de arredondamento não virar alarme falso. Registrar o critério em `HIPOTESES.md`.
- **[ASSUMIDO]** Spread **padrão** (em branco ou `padrão`) segue sem resposta (pergunta 4): enquanto não houver, a divergência desses lojistas não é calculada (a comissão não depende do spread contratado) e o fato é registrado em `HIPOTESES.md`.
- Conferir `Total de operações: 233` e `Spread total R$: 78.073,59` do rodapé contra as linhas (só como checagem; o rodapé **inclui** repetida e negativos).
- Lojista da Ponte identificado **por CNPJ normalizado**, nunca pelo nome truncado.



### Notas fiscais

- **[CONFIRMADO]** Checkout: **1 NF por lojista por mês**, valor = comissão pela taxa contratada (MDR + antecipação na mesma nota − estornos que abatem).
- **[ASSUMIDO]** Tomador da NF de checkout = o próprio lojista (CNPJ do cadastro). A Helena não disse quem é o tomador: é a única pergunta nova (16).
- **[CONFIRMADO]** Saldo zero ou negativo **não emite nota** e vira pendência para o financeiro (`quem_decide = Financeiro`). A Atlas não é faturada até o Comercial confirmar a taxa.
- **[CONFIRMADO]** Remessa: **uma única NF**, tomadora **Ponte Câmbio**, pelo **total da participação da Tarvo no mês** (50% do spread válido), **sem nota por lojista**.
- **[SABEMOS]** O CNPJ da Ponte (75.374.179/0001-46) e a condição de que o repasse depende da NF de intermediação vêm do **e-mail da Ponte**, não da Helena.



### Lançamentos bancários (regra → conta)

Alvo: tudo por regra. Ordem das regras importa: **padrão específico antes do genérico** (`PIX ENVIADO CONTABILIDADE` antes de `PIX ENVIADO <lojista>`).


| Padrão                                                                                                                                | Conta                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `TED RECEBIDA … ORBE` (Aurora, 21)                                                                                                    | 1.1.03.001 Recebíveis Orbe                                            |
| `TRANSF ENTRE CONTAS` (Aurora, 4) e `TED RECEBIDA TARVO … MESMA TITULARIDADE` (Meridiano, 3)                                          | 1.1.09.001                                                            |
| `PIX ENVIADO CONTABILIDADE EXATA`                                                                                                     | 4.2.06 — **antes** da regra abaixo                                    |
| `PIX ENVIADO <lojista>` (Aurora, 44)                                                                                                  | 2.1.01.001 Repasses a lojistas                                        |
| `PIX RECEB <lojista>` (Meridiano, 64) e `TED ENVIADA PONTE CAMBIO … LIQ OPERACOES` (21)                                               | 2.1.02.001 Recursos p/ remessas **[ASSUMIDO p/ a TED]**               |
| `TED RECEB PONTE CAMBIO … REPASSE COMISSAO 08/2026`                                                                                   | 1.1.03.002 **[ASSUMIDO: competência de agosto]**                      |
| `DEVOLUCAO PIX`                                                                                                                       | 2.1.01.002                                                            |
| `TAR …` / `TARIFA MANUTENCAO` / `TARIFA PACOTE CAMBIO`                                                                                | 4.2.01                                                                |
| `CONDOMINIO` 4.2.02 · `AMAZON WEB SERVICES` 4.2.03 · `GOOGLE WORKSPACE` 4.2.04 · `SEGURO EMPRESARIAL` 4.2.05 · `CONTABILIDADE` 4.2.06 |                                                                       |
| `APLICACAO` / `RESGATE AUTOMATICO CDB DI`                                                                                             | 1.1.02.001                                                            |
| `RENDIMENTO APLIC AUTOMATICA`                                                                                                         | 3.2.01                                                                |
| `IOF S/ OPERACAO CREDITO`                                                                                                             | 4.3.01                                                                |
| `DARF 8109 PIS` / `2172 COFINS` / `0561 IRRF` / `ISS`                                                                                 | 2.1.03.001 / .002 / .004 / .003                                       |
| `PAGTO SALARIOS` / `GPS INSS` / `GRF FGTS`                                                                                            | 2.1.04.001 / .002 / .003 **[ASSUMIDO: baixa de provisão de 08/2026]** |
| `PIX RECEBIDO <CNPJ desconhecido>` (R$ 7.350, 16/09)                                                                                  | 1.1.09.002 + pendência                                                |
| Resto                                                                                                                                 | Alvo: pendência `HUMANO` · Extra: LLM → se confiança < 0.8, pendência |


Conferência: as contagens por padrão devem bater com `DICIONARIO_DADOS.md` §5 (Aurora 84, Meridiano 100).

---



## 5. Perguntas ao financeiro e status das respostas

Prefixar com o nome do time. Registrar pergunta, horário e resposta em `HIPOTESES.md` na hora. Respostas dadas pela Helena (financeiro da Tarvo). Status: **[RESPONDIDA]**, **[PARCIAL]** ou **[ABERTA]**. Lote 1 saiu às 9h30, quando o canal abriu.

**Lote 1 (bloqueiam números do Mínimo e do Alvo):**

1. A comissão do lojista é calculada pela taxa **contratada** na planilha ou pela taxa que a Orbe aplicou? Quando a aplicada é maior, a diferença é devolvida ao lojista?
  - **[RESPONDIDA]** Pela taxa **contratada**, a taxa inteira, sem desconto do custo da Orbe. Sobre devolver a diferença ao lojista não há resposta explícita; o plano só **reporta** a divergência em `divergencias_taxa.csv`.
2. Em estorno de venda de agosto lançado em setembro, a Tarvo devolve o MDR? Com qual taxa (da venda original ou vigente)?
  - **[RESPONDIDA]** Devolve a taxa ao lojista e abate a comissão de **setembro** (agosto não é reaberto). Vale a taxa vigente na data da **venda original**.
3. Antecipação e reversão de antecipação entram na comissão de checkout e na mesma NF do MDR?
  - **[RESPONDIDA]** A antecipação entra na **mesma nota**; a reversão anula só a taxa da antecipação que reverte.
4. Qual é o spread **padrão** de remessa (para em branco e "padrão")?
  - **[ABERTA]** Sem resposta. Efeito: só a divergência desses lojistas fica sem cálculo (seção 4, Remessa).
5. A NF de remessa é emitida para a Ponte Câmbio (sobre os 50%) ou para cada lojista? E a de checkout é uma por lojista no mês?
  - **[RESPONDIDA]** Remessa: **uma nota só**, tomadora Ponte Câmbio, pelo total da participação da Tarvo no mês. Checkout: **uma por lojista por mês**. O tomador do checkout não foi dito (pergunta 16).
6. Comissão de remessa usa `Spread R$` realizado ou `Spread Estimado D-1`?
  - **[RESPONDIDA]** 50% do `Spread R$` **realizado**.

**Lote 2 (exceções):**
7. `HORIZONTE INTERCAMBIO` (EC 1043300981) é a Horizonte Viagens ou a Novo Horizonte? Qual EC é da Kiwi?

- **[ABERTA]** Segue como pendência (não adivinhar).

1. Atlas Idiomas transaciona em setembro mas só está na tabela de 2025. Qual taxa vale? Quem decide?
  - **[PARCIAL]** Quem decide: o **Comercial**, e a Atlas **não é faturada** até ele confirmar a taxa. A taxa que vale segue em aberto.
2. Operação repetida e spread negativo da Ponte: qual o critério de aceitar? Quem contesta?
  - **[RESPONDIDA]** Repetida: conta uma vez e vai para a lista de correção da Ponte. Negativo: fora da comissão e da nota, pendência de **contestação** (trava de 2 horas excedida), não divergência. Considerar dentro do prazo de 5 dias úteis. O critério de "mesmos campos" não foi comentado.
3. "APROVADO C/ RESSALVA" entra na comissão normalmente? (o e-mail diz que segue para liquidação; confirmar para a comissão)
  - **[ABERTA]** Seguir o e-mail (entra) como **[ASSUMIDO]**.
4. A vigência de taxa vale pela data da venda ou da liquidação?
  - **[PARCIAL]** Estorno: data da venda original. Venda normal: não afirmado; seguir a `data_movimento` como **[ASSUMIDO]**.
5. Pagamento de salários/INSS/FGTS/impostos de 08 é baixa de provisão (passivo) ou despesa direta?
  - **[ABERTA]** Parâmetro em `regras.yaml`, padrão baixa de provisão.
6. Divergência abaixo de quanto vocês ignoram (arredondamento)?
  - **[PARCIAL]** Lógica confirmada (comparar taxas; truncamento da Orbe não é divergência). O limiar de R$ 0,01 não foi mencionado: segue **[ASSUMIDO]**.

**Nova pergunta (gerada pelas respostas; única que justifica voltar ao financeiro):**
16. O tomador da NF de checkout é o próprio lojista (CNPJ do cadastro mestre)?

**Lote 3 (só se sobrar tempo; não bloqueia nada):**
14. O repasse da Ponte de 08/2026 (R$ 61.884,12, em 04/09) baixa recebível ou é receita do mês?
15. A TED de R$ 300 mil de 30/09 (Aurora → Meridiano) sem contrapartida no Meridiano é só timing de fim de mês? Quem acompanha?

**Fora do personagem (#hackathon-duvidas):** numeração do `ref_origem` do Aurora — a primeira transação está na linha física 9, mas o enunciado exemplifica `L10, L11…`. Perguntar **antes** de gerar `lancamentos_classificados`.

---



## 6. Time de 2, níveis de entrega e cronograma



### 6.1 Divisão do time


| Pessoa                               | Dono de                                                                                                                                               | Dono da comunicação                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **A — Checkout & Fiscal**            | `ingest/orbe`, `ingest/taxas`, cadastro mestre, `regras/checkout`, `regras/notas`, `core/normalize`                                                   | Checkpoint 1, README, números do pitch                                       |
| **B — Remessa, Bancos & Plataforma** | `core/saida` + testes, `main.py`, `regras/pendencias`, `ingest/ponte`, `regras/remessa`, `ingest/bancos` + `regras/classificacao`, Extra (LLM, front) | Perguntas ao financeiro, `HIPOTESES.md`, Checkpoint 2, slides, `MOMENTOS.md` |


Regras de colaboração:

- Cada um abre **sua própria sessão de Claude Code** e salva o transcript desde o primeiro prompt.
- **Revisão cruzada obrigatória** em cada gate: quem não escreveu o código recalcula linhas à mão contra o arquivo de origem.
- Travado > 20 min: avisar o outro. No gate, os dois trabalham no que está vermelho, não cada um na sua frente.
- Ninguém altera módulo do outro sem avisar; o contrato é `core/saida.py` e as colunas de `core/normalize.py`.



### 6.2 Regras do jogo (valem para os três níveis)

**Definição de pronto geral** — um item só conta como pronto se:

1. está em `main`, com `pytest` verde;
2. `python -m src.main …` regenera `saida/` do zero, a partir dos arquivos **como vêm** (nenhuma edição manual de entrada);
3. todo número tem linha em `rastro.csv` e a soma bate (teste automático, não conferência visual);
4. cada premissa usada está em `HIPOTESES.md` com pergunta, horário e resposta (ou "assumido, sem resposta");
5. outra pessoa recalculou à mão ao menos 3 linhas da saída contra a origem;
6. nenhum CNPJ, EC, nome de lojista ou data de competência está escrito no código (só em `config/` e `tests/`).

**Gates:** cada nível termina com um gate de go/no-go. Gate vermelho no horário → o time **para** o nível seguinte e corrige. Mínimo certo > extra com número que não fecha.

---



### 6.3 Fase 0 — Fundação (9h30–10h45 · 1h15 · os dois)


| A                                                                           | B                                                                                                                        |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Esqueleto do repo + `requirements.txt`                                      | **9h30:** envia lote 1 no #tarvo-financeiro e a dúvida do `ref_origem` Aurora no #hackathon-duvidas; abre `HIPOTESES.md` |
| `core/normalize.py` (`cnpj`, `brl`, `pct`, `data`) com testes               | `core/saida.py` (contrato da seção 3) + `tests/test_saida.py`                                                            |
| Lê planilha de taxas e Orbe, confirma as regras de checkout contra os dados | Lê e-mail da Ponte e extratos, confirma as regras de remessa/bancos, prepara lote 2                                      |


**Pronto quando:** contrato de saída e `normalize` em `main`; lote 1 enviado; os dois com sessão de IA aberta e salva.
**10h45 — Checkpoint 1** (A posta; limite 11h): causa raiz (seção 1), o que vamos atacar (nível Alvo, com o Mínimo como piso), hipóteses principais, fora do escopo (seção 9).

---



### 6.4 Nível MÍNIMO — comissão de checkout por lojista, com rastro

**Janela:** 10h45–12h30 · **Gate M: 12h30**

**Escopo**


| A                                                                                                          | B                                                                                             |
| ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `ingest/orbe.py`, `ingest/taxas.py` (vigências, `%` em texto, CNPJ numérico), cadastro mestre por EC exato | `main.py` (CLI) + `regras/pendencias.py` (API simples para qualquer módulo registrar exceção) |
| `regras/checkout.py` **só** `VENDA` (1.841 linhas: 1.840 do `01_` + 1 do `06_`) → `comissoes_por_lojista` CHECKOUT + `rastro`           | Integra A em `main`; revisão cruzada do Mínimo às 12h15                                       |
| EC sem contrato → `pendencias` (não entra na comissão)                                                     | Adianta base do Alvo **fora do caminho crítico**: `ingest/ponte.py` e `ingest/bancos.py`      |


**Critérios de aceite**

- [ ] **M1.** Um comando roda do zero e gera `saida/comissoes_por_lojista.csv`, `rastro.csv` e `pendencias.csv` sem erro e sem editar arquivo de entrada.
- [ ] **M2.** `comissoes_por_lojista.csv`: colunas obrigatórias, `;`, decimal ponto, CNPJ com 14 dígitos, `linha_negocio = CHECKOUT`, 1 linha por lojista, ids `COM-…`.
- [ ] **M3.** Para cada `id_saida`: Σ `rastro.valor` = `comissao_brl` (centavo exato). Todo `ref_origem` do rastro existe como `id_transacao` na Orbe e `arquivo_origem` aponta para o arquivo de origem.
- [ ] **M4.** **Conservação:** das 1.957 linhas da Orbe (1.943 do `01_` + 14 do `06_ajustes_tardios`), nenhuma some. As 1.841 `VENDA` = tratadas + em pendência; as 116 linhas não-`VENDA` (69 estornos, 38 antecipações, 9 reversões) são contadas no log da execução como "fora do escopo deste nível". Não aparecem em `pendencias.csv` (seriam alarme falso).
- [ ] **M5.** Lojista casado **só por EC exato** da planilha. Zero fuzzy match. Atlas (`quem_decide = Comercial`), Horizonte/Novo Horizonte, Kiwi e Globo Trotter vão para `pendencias.csv` com `tipo`, `motivo` e `quem_decide` preenchidos.
- [ ] **M6.** Testes unitários: Bridge com venda em 14/09 usa 2,59% e em 15/09 usa 2,19%; `'2,59%'` e `0.0259` dão o mesmo valor; CNPJ de 13 dígitos vira 14; faixa certa por modalidade/parcelas (débito, à vista, 2–6x, 7–12x, Pix); arredondamento `ROUND_HALF_UP` (um valor com `.xx5` arredonda para cima, não para o par).
- [ ] **M7.** Revisão cruzada: 5 transações recalculadas à mão (`bruto × taxa contratada`) batem com o rastro; resultado anotado em `HIPOTESES.md`.
- [ ] **M8.** A regra de comissão (taxa contratada, sem desconto do custo da Orbe) está em `config/regras.yaml` e registrada em `HIPOTESES.md` como **[CONFIRMADO]** (pergunta 1, Helena).

**Definição de pronto (Mínimo)**

- Critérios M1–M8 marcados; definição de pronto geral (6.2) cumprida.
- `saida/` do Mínimo **commitada** e tag `minimo` criada: se tudo mais falhar, o repositório já contém uma entrega válida.
- Checkpoint 1 postado; transcripts de A e B sendo salvos.

**Gate M (12h30):** verde → segue para o Alvo. Vermelho → os dois corrigem o Mínimo; nada do Alvo é mesclado em `main` até ficar verde.

---



### 6.5 Nível ALVO — duas linhas, divergências, notas e lançamentos

**Janela:** 13h15–15h00 (construção) + 15h00–15h30 (validação cruzada) · **Checkpoint 2 postado até 15h15** (limite do enunciado: 15h30) · **Gate A: 15h30**

**Escopo**


| A — Checkout & Fiscal                                                                                  | B — Remessa & Bancos                                                                                      |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `checkout.py` completo: `ESTORNO` (taxa da venda original), `ANTECIPACAO`, `REVERSAO`, vigência Bridge | `remessa.py`: dedupe, spread negativo, comissão 50%, checagem do rodapé → `comissoes_por_lojista` REMESSA |
| `divergencias_taxa` CHECKOUT (inclui as 5 taxas fora da planilha)                                      | `divergencias_taxa` REMESSA                                                                               |
| `regras/notas.py` → `notas_a_emitir` (checkout por lojista + remessa para a Ponte)                     | `bancos.py` + `classificacao.py` (tabela da seção 4) → `lancamentos_classificados`                        |
| Aplica em `regras.yaml` as respostas já recebidas (seção 5) e as que ainda chegarem                    | `pendencias.csv` consolidado (todos os módulos); aplica as respostas pendentes do lote 2                  |


**Critérios de aceite**

*Comissões*

- [ ] **A1.** Checkout: comissão = MDR das vendas − estornos + antecipação − reversões (só a taxa da antecipação revertida), por lojista; o rastro lista cada `id_transacao` envolvido (incluindo estornos e reversões com valor negativo). Reconciliação das 1.957 linhas da Orbe (`01_` + `06_`): tratadas + em pendência = 1.957, com a contagem por arquivo no log.
- [ ] **A2.** Estorno usa a taxa vigente na data da venda original (inclusive de agosto) e abate a comissão de **setembro** (a de agosto não é reaberta); reversão de antecipação anula só a taxa da antecipação referenciada em `id_referencia`. Estorno cuja venda original não está no arquivo é resolvido por `data_venda_original` + EC, nunca ignorado. Teste: estorno em setembro de venda de agosto reduz a comissão de setembro.
- [ ] **A3.** Remessa: as 233 linhas da Ponte são lidas; `PC-0926-0162` conta **uma vez**; o par com mesmo CNPJ/valor/moeda/data é sinalizado; os 4 spreads negativos ficam fora da comissão **e da nota**; cada um deles está em `pendencias.csv` com `tipo = CONTESTACAO` (não em `divergencias_taxa.csv`) e motivo "trava de 2 horas excedida"; a repetida está na lista de correção para a Ponte.
- [ ] **A4.** Remessa: comissão = 50% × Σ `Spread R$` válido por lojista (casado por **CNPJ normalizado**, 14 clientes distintos). Reconciliação documentada: `78.073,59 (rodapé) − repetida − negativos = base da comissão`, com cada parcela listada. Rodapé (233 / 78.073,59) conferido por teste.

*Divergências*

- [ ] **A5.** `divergencias_taxa.csv`: 1 linha por transação/operação com `|diferenca_brl| ≥ limiar`; `taxa_contratada_pct` e `taxa_aplicada_pct` **na mesma escala** (pontos percentuais); sinal de `diferenca_brl` documentado (positivo = lojista pagou a mais); `ref_origem` = `id_transacao` ou `Nº Operação`. Remessa: `diferenca_brl` é o **valor cheio** (não a metade), pelo critério `Spread R$ − Valor ME × PTAX × spread contratado` (seção 4); teste com uma operação em que o cálculo pelo percentual e pelo valor do relatório diferem em ~R$ 0,03 e que **não** vira divergência quando o `Spread %` bate com o contratado.
- [ ] **A6.** **Zero alarme falso por arredondamento:** teste com linha cuja taxa aplicada = contratada e `valor_taxa` truncado em R$ 0,01 → não aparece em divergências. Cada uma das 5 taxas fora da aba vigente (0,99; 1,99; 3,99; 4,09; 4,49) termina ou como divergência ou como pendência de lojista sem contrato; nenhuma é silenciada.

*Notas fiscais*

- [ ] **A7.** `notas_a_emitir.csv`: 1 NF CHECKOUT por lojista por mês (tomador = lojista, **[ASSUMIDO]** até a pergunta 16; antecipação na mesma nota, estorno abatendo) + **uma única** NF REMESSA para a Ponte (CNPJ 75374179000146, do e-mail), sem nota por lojista; `discriminacao` preenchida (tipo de comissão, competência, nº de transações).
- [ ] **A8.** Σ NF CHECKOUT = Σ comissões CHECKOUT, exceto lojistas sem NF, e a NF REMESSA = Σ comissões REMESSA (teste automático). Lojista com comissão ≤ 0 **não gera NF** e aparece em `pendencias.csv` (`quem_decide = Financeiro`); a **Atlas não gera NF** (`quem_decide = Comercial`) até a taxa ser confirmada. O rastro de cada NF aponta para as mesmas linhas de origem da comissão.

*Lançamentos*

- [ ] **A9.** 84 lançamentos Aurora + 100 Meridiano = **184** linhas, cada uma uma única vez; SALDO ANTERIOR, SALDO FINAL e aviso do Aurora não aparecem. `ref_origem` Aurora segue a convenção respondida em #hackathon-duvidas (registrada em `HIPOTESES.md`); Meridiano = `FITID`.
- [ ] **A10.** `conta_codigo` de toda linha ∈ contas com `ACEITA_LANCTO = S` do plano (teste). Contagem por padrão confere com `DICIONARIO_DADOS.md` §5.
- [ ] **A11.** Casos-armadilha cobertos por teste: `PIX ENVIADO CONTABILIDADE EXATA` → 4.2.06 (não 2.1.01.001); `DEVOLUCAO PIX` → 2.1.01.002; `PIX RECEBIDO … SEM IDENTIFICACAO` (R$ 7.350) → 1.1.09.002 **e** pendência.
- [ ] **A12.** Linha que nenhuma regra pegou: `metodo = HUMANO`, `confianca` baixa, **pendência** correspondente. Linha por regra: `metodo = REGRA`, `confianca = 1`.
- [ ] **A13.** Salários/INSS/FGTS/impostos de 08 são decididos por parâmetro em `regras.yaml` (provisão × despesa), marcados **[ASSUMIDO]** até haver resposta.

*Pendências, rastro e formato*

- [ ] **A14.** Os 6 arquivos existem em `saida/` com colunas obrigatórias e formato correto (`;`, decimal ponto, `AAAA-MM-DD`, CNPJ 14 dígitos, enums válidos); `pytest` valida colunas e enums.
- [ ] **A15.** `test_saida`: para **todos** os arquivos que carregam valor, Σ `rastro.valor` por `id_saida` = valor reportado. Toda pendência tem `tipo`, `motivo` e `quem_decide` não vazios.
- [ ] **A16.** Determinismo: duas execuções seguidas geram `saida/` idêntica (hash dos arquivos).
- [ ] **A17.** Revisão cruzada: A recalcula 3 linhas de cada saída de B e B recalcula 3 de cada saída de A; erros achados e corrigidos são anotados para `MOMENTOS`.

**Definição de pronto (Alvo)**

- Critérios A1–A17 marcados; definição de pronto geral (6.2) cumprida.
- Respostas do financeiro aplicadas; toda premissa ainda sem resposta está em `HIPOTESES.md` marcada **[ASSUMIDO]** e parametrizada.
- `saida/` regenerada de um run limpo, commitada, tag `alvo`.
- Checkpoint 2 postado com o que funciona, números preliminares e o que mudou no plano.
- Totais do pitch calculados a partir de `saida/` (não de memória): R$ em divergência, devoluções a lojistas, receita de remessa que não seria faturada sem NF, nº de pendências por `quem_decide`.

**Gate A (15h30):** verde → libera o Extra (apenas B) e a documentação (A). Vermelho → os dois fecham o Alvo; **o Extra é cancelado** e os docs/pitch começam com o que estiver verde.

---



### 6.6 Nível EXTRA — rastro completo, pendências explicadas, roda em outubro

**Janela:** 15h30–16h30 · **corte duro às 16h30**: o que não estiver pronto é desligado/removido, não commitado pela metade.
Executa **B**, enquanto **A** faz a documentação (6.7). Ordem de prioridade (parar onde o tempo acabar; cada item é independente):


| #   | Item                                     | Por quê                                                   |
| --- | ---------------------------------------- | --------------------------------------------------------- |
| E1  | Rastro completo e conferência automática | É o critério de avaliação do enunciado para "Extra"       |
| E2  | Pendências explicadas                    | Idem; é o que o CFO lê                                    |
| E3  | Roda em outubro sem retrabalho           | Idem; é a resposta à pergunta "como a analista usa"       |
| E4  | Fallback de IA na classificação bancária | Dá o "onde a IA atua" ao pitch                            |
| E5  | Front Streamlit fino                     | Conveniência; **primeiro a ser cortado** (não é avaliado) |


**Critérios de aceite**

- [ ] **E1.** *Rastro completo:* `DIV`, `LAN` e `PEN` têm rastro 1:1 com a linha de origem; `NF` e `COM` apontam para todas as transações/operações; a execução imprime um relatório de conferência (Σ por arquivo × Σ rastro × totais de origem) e **falha o comando** se algo não fechar.
- [ ] **E2.** *Pendências explicadas:* `motivo` em linguagem de negócio (frase que o financeiro entende, sem jargão de código); `quem_decide` de uma lista fechada (Financeiro, Comercial, Ponte, Contador…); coluna extra `sugestao` com o próximo passo; cobre no mínimo os casos de `DICIONARIO_DADOS.md` §6 (Atlas, Horizonte/Kiwi, repetida e negativos da Ponte, PIX sem identificação, TED de R$ 300 mil sem contrapartida).
- [ ] **E3.** *Outubro sem retrabalho:* (a) `--entrada` e `--competencia` são parâmetros e nenhuma data/EC/CNPJ está no código (verificação por `grep`); (b) toda regra mutável está em `config/regras.yaml` / `lojistas.yaml`; (c) o cabeçalho de cada arquivo é localizado pelo conteúdo; (d) um teste roda o pipeline numa cópia do data pack com um lojista removido e uma data deslocada, sem alterar código; (e) o `README.md` leva um clone limpo a gerar `saida/` em < 5 comandos; (f) lojista novo sem cadastro vira pendência, nunca erro.
- [ ] **E4.** *IA fallback:* `llm.py` devolve JSON `{conta_codigo, confianca}` com `conta_codigo` restrita às analíticas; `confianca < 0.8` vira pendência `HUMANO`; sem `ANTHROPIC_API_KEY` o pipeline continua e as linhas viram pendência; toda chamada é registrada (entrada, saída) e as correções ficam para `MOMENTOS`; só roda sobre linhas que nenhuma regra pegou (nunca sobre as 184 já classificadas por regra, para não mudar número do Alvo).
- [ ] **E5.** *Front:* roda, mostra as saídas, `id_saida` → linhas do rastro, fila de pendências; **nenhuma regra de negócio** em `app.py`.

**Definição de pronto (Extra)**

- Cada item entregue cumpre seus critérios **e** não altera nenhum número do Alvo (comparar `saida/` antes × depois: só linhas esperadas mudam).
- Definição de pronto geral (6.2) cumprida; tag `extra`.
- Itens não entregues estão listados em "limitações conhecidas" do `README.md` e na resposta "o que faria com mais um mês" do pitch.

**Gate E (16h30):** corte duro. Tudo que não passou nos critérios é revertido; `main` volta para a última tag verde.

---



### 6.7 Entregáveis transversais (não são nível; todos obrigatórios)


| Entregável                   | Dono                                     | Pronto quando                                                                                                             |
| ---------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `HIPOTESES.md`               | B (cada um registra na hora)             | Toda premissa com **[SABEMOS]/[ASSUMIDO]**; perguntas com horário e resposta; premissas sem resposta explícitas           |
| `PROMPTS/A/`, `PROMPTS/B/`   | cada um                                  | Transcript exportado sem edição (só chaves removidas)                                                                     |
| `PROMPTS/MOMENTOS.md`        | B (com A)                                | 2–4 momentos; ≥ 1 em que a IA errou; cada um com: o que pedimos, o que voltou, o que fizemos                              |
| `README.md`                  | A                                        | Instalar do zero, `ANTHROPIC_API_KEY` (opcional), como rodar a competência, limitações conhecidas; testado em clone limpo |
| Pitch (7 itens do enunciado) | A (itens 1, 3, 4) e B (itens 2, 5, 6, 7) | Linguagem do CFO; números vêm de `saida/`; enviado em #hackathon-entregas até as 19h                                      |
| Checkpoints 1 e 2            | A e B                                    | Postados no thread do time antes de 11h e 15h30                                                                           |


---



### 6.8 Cronograma consolidado


| Horário     | Fase                         | A                                                                      | B                                             | Gate / marco                               |
| ----------- | ---------------------------- | ---------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------ |
| 9h30–10h45  | **0 · Fundação**             | repo, `normalize`, leitura da planilha/Orbe                            | lote 1, `saida`, testes, leitura Ponte/bancos | **CP1 postado (limite 11h)**               |
| 10h45–12h30 | **1 · Mínimo**               | Orbe + taxas + checkout VENDA                                          | `main`, `pendencias`, base ponte/bancos       | **Gate M 12h30**, tag `minimo`             |
| 12h30–13h15 | Pausa                        |                                                                        |                                               |                                            |
| 13h15–15h00 | **2 · Alvo**                 | checkout completo, divergências, NFs                                   | remessa, divergências, bancos                 | CP2 postado até 15h15                      |
| 15h00–15h30 | **3 · Validação cruzada**    | revisa B                                                               | revisa A                                      | **Gate A 15h30**, tag `alvo`               |
| 15h30–16h30 | **4 · Extra + docs**         | README, `HIPOTESES`, totais do pitch                                   | E1 → E5                                       | **Gate E 16h30** (corte duro), tag `extra` |
| 16h30–17h30 | **5 · Pitch e congelamento** | slides (itens 1, 3, 4)                                                 | slides (itens 2, 5, 6, 7), `MOMENTOS`         | exportar transcripts                       |
| 17h30–18h30 | Folga                        | clone limpo, `saida/` final, commit, push, link em #hackathon-entregas | dado novo / respostas tardias                 | **Entrega 18h30**; pitch até 19h           |


- Financeiro atende até 17h30: o lote 3 e as últimas dúvidas saem até 15h30, com margem para aplicar a resposta.
- Atenção ao **#hackathon-avisos**: dado novo → rodar o pipeline de novo, **não remendar a saída**.
- Se o Gate A estiver vermelho às 15h30, não existe Fase 4 de Extra.



### 6.9 Riscos específicos do time de 2


| Risco                                                                           | Mitigação                                                                                                                                 |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Duas pessoas, sem sobra: um travamento para metade do time                      | Regra dos 20 min; gate é trabalho conjunto                                                                                                |
| Caminho crítico do Mínimo depende de `core/saida.py` (B) e de `checkout.py` (A) | Contrato definido na Fase 0; A desenvolve já contra a assinatura de `emitir()`; B entrega `saida` antes das 10h45                         |
| A carga de B no Alvo (remessa + bancos) é maior                                 | `ingest/ponte` e `ingest/bancos` já adiantados na Fase 1; A termina o checkout e puxa `classificacao` se B estiver atrasado às 14h15      |
| Cortar escopo sem perder pontos                                                 | Streamlit e LLM saem do Alvo (não pesam na correção dos números, que vale 25%); a IA continua evidenciada pelo histórico de prompts (20%) |
| Extra consumir o tempo de docs/pitch                                            | Docs e pitch rodam em paralelo ao Extra com dono definido; corte duro às 16h30                                                            |


---



## 7. Histórico de uso de IA (20% da nota)

- Uma sessão de Claude Code por pessoa (A e B), salva desde o início. Neste arquivo começa o histórico de planejamento.
- Padrão de prompt: **dar a regra para a IA, não pedir a regra.** Ex.: "implemente a comissão usando a taxa contratada da faixa por nº de parcelas; venda de 15/09 em diante da Bridge usa 2,19%".
- Sempre verificar: depois de cada módulo, pedir para a IA mostrar 3 linhas de origem → saída e conferir à mão.
- Anotar em `PROMPTS/rascunho_momentos.md` **na hora** (não reconstruir no fim): o que pedimos, o que voltou, o que corrigimos. Candidatos prováveis: IA propondo fuzzy match de nomes (rejeitar), IA lendo a aba "ANTIGO 2025", IA somando o spread estimado no lugar do realizado, IA classificando `PIX ENVIADO CONTABILIDADE` como repasse a lojista, IA tratando diferença de R$ 0,01 como divergência.

---



## 8. Estrutura do repositório

```
README.md  HIPOTESES.md  PLANO.md  DICIONARIO_DADOS.md
PROMPTS/  (A/, B/, MOMENTOS.md)
config/   regras.yaml  lojistas.yaml
src/      main.py  app.py [Extra]
          core/   normalize.py  saida.py
          ingest/ orbe.py taxas.py ponte.py bancos.py plano.py
          regras/ checkout.py remessa.py notas.py classificacao.py pendencias.py
          ia/     llm.py [Extra]
tests/    test_normalize.py  test_saida.py  test_checkout.py
          test_remessa.py  test_lancamentos.py  test_formato.py
saida/    (6 CSVs gerados)
context/  tarvo_data_pack/ (entrada, intocada)
```

Stack: Python 3.11, pandas, openpyxl, pytest · Extra: anthropic, streamlit.

## 9. Fora do escopo (declarar no Checkpoint 1)

Conciliação TED Orbe × líquido das transações, emissão real de NF, integração com o ERP Fênix, login/multiusuário, multi-competência, visual caprichado. Streamlit e fallback de IA só entram se o Gate A fechar no horário.