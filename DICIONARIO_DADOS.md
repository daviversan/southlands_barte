# Dicionário de dados: data pack Tarvo (fechamento set/2026)

Fonte: `context/tarvo_data_pack/`. Tudo aqui foi medido nos arquivos. O que é interpretação ou hipótese está marcado como **[hipótese]**.

## 1. Visão geral

| Arquivo | Entidade | Uma linha é | Formato | Volume |
|---|---|---|---|---|
| `01_orbe_relatorio_comissoes_set2026.csv` | Transação da adquirente Orbe | uma venda, estorno, antecipação ou reversão | CSV `;`, decimal vírgula, `dd/mm/aaaa`, ASCII, CRLF | 1.943 linhas (cabeçalho + 1.943) |
| `02_tabela_taxas_contratadas.xlsx` | Contrato de taxas por lojista | um lojista (ou uma vigência de um lojista) | xlsx, 2 abas | 25 linhas na aba vigente (24 lojistas, a Bridge aparece 2 vezes) |
| `03_email_ponte_cambio_relatorio_set2026.eml` | Operação de câmbio da Ponte | uma remessa internacional | e-mail com anexo xlsx (2 abas) | 233 operações |
| `04_plano_de_contas_fenix_erp.csv` | Conta contábil do ERP Fênix | uma conta | CSV `;`, **ISO-8859-1**, CRLF | 52 contas (32 analíticas) |
| `05a_extrato_banco_aurora_cc4471_set2026.csv` | Lançamento da conta principal | um débito ou crédito | CSV `;`, UTF-8, LF, valores pt-BR | 95 linhas físicas, 84 lançamentos |
| `05b_extrato_banco_meridiano_cc90233_set2026.ofx` | Lançamento da conta de remessas | um débito ou crédito | OFX 1.02 (SGML), **CP1252**, CRLF | 100 lançamentos |

O `00_LEIA-ME.md` descreve o pacote e não tem dados.

## 2. Como cada fonte identifica o lojista

Não existe chave comum. Este é o centro do problema do case.

| Fonte | Identificador | Forma | Problema medido |
|---|---|---|---|
| Orbe | `cod_estabelecimento` (EC) e `nome_estabelecimento` | EC com 10 dígitos | 22 ECs com 31 grafias de nome. O EC 1037647039 aparece como `Mundo Aberto`, `MUNDO ABERTO INTERCAMBIO` e `MUNDO ABERTO INTERC LTDA` |
| Planilha de taxas | `EC Orbe`, `CNPJ` e nome | CNPJ pontuado, só dígitos ou número | 5 lojistas sem EC. Dois CNPJs com 13 dígitos (zero à esquerda perdido) |
| Ponte | `CNPJ Cliente` e `Cliente` | CNPJ pontuado em 70 linhas e só dígitos em 163 | Nome truncado em 20 caracteres |
| Aurora | só o nome dentro de `Lançamento` | texto livre truncado | Sem CNPJ, sem EC |
| Meridiano | só o nome dentro de `MEMO` | texto livre truncado | `PONTE AÉREA` e `PONTE AEREA` coexistem |

## 3. Dicionário por arquivo

### 3.1 Orbe: `01_orbe_relatorio_comissoes_set2026.csv`

Granularidade: uma linha por transação. Período: 01/09/2026 a 30/09/2026. `id_transacao` é único (1.943 valores).

| Coluna | Tipo | Descrição | Domínio ou exemplo | Observações |
|---|---|---|---|---|
| `id_transacao` | texto | Identificador da transação | `TX88410932` (venda, estorno), `AN88444882` (antecipação, reversão) | Prefixo `TX` ou `AN`. É o `ref_origem` exigido na saída |
| `data_movimento` | data `dd/mm/aaaa` | Data do lançamento na Orbe | `01/09/2026` | Em estorno, é a data do estorno, não da venda |
| `cod_estabelecimento` | texto numérico | EC do lojista na Orbe | `1018325654` | Nunca vazio. Tratar como texto |
| `nome_estabelecimento` | texto | Nome do lojista como a Orbe o escreve | `CASA DO ESTUDANTE VIAGENS` | Varia para o mesmo EC. Não usar como chave |
| `tipo_lancamento` | enum | Natureza da linha | `VENDA` (1.840), `ESTORNO` (59), `ANTECIPACAO` (38), `REVERSAO ANTECIPACAO` (6) | |
| `modalidade` | enum | Forma de pagamento | `CREDITO PARCELADO` (951), `CREDITO A VISTA` (591), `PIX` (183), `DEBITO` (174), vazio (44) | Vazio nas 44 linhas de antecipação e reversão |
| `qtd_parcelas` | inteiro | Número de parcelas | 1 a 12 | 1 para débito, à vista e Pix. Vazio nas antecipações |
| `bandeira` | enum | Bandeira do cartão | `MASTERCARD`, `ELO`, `AMEX`, `VISA`, `HIPERCARD` | Vazio em Pix (183) e antecipação (44) |
| `valor_bruto` | decimal, vírgula | Valor da operação em R$ | `608,88`, `-2193,16` | **Negativo em estorno e reversão** (65 linhas) |
| `taxa_aplicada_pct` | decimal, vírgula | Taxa que a Orbe aplicou, em pontos percentuais | `2,69` significa 2,69% | Não é fração. Compara-se com a taxa contratada (planilha, em fração) |
| `valor_taxa` | decimal, vírgula | Taxa em R$ | `16,37` | Negativo em estorno. Aparenta ser **truncado** no centavo: 608,88 × 2,69% = 16,3789 e o arquivo traz 16,37 |
| `valor_liquido` | decimal, vírgula | `valor_bruto − valor_taxa` | `592,51` | Conferido nas linhas lidas |
| `id_referencia` | texto | Transação original que este estorno ou reversão desfaz | `TX87651902`, `AN88444915` | Preenchido só nas 65 linhas negativas |
| `data_venda_original` | data | Data da venda ou antecipação original | `22/08/2026` | Preenchido só nas 65 linhas negativas. Pode ser de agosto |

Taxas aplicadas observadas: 0,79; 0,89; 0,99; 1,39; 1,49; 1,99; 2,10; 2,19; 2,39; 2,49; 2,59; 2,69; 2,89; 2,99; 3,09; 3,19; 3,49; 3,59; 3,79; 3,99; 4,09; 4,49. As taxas 0,99, 1,99, 3,99, 4,09 e 4,49 não coincidem com nenhuma taxa da aba vigente da planilha. Podem ser divergências, ou lojistas fora da aba, como a Atlas.

### 3.2 Planilha de taxas: `02_tabela_taxas_contratadas.xlsx`

Mantida à mão pelo financeiro ("atualizar sempre que o comercial fechar!!", última atualização 02/09, Bia).

**Aba `Taxas vigentes`.** O topo traz título, data de atualização e grupos (`CARTÃO / PIX (MDR)` e `REMESSA`), antes do cabeçalho. O rodapé traz `* spread em branco = padrão`.

| Coluna | Descrição | Formato real encontrado |
|---|---|---|
| `Lojista` | Nome comercial | Texto livre. `Vela`, `Canguru` e `EduAbroad` diferem do nome nas outras fontes |
| `CNPJ` | CNPJ do lojista | Pontuado, só dígitos ou perdendo zero à esquerda (13 dígitos: Fluente e Campus Global) |
| `EC Orbe` | EC na Orbe | Vazio em Horizonte Viagens, Kiwi (obs.: `EC pendente`), Ponte Aérea, Nórdica e Novo Horizonte |
| `Débito`, `Crédito à vista`, `Créd. 2-6x`, `Créd. 7-12x`, `Pix`, `Antecipação` | MDR e antecipação contratados | **Fração** (`0.0149`) na maioria. **Texto com `%`** (`'1,49%'`) em Oxford Prep e Sol Nascente |
| `Spread remessa` | Spread cobrado do lojista na remessa | Fração (`0.015`), a palavra `padrão` (Canguru) ou vazio (vale o padrão, que não está escrito) |
| `Vigência` | Início ou intervalo de validade | `01/01/2026`, `01/06/2026`, `até 14/09/2026`, `a partir de 15/09/2026`, ou vazio (Globo Trotter) |
| `Obs` | Observação livre | `renegociado`, `só remessa`, `INATIVO desde jul/26`, `EC pendente` |

Pontos de atenção:
- A **Bridge** ocupa 2 linhas, com o mesmo EC e CNPJ. O crédito à vista é 2,59% até 14/09 e 2,19% a partir de 15/09.
- **Ponte Aérea** e **Nórdica** são só remessa e não têm taxas de checkout. A Nórdica tem spread 1,25%.
- **Globo Trotter** está inativo, sem vigência.
- Faixas dos MDR: débito 1,39–1,49%, crédito à vista 2,19–2,69%, 2–6x 2,89–3,19%, 7–12x 3,49–3,79%, Pix 0,79–0,89%, antecipação 2,10% para todos. Spread de remessa: 1,20–1,60%.

**Aba `ANTIGO 2025 - nao usar`.** 12 lojistas com `Lojista`, `CNPJ` (só dígitos), `Débito`, `Crédito à vista`, `Créd. parcelado` (sem separar 2–6x de 7–12x) e `Pix`. Contém a **Atlas Idiomas**, que não está na aba vigente. É lixo para a regra geral, mas é a única menção de contrato da Atlas.

### 3.3 Ponte Câmbio: `03_email_ponte_cambio_relatorio_set2026.eml`

**E-mail.** De `relatorios@pontecambio.com.br` para `financeiro@tarvo.com.br`, enviado em 02/10/2026. Texto em UTF-8 quoted-printable. Anexo: `PonteCambio_Relatorio_TARVO_092026.xlsx`. O corpo traz regras de negócio:
- a Tarvo recebe **50% do spread realizado**;
- o repasse é creditado em **06/10/2026**, mediante recebimento da **nota fiscal de intermediação**;
- operações `APROVADO C/ RESSALVA` seguem normalmente para liquidação;
- divergências devem ser reportadas em até **5 dias úteis**.

A assinatura traz o CNPJ da Ponte (75.374.179/0001-46). O relatório traz o CNPJ da Tarvo (84.626.315/0001-39).

**Anexo, aba `Operações`.** Linhas 1 a 3: título, parceiro e competência. Linha 5: cabeçalho. Linhas 6 a 238: operações. Linhas 240 e 241: rodapé (`Total de operações: 233` e `Spread total R$: 78073.59`). Os textos são `inlineStr` (o arquivo não tem `sharedStrings.xml`).

| Coluna | Tipo | Descrição | Observações |
|---|---|---|---|
| `Nº Operação` | texto | Identificador da operação | `PC-0926-0002`. É o `ref_origem`. A sequência não é contígua |
| `Data Contratação` | **serial Excel** | Dia em que a operação foi contratada | 46266 = 01/09/2026 (sistema 1900) |
| `Data Liquidação` | serial Excel | Dia da liquidação | Normalmente 1 a 3 dias após |
| `CNPJ Cliente` | texto | CNPJ do lojista | Pontuado (70) ou só dígitos (163) |
| `Cliente` | texto | Nome do lojista | **Truncado em 20 caracteres** (`MUNDO ABERTO INTERCÂ`). 14 clientes distintos |
| `Moeda` | enum ISO 4217 | Moeda estrangeira | `AUD` 48, `CAD` 42, `NZD` 37, `USD` 37, `GBP` 36, `EUR` 33 |
| `Valor ME` | decimal | Valor na moeda estrangeira | |
| `Taxa Cliente` | decimal | Câmbio aplicado ao lojista (R$ por unidade de ME) | = PTAX × (1 + spread) |
| `PTAX Ref.` | decimal | Câmbio de referência | |
| `Valor R$` | decimal | `Valor ME × Taxa Cliente` | Conferido em uma linha |
| `Spread R$` | decimal | `Valor ME × (Taxa Cliente − PTAX)`. É o spread **realizado** | **Negativo em 4 linhas**: −687,52; −509,22; −292,28; −345,03 |
| `Spread %` | decimal (fração) | Spread sobre a PTAX | `0.01501`. Compara-se com o spread contratado |
| `Spread Estimado R$ (D-1)` | decimal | Estimativa feita na véspera | Difere do realizado. Não é a base de comissão **[hipótese]** |
| `IOF R$` | decimal | IOF da operação | ≈ 0,38% do `Valor R$` (conferido em 4 linhas) |
| `Status Compliance` | enum | Situação | `APROVADO` 217, `APROVADO C/ RESSALVA` 16 |
| `Observação` | texto | Nota da Ponte | Vazio (228), `Taxa travada no pedido (D-1)` (4), `reprocessada` (1) |

Totais do rodapé: 233 operações e R$ 78.073,59 de spread. Os dois números **incluem** a operação repetida e os 4 spreads negativos, porque a soma das linhas dá exatamente 78.073,59.

**Aba `Resumo`.** Por moeda: `Moeda`, `Qtd`, `Volume ME`, `Spread R$`. As quantidades somam 233 e o spread soma 78.073,59.

### 3.4 Plano de contas: `04_plano_de_contas_fenix_erp.csv`

Encoding **ISO-8859-1**. Lido como UTF-8, os acentos se corrompem.

| Coluna | Descrição | Domínio |
|---|---|---|
| `COD_CONTA` | Código hierárquico | `1.1.01.001`, `3.1.01`. **Nem toda analítica tem a mesma profundidade**: `3.1.01` tem 3 níveis e `1.1.01.001` tem 4 |
| `DESCRICAO` | Nome da conta | |
| `TIPO` | Sintética (agrupa) ou analítica (recebe lançamento) | `SINTETICA` 20, `ANALITICA` 32 |
| `NATUREZA` | Natureza do saldo | `D` ou `C` |
| `ACEITA_LANCTO` | Se aceita lançamento | `S` exatamente nas 32 analíticas |
| `COD_SUPERIOR` | Conta pai | |
| `DT_CRIACAO` | Data de criação | Todas `15/01/2024` |

Estrutura: 1 Ativo, 2 Passivo, 3 Receitas, 4 Despesas. Só as contas com `ACEITA_LANCTO = S` podem ser usadas em `conta_codigo`.

### 3.5 Aurora: `05a_extrato_banco_aurora_cc4471_set2026.csv`

Conta principal da Tarvo (agência 0318, conta 4471-0). O arquivo é um extrato impresso, não uma tabela limpa.

| Linha física | Conteúdo |
|---|---|
| 1 a 6 | Banco, tipo de extrato, cliente, CNPJ da Tarvo, agência e conta, período |
| 7 | Cabeçalho: `Data;Lançamento;Documento;Valor (R$);Saldo (R$)` |
| 8 | `SALDO ANTERIOR` (31/08/2026), saldo 612.334,81, sem valor |
| **9 a 92** | **84 lançamentos** |
| 93 a 95 | Linha vazia, `SALDO FINAL` (−1.920.088,60) e aviso `Os lançamentos estão sujeitos a confirmação.` |

| Coluna | Tipo | Descrição | Observações |
|---|---|---|---|
| `Data` | data `dd/mm/aaaa` | Data do lançamento | |
| `Lançamento` | texto | Descrição livre | Truncada em cerca de 36 caracteres. O nome do lojista está aqui |
| `Documento` | numérico | Número do documento | Só preenchido nas TEDs da Orbe (`988044`) |
| `Valor (R$)` | decimal pt-BR | Valor assinado | **Ponto de milhar, vírgula decimal** (`66.026,00`). **Negativo é saída** |
| `Saldo (R$)` | decimal pt-BR | Saldo corrente | Negativo a partir de 09/09 |

**`ref_origem`:** a primeira transação (TED da Orbe de 01/09) está na linha física **9** e o `TAR PACOTE SERVICOS PJ` na linha 10. O enunciado exemplifica `L10, L11…`. Confirmar a convenção de numeração em #hackathon-duvidas antes de gerar o `ref_origem`.

### 3.6 Meridiano: `05b_extrato_banco_meridiano_cc90233_set2026.ofx`

Conta de câmbio (banco 0477, agência 0091, conta 90233-5, BRL). OFX 1.02 em SGML: as tags **não são fechadas**, então um parser XML não funciona. Encoding declarado `CHARSET:1252`.

**Cabeçalho do extrato:** `DTSTART` 01/09/2026, `DTEND` 30/09/2026, saldo final (`LEDGERBAL`) **1.320.453,26** em 30/09.

| Campo (por `<STMTTRN>`) | Tipo | Descrição | Observações |
|---|---|---|---|
| `TRNTYPE` | enum | Sentido | `CREDIT` 72, `DEBIT` 28 |
| `DTPOSTED` | data e hora | Data do lançamento | `20260901120000[-3:BRT]`. A hora é sempre 12:00:00 |
| `TRNAMT` | decimal com **ponto** | Valor assinado | `-240619.49`. Diferente do Aurora (vírgula) |
| `FITID` | texto | Identificador único | `MRD2026090003`. Único em todo o arquivo. É o `ref_origem` |
| `CHECKNUM` | numérico | Número do documento | |
| `MEMO` | texto | Descrição | Truncada em cerca de 38 caracteres, com caracteres CP1252 (`INTERC�MBIO`) |

## 4. Relações entre os arquivos

| De | Para | Chave | Qualidade |
|---|---|---|---|
| Orbe `cod_estabelecimento` | Planilha `EC Orbe` | EC exato | Boa onde o EC existe. Faltam 5 |
| Planilha `CNPJ` | Ponte `CNPJ Cliente` | CNPJ normalizado (só dígitos, 14) | Boa depois de normalizar |
| Orbe `id_referencia` | Orbe `id_transacao` | ID exato | Boa. Liga estorno e reversão à origem |
| Orbe (soma dos líquidos) | Aurora `TED RECEBIDA … ORBE` | Data e valor | 21 TEDs. Conciliação fora do escopo declarado |
| Aurora `PIX ENVIADO <nome>` | Lojista | Nome truncado | Sem chave. Precisa do cadastro mestre |
| Meridiano `PIX RECEB <nome>` | Lojista | Nome truncado | Sem chave |
| Meridiano `TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES` | Ponte, operações | Nenhuma | 21 TEDs para 233 operações, então a liquidação é em lote |
| Aurora `TRANSF ENTRE CONTAS` | Meridiano `TED RECEBIDA … MESMA TITULARIDADE` | Data e valor | 3 de 4 casam: 350 mil (02/09), 420 mil (11/09), 380 mil (21/09). A de **R$ 300 mil em 30/09 não tem contrapartida** no Meridiano |
| Meridiano `TED RECEB PONTE CAMBIO REPASSE COMISSAO 08/2026` | Spread de agosto | Competência no texto | R$ 61.884,12 em 04/09. **O repasse da Ponte cai no Meridiano** |

## 5. Padrões de lançamento bancário

A coluna "conta candidata" é uma proposta a validar com o financeiro, não uma regra confirmada.

### Aurora (84 lançamentos)

| Padrão em `Lançamento` | Qtd | Conta candidata |
|---|---|---|
| `TED RECEBIDA <CNPJ> ORBE ADQUIRENCIA SA` | 21 | 1.1.03.001 |
| `PIX ENVIADO <lojista>` | 44 (22 lojistas × 2) | 2.1.01.001 |
| `TRANSF ENTRE CONTAS P/ BCO MERIDIANO …` | 4 | 1.1.09.001 |
| `DEVOLUCAO PIX <lojista>` | 1 | 2.1.01.002 |
| `PIX RECEBIDO <CNPJ> SEM IDENTIFICACAO` (R$ 7.350,00, 16/09) | 1 | 1.1.09.002 e pendência |
| `TAR …` (pacote de serviços; TED e Pix avulsas) | 2 | 4.2.01 |
| `BOLETO CONDOMINIO …` | 1 | 4.2.02 |
| `DEB AUT AMAZON WEB SERVICES` | 1 | 4.2.03 |
| `CARTAO PJ - GOOGLE WORKSPACE` | 1 | 4.2.04 |
| `PIX ENVIADO CONTABILIDADE EXATA LTDA` | 1 | 4.2.06. **Atenção:** o prefixo é igual ao dos repasses a lojistas |
| `PAGTO SALARIOS - FOLHA 08/2026` | 1 | 2.1.04.001 ou 4.1.01 (depende da resposta sobre provisão) |
| `GPS INSS 08/2026` e `GRF FGTS 08/2026` | 2 | 2.1.04.002 e 2.1.04.003 (idem) |
| `DEBITO DARF … IRRF`, `PIS`, `COFINS` | 3 | 2.1.03.004, .001, .002 |
| `PAGTO ISS SAO PAULO DAMSP 08/2026` | 1 | 2.1.03.003 |

### Meridiano (100 lançamentos)

| Padrão em `MEMO` | Qtd | Conta candidata |
|---|---|---|
| `PIX RECEB <lojista>` | 64 | 2.1.02.001 |
| `TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES` | 21 | 2.1.02.001 **[hipótese]** |
| `TED RECEBIDA TARVO PAGAMENTOS … MESMA TITULARIDADE` | 3 | 1.1.09.001 |
| `TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 08/2026` | 1 | 1.1.03.002 **[hipótese]**, por ser competência de agosto |
| `APLICACAO AUTOMATICA CDB DI` e `RESGATE AUTOMATICO CDB DI` | 3 + 3 | 1.1.02.001 |
| `RENDIMENTO APLIC AUTOMATICA` | 1 | 3.2.01 |
| `TARIFA MANUTENCAO CONTA PJ` e `TARIFA PACOTE CAMBIO` | 2 | 4.2.01 |
| `SEGURO EMPRESARIAL PARC 09/12` | 1 | 4.2.05 |
| `IOF S/ OPERACAO CREDITO` | 1 | 4.3.01 |

## 6. Armadilhas medidas

1. **Orbe, nomes:** 31 grafias para 22 ECs. Casar por nome gera erro. Casar por EC não.
2. **Orbe, sinais:** estorno e reversão têm `valor_bruto`, `valor_taxa` e `valor_liquido` negativos (65 linhas). A taxa a usar é a da venda original, que pode ser de agosto **[hipótese]**.
3. **Orbe, vazios estruturais:** as 44 linhas de antecipação e reversão não têm modalidade, parcelas nem bandeira. Não são dado faltante.
4. **Orbe, arredondamento:** `valor_taxa` parece truncado no centavo. Diferenças de R$ 0,01 contra o cálculo `bruto × taxa` não são divergência de taxa.
5. **Orbe, taxas fora da tabela:** 0,99; 1,99; 3,99; 4,09 e 4,49 não existem na aba vigente.
6. **Planilha, tipos mistos:** fração, texto com `%`, CNPJ como texto ou número (zero à esquerda perdido), spread em fração, `padrão` ou vazio.
7. **Planilha, cobertura:** 5 lojistas sem EC. A Atlas só existe na aba 2025. A Globo Trotter está inativa.
8. **Ponte, repetição:** 233 linhas para 232 `Nº Operação` distintos. O `PC-0926-0162` aparece 2 vezes, e há ainda um par com o mesmo CNPJ, valor, moeda e data.
9. **Ponte, spread:** 4 negativos, 16 `APROVADO C/ RESSALVA`, 4 `Taxa travada no pedido (D-1)` e 1 `reprocessada`.
10. **Ponte, formato:** datas em serial Excel, CNPJ em 2 formatos, nome truncado em 20 caracteres.
11. **Aurora, prefixos:** `PIX ENVIADO` serve tanto para lojista quanto para a contabilidade. Classificar só pelo prefixo erra.
12. **Aurora, saldo:** negativo a partir de 09/09 e termina em −R$ 1.920.088,60. Os repasses saem antes de as TEDs da Orbe cobrirem.
13. **Encodings:** Orbe em ASCII, Aurora em UTF-8, Plano em ISO-8859-1 e OFX em CP1252. Um leitor único errará.
14. **Pix sem identificação:** R$ 7.350,00 em 16/09, CNPJ 38686002000180.

## 7. Glossário

| Termo | Significado |
|---|---|
| **Subadquirente** | Empresa que credencia lojistas e usa uma adquirente (aqui, a Orbe) para processar. É a Tarvo |
| **EC (estabelecimento comercial)** | Código do lojista na adquirente |
| **MDR** | Taxa cobrada do lojista sobre cada venda no cartão ou Pix |
| **Antecipação** | Receber hoje o valor de vendas parceladas, pagando uma taxa. Reversão desfaz uma antecipação |
| **Estorno** | Devolução de uma venda. Gera linha negativa |
| **PTAX** | Taxa de câmbio de referência do Banco Central |
| **Spread** | Diferença entre o câmbio cobrado do cliente e a PTAX. É a remuneração da operação de câmbio |
| **ME** | Moeda estrangeira |
| **IOF** | Imposto sobre operações financeiras, incluindo câmbio |
| **TED e Pix** | Transferências bancárias. TED liquida em lote |
| **FITID** | Identificador único de uma transação no formato OFX |
| **OFX** | Formato padrão de extrato bancário |
| **DARF, GPS, GRF** | Guias de recolhimento de tributo, INSS e FGTS |
| **ISS, PIS, COFINS, IRRF** | Tributos sobre serviço, receita e renda retida |
| **Conta sintética e analítica** | Sintética agrupa e não recebe lançamento. Analítica recebe |
| **NF de intermediação** | Nota fiscal que a Tarvo emite à Ponte pela participação no spread |
| **Competência** | Mês a que o fato econômico pertence, independente do pagamento |
