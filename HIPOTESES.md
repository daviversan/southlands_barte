# Hipóteses, perguntas ao financeiro e verificações

Etiquetas: **[SABEMOS]** vem dos arquivos ou do e-mail da Ponte · **[CONFIRMADO]** respondido pela Helena (financeiro) · **[PARCIAL]** respondido em parte · **[ASSUMIDO]** sem resposta; parametrizado em `config/regras.yaml` · **[DECIDIDO]** decisão do time.

Horário das perguntas: preencher na hora (coluna "Horário"). Lote 1 saiu às 9h30.

## 1. Perguntas e respostas

| # | Pergunta | Status | Resposta / efeito | Horário |
|---|---|---|---|---|
| 1 | Comissão pela taxa contratada ou aplicada? | CONFIRMADO | Contratada, inteira, sem desconto do custo da Orbe. Divergência só é reportada | |
| 2 | Estorno de agosto lançado em setembro | CONFIRMADO | Devolve a taxa, abate setembro (agosto não reabre); taxa da venda original | |
| 3 | Antecipação/reversão na comissão e na NF | CONFIRMADO | Mesma nota do MDR; reversão anula só a taxa da antecipação que reverte | |
| 4 | Spread padrão de remessa | ABERTA | Divergência dos lojistas sem spread contratado não é calculada | |
| 5 | Destino das NFs | CONFIRMADO | Remessa: 1 nota para a Ponte. Checkout: 1 por lojista por mês | |
| 6 | Spread realizado ou estimado D-1 | CONFIRMADO | Realizado (`Spread R$`) | |
| 7 | Horizonte Intercâmbio (EC 1043300981) e Kiwi | ABERTA | Pendência, sem adivinhar | |
| 8 | Taxa da Atlas | PARCIAL | Quem decide: Comercial; Atlas não é faturada até confirmar | |
| 9 | Repetida e spread negativo da Ponte | CONFIRMADO | Repetida conta 1x e vai para correção da Ponte. Negativo: contestação (trava de 2h), fora da comissão e da nota | |
| 10 | "APROVADO C/ RESSALVA" entra? | ABERTA | ASSUMIDO: entra (e-mail da Ponte) | |
| 11 | Vigência: data da venda ou da liquidação | PARCIAL | Estorno: venda original. Venda normal: ASSUMIDO `data_movimento` | |
| 12 | Salários/INSS/FGTS/impostos de 08 | ABERTA | ASSUMIDO: baixa de provisão (parâmetro) | |
| 13 | Limiar de divergência | PARCIAL | Lógica confirmada (comparar taxas). ASSUMIDO: ≥ R$ 0,01 | |
| 14 | Repasse da Ponte de 08/2026 (R$ 61.884,12) | ABERTA (lote 3) | ASSUMIDO: baixa recebível (1.1.03.002) | |
| 15 | TED de R$ 300 mil de 30/09 sem contrapartida | ABERTA (lote 3) | Pendência | |
| 16 | Tomador da NF de checkout é o lojista? | ABERTA | ASSUMIDO: sim (CNPJ do cadastro mestre) | |
| 17 | Ajustes tardios da Orbe (`06_`) são definitivos? Podem chegar mais depois do fechamento? | ABERTA | ASSUMIDO: competência de setembro, entram no fechamento. Ver §3.5 | |
| — | `ref_origem` Aurora: L9 (linha física) ou L10 (enunciado)? (#hackathon-duvidas) | ABERTA | Ver §3.1. Perguntar **antes** de gerar `lancamentos_classificados` | |

## 2. Decisões do time

- **[DECIDIDO] Diferença de ~R$ 0,03 em remessa:** `diferenca_brl = Spread R$ − Valor ME × PTAX Ref. × spread contratado`. Entra em divergências só se `Spread %` diferir do contratado além de 5 casas.
- **[DECIDIDO] Arredondamento e rastro:** `Decimal` com `ROUND_HALF_UP`. Quem emite passa cada linha de origem já com a regra aplicada (ex.: comissão da transação); `core/saida.py` arredonda cada linha e o total a 2 casas e **falha** se Σ rastro ≠ total. Consequência para o checkout: a comissão é arredondada **por transação** e o total do lojista é a soma das linhas arredondadas.
- **[DECIDIDO] Percentual:** tudo em pontos percentuais (2,59 = 2,59%). A planilha vem em fração e é convertida em `core/normalize.pct`; a Orbe já vem em pontos.
- **[DECIDIDO] Python 3.12** (o 3.11 do plano não está instalado na máquina; sem diferença para o código).

## 3. Verificações da Fase 0 contra os dados

Feitas com um script descartável lendo os arquivos como vêm (sem editar entrada).

### 3.1 Bancos
- Aurora: 84 lançamentos, primeiro na linha física **9** (`L9`) e último em `L92`; Meridiano: 100 `FITID` únicos. **[SABEMOS]** Confere com o dicionário.
- O enunciado exemplifica `L10, L11…`, mas a primeira transação está na linha 9. Seguimos a linha física real (`L9`) até a resposta.

### 3.2 Orbe
- 1.943 linhas, `id_transacao` único, 22 ECs, período 01–30/09. Tipos: 1.840 VENDA, 59 ESTORNO, 38 ANTECIPACAO, 6 REVERSAO ANTECIPACAO. **[SABEMOS]**
- `valor_liquido = valor_bruto − valor_taxa` em todas as linhas.
- **Truncamento confirmado:** `valor_taxa` é o truncado de `bruto × taxa` em **1.840/1.840** vendas; só 893 coincidem com o arredondado. Logo `valor_taxa` não serve de base nem de comparação.
- 65 linhas negativas; só **56** têm `id_referencia` dentro do arquivo. As outras **9** referem vendas de agosto (fora do arquivo) e precisam ser resolvidas por `data_venda_original` + EC, como prevê o critério A2.
- `CREDITO PARCELADO` nunca tem 1 parcela e `CREDITO A VISTA` sempre tem 1: a faixa por parcelas é inequívoca.

### 3.3 Taxas contratadas
- Aba vigente: 25 linhas (24 lojistas, Bridge repetida), 20 com EC. 5 sem EC: Horizonte Viagens, Kiwi, Ponte Aérea, Nórdica, Novo Horizonte.
- 4 ECs da Orbe **não estão** na aba vigente: Kiwi (1038867654, 85 linhas), Horizonte Intercâmbio (1043300981, 73), Horizonte Viagens (1043396662, 75) e Atlas (1076801732, 57). Nota: a Horizonte Viagens tem EC na Orbe mas a planilha o deixa vazio; só um humano pode ligar os dois.
- EC da aba sem transações: Globo Trotter (1157874034, inativo).
- Das 5 taxas "inexistentes" (0,99; 1,99; 3,99; 4,09; 4,49): **4 são da Atlas** (sem contrato → pendência para o Comercial) e **4,09 é divergência real da Rota Global**.
- Divergências nos lojistas com contrato (por transação, antes de estornos): **88 vendas, ≈ R$ 1.674,67** (preliminar, para sanidade; o número final sai de `saida/`). Rota Global: crédito aplicado 0,50 p.p. acima do contratado (83 vendas). Bridge: 5 vendas com 2,59% aplicado onde o contrato vigente de 15/09 em diante é 2,19%.

### 3.4 Ponte
- Anexo lido via `email` + `openpyxl`; cabeçalho na linha 5 (achado pelo conteúdo). 233 linhas, 232 `Nº Operação`; rodapé 233 e R$ 78.073,59; Σ das linhas = 78.073,59 (**inclui** repetida e negativos). **[SABEMOS]**
- 14 clientes distintos por CNPJ normalizado.
- 4 spreads negativos: PC-0926-0210 (−687,52), PC-0926-0326 (−509,22), PC-0926-0491 (−292,28), PC-0926-0545 (−345,03).
- **Correção ao dicionário:** o par "mesmo CNPJ/valor/moeda/data" **é a própria `PC-0926-0162`** (Bagagem Livre, USD 10.429,99, 22/09, spread R$ 821,88 nas duas linhas). Não existe um segundo par com `Nº Operação` diferente. A sinalização por "mesmos campos" continua implementada como guarda para outubro.
- **Base da comissão:** 78.073,59 − 821,88 (repetida) − (−1.834,05) (negativos) = **79.085,76**; comissão de remessa = 50% = **39.542,88** (preliminar). Os negativos são subtraídos, então **aumentam** a base: o texto de A4 "− negativos" deve ser lido assim.
- `Spread R$` × `Valor ME × PTAX × Spread %` difere até R$ 0,04 (44 operações acima de R$ 0,01): é a diferença de arredondamento já decidida em §2.
- 16 `APROVADO C/ RESSALVA`, 4 `Taxa travada no pedido (D-1)`, 1 `reprocessada`.

### 3.5 Orbe: ajustes tardios (`06_orbe_ajustes_tardios_set2026.csv`, chegou depois do data pack)
Não consta no `00_LEIA-ME.md`, no enunciado nem no `DICIONARIO_DADOS.md`. **[SABEMOS]** pelos dados:
- Mesmo layout e colunas da Orbe, 14 linhas, **todas de 30/09/2026**: 10 `ESTORNO`, 3 `REVERSAO ANTECIPACAO`, 1 `VENDA`. Sem `id_transacao` repetido contra o `01_`.
- As 13 linhas negativas têm `id_referencia` **dentro do `01_`**, com o mesmo valor (sinal oposto) e nenhuma já estornada no `01_`: **não há estorno em dobro**. Todas as vendas originais são de setembro (nenhuma de agosto).
- `valor_taxa` truncado e `valor_liquido = bruto − taxa` em todas as linhas, igual ao `01_`.
- A taxa aplicada em cada ajuste = contratada na data da venda original (inclusive Bridge antes de 15/09): **não gera divergência**.
- A venda `TX88447225` (R$ 5.480,00) é da **Kiwi** (EC 1038867654, sem contrato): vira pendência, não comissão.
- Efeito na comissão de setembro (preliminar): estornos e reversões **abatem R$ 3.479,20** (estornos 867,71 de taxa Orbe + reversões 2.436,61 pela taxa aplicada, arredondadas pela regra Tarvo) em Dublin Hub, Maple Study, Mundo Aberto, Bridge, EduAbroad e Oxford Prep. Oxford Prep e Maple concentram as 3 reversões de antecipação (R$ 124 mil de principal).
- **[ASSUMIDO]** Os ajustes pertencem à competência de setembro (data 30/09) e entram no mesmo fechamento. Pergunta nova **17**: os ajustes tardios são definitivos ou a Orbe pode mandar mais depois do fechamento (reabre?). Efeito até a resposta: o pipeline lê todos os arquivos Orbe da pasta, então qualquer novo arquivo é só rodar de novo.
- Totais Orbe passam a ser **1.957 linhas**: 1.841 VENDA, 69 ESTORNO, 38 ANTECIPACAO, 9 REVERSAO; 116 não-VENDA.

## 4. Mínimo, lado A: checkout (leitores, cadastro, cálculo)

- **[CONFIRMADO, P1] M8:** comissão = `valor_bruto × taxa contratada`, sem custo da Orbe; `config/regras.yaml` (`checkout.base_comissao`).
- **Cadastro mestre:** `config/lojistas.yaml` gerado da planilha por EC exato (19 ECs); regerar só acrescenta. Os 4 ECs da Orbe fora dele (Kiwi, Horizonte Intercâmbio, Horizonte Viagens, Atlas) viram pendência; **nenhum casamento por nome**.
- **[ASSUMIDO] Roteamento de pendências** por `checkout.ec_sem_cadastro` (config): Atlas → `CONTRATO_AUSENTE`/Comercial (confirmado, P8); Horizonte Intercâmbio → `CONTRATO_AMBIGUO`/Comercial (segue a tabela do contrato técnico; quem decide não foi dito, P7); demais ECs → `CADASTRO_NAO_RESOLVIDO`/Financeiro.
- **Resultado preliminar (data pack):** 1.841 vendas = 1.574 processadas + 267 em pendência (Kiwi + Horizonte Viagens 152, Horizonte Intercâmbio 69, Atlas 49, Globo Trotter 0 vendas); 18 lojistas com comissão; 116 não-VENDA fora de escopo (69 estornos, 38 antecipações, 9 reversões); 1.943 linhas do `01_` + 14 do `06_`.
- **M7, revisão de 5 vendas (feita por A; falta a cruzada com B):** TX88410932 608,88×2,69% = 16,3789 → 16,38 (Orbe truncou 16,37); TX88410128 5.773,57×3,79% → 218,82; TX88416245 15.600,29×3,79% → 591,25; TX88436225 2.716,38×3,19% → 86,65; TX88444565 2.459,05×3,19% → 78,44. Todas batem com o rastro.

## 5. Alvo: hipóteses e decisões (CONTRATO_TECNICO_ALVO.md)

Registradas na elaboração do contrato do Alvo. Nenhuma delas veio do financeiro; as marcadas **[PROPOSTO]** aguardam confirmação do time (contrato Alvo §10) e podem mudar números.

| # | Hipótese / decisão | Etiqueta | Efeito e parâmetro |
|---|---|---|---|
| H1 | **Arredondamento da remessa por operação** (`q2(Spread R$ × 0,5)` por linha; comissão do lojista = soma das linhas), coerente com §2 | [PROPOSTO] | Comissão REMESSA = **R$ 39.543,45**; a conta "50% × Σ" daria R$ 39.542,88 (diferença +R$ 0,57). NF REMESSA = R$ 39.543,45. Os 39.542,88 de §3.4 e do PLANO A4 ficam como preliminar superado, se confirmado. Alternativa (arredondar só o total) exigiria linha de ajuste no rastro, vedada pelo contrato |
| H2 | **`ref_origem` da operação repetida = `<Nº Operação>#<k>`** (k = ordem da ocorrência: `PC-0926-0162#2`), com origem no `.eml` | [PROPOSTO] | Evita duplicar `ref_origem` no rastro. Alternativa: linha física (`Operações!L77`). A e B devem combinar |
| H3 | **Janela de contrapartida de transferência entre contas = 3 dias** | [DECIDIDO] | `bancos.janela_contrapartida_dias`. Os 3 pares do data pack batem no mesmo dia. Sem par: `TRANSFERENCIA_SEM_CONTRAPARTIDA` (R$ 300 mil de 30/09, pergunta 15 aberta) |
| H4 | **`conta_codigo` pode ser vazio quando `metodo = HUMANO`** (`confianca = 0`) | [PROPOSTO] | Exige relaxar a validação em `saida.py` só nesse caso. Hoje nenhum lançamento cai aqui (as 184 casam por regra); teste sintético. Conferir no enunciado |
| H5 | **Tolerância do spread de remessa em pontos percentuais**: `precisao_spread_pct` (0,00001 em fração) vale **0,001 p.p.** | [DECIDIDO] | Converter `× 100` no código; chave do YAML mantida em fração. Testar com a operação de ~R$ 0,03 |
| H6 | **`OPERACAO_POSSIVEL_DUPLICIDADE` só sinaliza** (mesmo CNPJ, Valor ME, moeda e data com `Nº Operação` diferente); a operação continua na comissão | [ASSUMIDO] | Critério de "mesmos campos" não foi comentado pela Helena (P9). Hoje não ocorre além da própria `PC-0926-0162` |
| H7 | **Divergência de remessa não calculada para spread padrão** (célula vazia ou `padrão`); a comissão é calculada normalmente | [ASSUMIDO] | Pergunta 4 aberta. 51 operações sem divergência calculada (Kiwi, Ponte Aérea, Canguru). `spread_remessa_pct = None` |
| H8 | **Modo `despesa` de folha e impostos de 08 não tem conta para INSS e FGTS** no plano (só 4.1.01 Salários); essas linhas viram `LANCAMENTO_NAO_CLASSIFICADO` | [ASSUMIDO] | Pergunta 12 aberta; padrão `baixa_provisao` (2.1.04.001/.002/.003) |
| H9 | **Estorno e reversão: a taxa e a vigência vêm da `data_venda_original`; a comissão abate o mês do estorno** (agosto não reabre). Estorno de venda de agosto é resolvido por `data_venda_original` + EC, sem precisar achar a original | [CONFIRMADO] P2/P3 | 9 estornos de agosto fora do arquivo. Estorno em 15/09 ou depois de venda da Bridge anterior a 15/09 usa 2,59% |
| H10 | **Divergência de estorno tem sinal negativo** (`diferenca_brl = bruto × (aplicada − contratada)`, bruto negativo): devolução do excesso. Positivo = lojista pagou a mais | [DECIDIDO] | 4 estornos de divergentes no data pack. Divergência não é restituição (pergunta 1 não respondeu sobre devolver a diferença) |
| H11 | **Linha bloqueada de qualquer tipo da Orbe rastreia o bruto assinado**; tipo de lançamento desconhecido, estorno em dobro e sinal inconsistente viram `LANCAMENTO_INVALIDO` | [DECIDIDO] | Nada some em silêncio; `fora_escopo_por_tipo` fica vazio no Alvo |
| H12 | **Atlas e lojista sem linha processada não têm comissão nem NF**; a explicação é a pendência por linha (`CONTRATO_AUSENTE`, Comercial). Sem `NF_NAO_EMITIDA` extra | [CONFIRMADO] P8 (nota não emitida) / [DECIDIDO] (sem duplicar alarme) | `NF_NAO_EMITIDA` só para comissão com saldo ≤ 0 |
| H13 | **Tomador da NF de checkout = o lojista** (CNPJ do cadastro) | [ASSUMIDO] P16 | `checkout.nf_tomador: lojista` |
| H14 | **Remessa identifica o lojista só por CNPJ e não exige EC**; nome exibido do cadastro mestre, senão da planilha | [DECIDIDO] | Kiwi, Novo Horizonte, Nórdica e Ponte Aérea entram na remessa mesmo sem EC. A Kiwi tem checkout bloqueado e remessa faturável |
| H15 | **`Data Liquidação` da Ponte não é validada contra a competência** (só `Data Contratação`) | [DECIDIDO] | 6 operações liquidam em outubro; todas contratadas em setembro |
| H16 | **Rodapé da Ponte divergente das linhas vira pendência `RODAPE_DIVERGENTE`**, não aborta a execução | [DECIDIDO] | Hoje confere: 233 linhas e R$ 78.073,59 |
| H17 | **Ordenação das comissões por `(linha_negocio, cnpj)`**: CHECKOUT antes de REMESSA | [DECIDIDO] | Mantém `COM-0001…0018` do Mínimo. Ids `PEN-` do Mínimo mudam ao entrarem tipos novos |
| H18 | **Repasse da Ponte de 08/2026 (R$ 61.884,12) classificado em 1.1.03.002 e Pix sem identificação em 1.1.09.002 com `metodo = REGRA`**, esta com pendência | [ASSUMIDO] P14 / [DECIDIDO] | O repasse não é pendência |

### 5.1 Números de referência do Alvo (recálculo independente, preliminar)

Verificações do data pack, não constantes do algoritmo; o número final sai de `saida/`.

- **Checkout:** 1.666 linhas tratadas + 291 bloqueadas = 1.957. Comissão **R$ 191.464,34** = vendas 180.006,23 − estornos 7.186,48 + antecipações 23.105,36 − reversões 4.460,77. Bloqueadas: 267 vendas, 12 estornos, 8 antecipações, 4 reversões.
- **Divergências de checkout:** 92 linhas (88 vendas, R$ 1.674,67; 4 estornos); líquido **R$ 1.576,23**. Rota Global 87, Bridge 5. Antecipações e reversões: nenhuma.
- **Remessa:** 233 = 228 válidas + 4 `CONTESTACAO` + 1 `OPERACAO_REPETIDA`; base R$ 79.085,76 (78.073,59 − 821,88 + 1.834,05); 41 divergências, R$ 1.419,05.
- **Bancos:** 84 Aurora + 100 Meridiano = 184, todas por regra; pendências: Pix sem identificação (R$ 7.350,00) e TED sem contrapartida (−R$ 300.000,00).
- **Notas:** 18 CHECKOUT + 1 REMESSA. Σ NF CHECKOUT = R$ 191.464,34 **se nenhum dos 18 lojistas tiver saldo ≤ 0** (a verificar).

### 5.2 Implementação de B e verificação

As decisões H1–H8 orientam a implementação de B: arredondamento por operação
(comissão R$ 39.543,45), referência da repetida com `#2`, janela de contrapartida
de 3 dias e conta vazia exclusivamente para `HUMANO` com confiança zero.
A tolerância configurada em fração é convertida para pontos percentuais.
Possível duplicidade apenas sinaliza; spread padrão não gera divergência nem
pendência. No modo `despesa`, INSS/FGTS exigem classificação humana.

Os testes de B conferem remessa e bancos contra as entradas reais e validam
publicação determinística com interfaces sintéticas de checkout/notas de A.
A reconciliação obtida é R$ 78.073,59 − R$ 821,88 − (−R$ 1.834,05) =
R$ 79.085,76 de base. Não foi realizada revisão cruzada por outra pessoa;
o fechamento real integrado aguarda a entrega de A descrita no README.
