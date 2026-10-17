# Contrato técnico — nível Alvo

Este documento complementa `PLANO.md` §6.5 e `CONTRATO_TECNICO_MINIMO.md`. Fixa as interfaces para A e B desenvolverem o Alvo em paralelo. Tudo que o contrato do Mínimo diz continua valendo, salvo onde este documento o estende explicitamente (§3.1 e §8). É decisão técnica de implementação; não representa novas respostas do financeiro. Regras de negócio ainda assumidas continuam identificadas como tais e devem ser registradas em `HIPOTESES.md`. Decisões deste contrato que precisam de confirmação estão reunidas na §10.

## 1. Entrega e responsabilidades

O comando passa a gerar, a partir dos arquivos originais, os **seis CSVs com conteúdo**: comissões de checkout **e** remessa, divergências de taxa, notas a emitir, lançamentos bancários classificados, pendências consolidadas e rastro.

| Responsável | Arquivos de sua responsabilidade | O que entrega ao outro |
|---|---|---|
| A | `src/regras/checkout.py` (completo), `src/regras/notas.py`, `src/ingest/orbe.py` e `src/ingest/taxas.py` (ajustes da §3.1), seção `checkout` e `notas` de `config/regras.yaml`, `config/lojistas.yaml` | `ResultadoCheckout` com divergências, e `NotaCalculada` das duas linhas de negócio, em memória |
| B | `src/core/contratos.py`, `src/core/saida.py` (ajuste da §6.4), `src/ingest/ponte.py`, `src/ingest/bancos.py`, `src/ingest/plano.py`, `src/regras/remessa.py`, `src/regras/classificacao.py`, `src/regras/pendencias.py`, `src/main.py`, seções `remessa` e `bancos` de `config/regras.yaml` | `ResultadoRemessa` e `ResultadoBancos` em memória; gravação, conservação e integração |

A escreve os testes de checkout, divergências de checkout e notas. B escreve os testes de remessa, bancos, formato, conservação e integração. Ambos revisam os resultados contra as entradas originais. `contratos.py` é de B; mudança de interface é combinada com A antes da edição.

**Fronteira (igual ao Mínimo):** os módulos de regras recebem registros e devolvem registros. Nenhum deles importa `saida.py` nem escreve arquivo. Só `main.py` fala com `Saida`.

**Dependência entre os dois lados, e só uma:** `notas.py` (A) consome `ComissaoCalculada` de CHECKOUT (de A) e de REMESSA (de B). A pode testá-lo antes de `remessa.py` existir usando uma comissão REMESSA sintética; o formato está na §3.

## 2. Convenções adicionais

Valem todas as do Mínimo §2 (Decimal, ISO, CNPJ/EC como `str`, taxas em pontos percentuais, `None` para ausente, `arquivo_origem` relativo à entrada). Acrescenta:

- **Sinal.** Estorno e reversão carregam valores **negativos** da fonte. A contribuição de comissão de uma linha negativa é negativa e entra no mesmo `Origem` do rastro, com sinal. Nunca tirar o módulo.
- **Uma linha, um destino.** Cada linha de entrada (Orbe, operação da Ponte, lançamento bancário) aparece **exatamente uma vez** em uma origem de comissão/classificação ou em uma pendência bloqueante. Pendência cadastral e sinalização não bloqueante são adicionais e não entram nessa contagem.
- **Valor da pendência bloqueante** de linha da Orbe: o **valor bruto assinado** da linha (estende o Mínimo §3 a todos os tipos, não só `VENDA`). Operação da Ponte: o `Spread R$` assinado. Lançamento bancário: o valor assinado. O motivo explicita a base.
- **`arquivo_origem` da Ponte e dos bancos:** a Ponte vem num anexo do e-mail; o arquivo de origem é o **`.eml`** (`03_email_ponte_cambio_relatorio_set2026.eml`), e a `ref_origem` é o `Nº Operação`. Para o repetido, ver §6.1. Bancos: `05a_...csv` e `05b_...ofx`.
- **Ordenação antes de emitir (B), estendida:** comissões por `(linha_negocio, cnpj)`, com CHECKOUT antes de REMESSA; isso mantém os ids `COM-0001…COM-0018` do Mínimo e acrescenta REMESSA depois. Divergências por `(linha_negocio, ref_origem)`. Notas por `(linha_negocio, tomador_cnpj)`. Lançamentos por `(banco, data, ref_origem)`. Pendências por `(tipo, arquivo da primeira origem, ref_origem)`, como no Mínimo. Os ids `PEN-` do Mínimo mudam porque entram tipos novos; isso é esperado.
- **Regras em configuração.** Nenhum CNPJ, EC, nome de lojista, nome de banco/parceiro, padrão de descrição ou conta contábil fica no código. Tudo isso vive em `config/` (§7). Vale o item 6 da definição de pronto de `PLANO.md` §6.2.

## 3. Tipos

### 3.1 Extensões de tipos existentes (B publica em `contratos.py`; A ajusta os leitores)

```python
class TaxasContrato(TypedDict):
    DEBITO: Decimal | None
    CREDITO_A_VISTA: Decimal | None
    CREDITO_2_6: Decimal | None
    CREDITO_7_12: Decimal | None
    PIX: Decimal | None
    ANTECIPACAO: Decimal | None          # NOVO: coluna "Antecipação" da planilha

class ContratoTaxa(TypedDict):
    ...                                  # campos do Mínimo, sem alteração
    spread_remessa_pct: Decimal | None   # NOVO: pontos percentuais; 1.50 = 1,50%
```

`ler_taxas` (A) passa a ler a coluna **Antecipação** (célula numérica ou texto `'2,10%'`, igual às demais faixas) e **Spread remessa** (fração na planilha, convertida com `pct(fracao=True)`). `spread_remessa_pct` é `None` quando a célula é vazia **ou** o texto `padrão`: os dois significam spread padrão (`HIPOTESES.md` pergunta 4, aberta). Não inventar valor. `ler_taxas` hoje não lê nenhuma das duas colunas; o Alvo depende disso.

`ler_orbe` já preserva `id_referencia` e `data_venda_original`; nas linhas de `ESTORNO` e `REVERSAO ANTECIPACAO` ambos vêm preenchidos (`data_venda_original` em ISO). Nas demais, `None`.

### 3.2 Checkout (A)

```python
class DivergenciaCalculada(TypedDict):
    cnpj: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    ref_origem: str                       # id_transacao ou Nº Operação
    taxa_contratada_pct: Decimal          # pontos percentuais
    taxa_aplicada_pct: Decimal            # pontos percentuais, mesma escala
    diferenca_brl: Decimal                # q2; positivo = lojista pagou a mais
    origens: list[Origem]                 # exatamente uma: (arquivo, ref_origem, diferenca_brl)
```

`ComissaoCalculada` (Mínimo §3) muda só em um ponto: `linha_negocio: Literal["CHECKOUT", "REMESSA"]`. A comissão de uma linha da Orbe continua com `origens` por linha e `contratos_utilizados`. Na REMESSA, `contratos_utilizados` pode ser `[]`.

`PendenciaCalculada` não muda de forma. O conjunto de tipos cresce (§3.6).

```python
class ResultadoCheckout(TypedDict):
    comissoes: list[ComissaoCalculada]            # só CHECKOUT
    divergencias: list[DivergenciaCalculada]      # NOVO; só CHECKOUT
    pendencias: list[PendenciaCalculada]
    resumo: ResumoCheckout
```

```python
class ResumoCheckout(TypedDict):
    total_orbe: int
    por_tipo: dict[str, dict[str, int]]    # NOVO: tipo -> {"total","processadas","bloqueadas"}
    linhas_processadas: int                # NOVO: Σ por_tipo[*].processadas
    linhas_bloqueadas: int                 # NOVO
    vendas_total: int                      # mantidos do Mínimo
    vendas_processadas: int
    vendas_bloqueadas: int
    fora_escopo_por_tipo: dict[str, int]   # no Alvo: sempre {} (tipo desconhecido vira pendência)
    contagens_por_arquivo: dict[str, int]
```

Invariante: `linhas_processadas + linhas_bloqueadas == total_orbe`.

### 3.3 Notas (A)

```python
class NotaCalculada(TypedDict):
    tomador_cnpj: str
    tomador: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    valor_brl: Decimal                     # q2
    discriminacao: str
    origens: list[Origem]                  # as MESMAS origens da(s) comissão(ões) que a compõem
    pendencias: list[PendenciaCalculada]   # NF não emitida por saldo <= 0
```

Para cada comissão CHECKOUT, uma nota; para o conjunto das comissões REMESSA, **uma** nota. O valor da nota é a soma exata das origens (nenhum ajuste), então `Saida.emitir` fecha sem resíduo.

### 3.4 Remessa (B)

```python
class OperacaoPonte(TypedDict):
    num_operacao: str                      # 'PC-0926-0002'
    linha: int                             # linha física na aba Operações (6..238)
    data_contratacao: str                  # ISO; normalize.data() lida com serial Excel
    data_liquidacao: str                   # ISO
    cnpj: str                              # 14 dígitos, normalizado
    cliente_origem: str                    # truncado em 20 caracteres; nunca é chave
    moeda: str
    valor_me: Decimal
    taxa_cliente: Decimal
    ptax: Decimal
    valor_brl: Decimal
    spread_brl: Decimal                    # "Spread R$" REALIZADO; mantém o sinal
    spread_pct: Decimal                    # pontos percentuais (a fonte vem em fração)
    spread_estimado_d1_brl: Decimal | None # lido, nunca usado como base
    iof_brl: Decimal | None
    status_compliance: str
    observacao: str | None
    arquivo_origem: str                    # o .eml
    ref_origem: str                        # igual a num_operacao

class RodapePonte(TypedDict):
    total_operacoes: int                   # 233
    spread_total_brl: Decimal              # 78073.59

class RelatorioPonte(TypedDict):
    operacoes: list[OperacaoPonte]         # todas as linhas, na ordem do arquivo, inclusive repetida
    rodape: RodapePonte
    competencia: str | None                # 'AAAA-MM', lida do cabeçalho "Competência: 09/2026"
    arquivo_origem: str

class ResultadoRemessa(TypedDict):
    comissoes: list[ComissaoCalculada]     # uma por CNPJ, linha_negocio REMESSA
    divergencias: list[DivergenciaCalculada]
    pendencias: list[PendenciaCalculada]
    resumo: ResumoRemessa

class ResumoRemessa(TypedDict):
    linhas_relatorio: int                  # 233
    operacoes_distintas: int               # 232
    validas: int                           # 228: entram na comissão
    bloqueadas: int                        # contestações, repetidas, cadastro etc.
    sem_spread_contratado: int             # 51: sem divergência calculada (spread padrão ou ausente)
    reconciliacao: dict[str, Decimal]      # ver §6.1
```

### 3.5 Bancos (B)

```python
class LancamentoBancario(TypedDict):
    banco: Literal["AURORA", "MERIDIANO"]
    ref_origem: str                        # Aurora 'L9'; Meridiano FITID
    data: str                              # ISO
    descricao: str                         # Lançamento (Aurora) ou MEMO (Meridiano), como vem
    valor: Decimal                         # assinado: saída negativa
    arquivo_origem: str

class ContaContabil(TypedDict):
    codigo: str
    descricao: str
    aceita_lancto: bool

class LancamentoClassificado(TypedDict):
    banco: str
    ref_origem: str
    data: str
    descricao: str
    valor: Decimal
    conta_codigo: str
    metodo: Literal["REGRA", "IA", "HUMANO"]   # só REGRA e HUMANO são usados; IA existe só no enum do enunciado
    confianca: Decimal                     # 1 para REGRA; 0 para HUMANO
    regra_id: str | None                   # auditoria; NÃO vai ao CSV
    origens: list[Origem]                  # uma: (arquivo_origem, ref_origem, valor)

class ResultadoBancos(TypedDict):
    lancamentos: list[LancamentoClassificado]
    pendencias: list[PendenciaCalculada]
    resumo: dict   # total_aurora, total_meridiano, por_regra: dict[str,int], humano: int
```

### 3.6 Resultado integrado (B)

```python
class ResultadoFechamento(TypedDict):
    checkout: ResultadoCheckout
    remessa: ResultadoRemessa
    bancos: ResultadoBancos
    notas: list[NotaCalculada]
    pendencias: list[PendenciaCalculada]   # consolidadas, validadas
```

**Tipos de pendência novos** (além dos sete do Mínimo). `quem_decide` continua restrito a `Financeiro` e `Comercial` neste nível; ampliar a lista é escopo do Extra (E2).

| Tipo | Quem decide | Origem | Quando |
|---|---|---|---|
| `LANCAMENTO_INVALIDO` | Financeiro | A | Linha não-`VENDA` da Orbe com dado inválido (§5.1) ou `tipo_lancamento` desconhecido |
| `NF_NAO_EMITIDA` | Financeiro | A | Comissão de CHECKOUT com saldo ≤ 0 |
| `CONTESTACAO` | Financeiro | B | Operação da Ponte com spread negativo |
| `OPERACAO_REPETIDA` | Financeiro | B | Mesmo `Nº Operação` em mais de uma linha; entra na lista de correção da Ponte |
| `OPERACAO_POSSIVEL_DUPLICIDADE` | Financeiro | B | Mesmo CNPJ/valor/moeda/data com `Nº Operação` diferente; **só sinaliza**, a operação continua na comissão |
| `OPERACAO_COM_RESSALVA` | Financeiro | B | Só se `aprovado_com_ressalva_entra: false`; bloqueia a operação |
| `RODAPE_DIVERGENTE` | Financeiro | B | Rodapé da Ponte ≠ soma/contagem das linhas |
| `LANCAMENTO_NAO_CLASSIFICADO` | Financeiro | B | Nenhuma regra bancária casou |
| `CREDITO_NAO_IDENTIFICADO` | Financeiro | B | Regra marcada como pendência (Pix sem identificação) |
| `TRANSFERENCIA_SEM_CONTRAPARTIDA` | Financeiro | B | Transferência entre contas sem lançamento correspondente no outro banco |

`CADASTRO_NAO_RESOLVIDO` (Financeiro) também é usado pela Remessa quando o CNPJ da Ponte não existe na planilha.

## 4. Interfaces dos módulos

```python
# A
ler_taxas(caminho: Path, arquivo_origem: str | None = None) -> list[ContratoTaxa]   # estendido (§3.1)
calcular_checkout(transacoes, contratos, cadastro, competencia, regras) -> ResultadoCheckout
gerar_notas(
    comissoes: list[ComissaoCalculada],        # CHECKOUT (A) + REMESSA (B), juntas
    competencia: str,
    regras: dict,
) -> list[NotaCalculada]

# B
ler_ponte(caminho: Path) -> RelatorioPonte                    # .eml -> anexo xlsx, em memória
calcular_remessa(
    relatorio: RelatorioPonte,
    contratos: list[ContratoTaxa],             # fornecem spread contratado e nome por CNPJ
    cadastro: dict[str, dict[str, str]],       # EC -> {cnpj, lojista}; nome tem prioridade
    competencia: str,
    regras: dict,
) -> ResultadoRemessa
ler_aurora(caminho: Path, regras: dict) -> list[LancamentoBancario]   # offset de ref (§7)
ler_meridiano(caminho: Path) -> list[LancamentoBancario]
ler_plano(caminho: Path) -> list[ContaContabil]               # ISO-8859-1
classificar_lancamentos(
    lancamentos: list[LancamentoBancario],
    plano: list[ContaContabil],
    regras: dict,
) -> ResultadoBancos
validar_pendencia(pendencia) -> None                          # já existe; aceita os tipos da §3.6
run(entrada: Path, competencia: str, saida: Path,
    regras_path: Path, cadastro_path: Path) -> ResultadoFechamento
```

Reutilizar `Saida`, `Origem`, `SaidaError`, `conferir_diretorio`. Não criar escritor novo. Erro de execução (arquivo ausente ou ilegível, configuração inválida, conta fora do plano, transação fora da competência, id duplicado) levanta exceção. Problema de negócio vira pendência.

## 5. Checkout completo (A)

### 5.1 Regra por tipo de lançamento

A taxa vem sempre do **contrato**, nunca da taxa aplicada pela Orbe. Comissão da linha = `q2(valor_bruto × taxa_contratada / 100)`, com o sinal do `valor_bruto`. O total do lojista é a soma das linhas arredondadas (`HIPOTESES.md` §2). `ROUND_HALF_UP` arredonda para longe do zero, então a contribuição de uma linha negativa é exatamente o oposto da positiva de mesmo módulo.

| Tipo | Taxa | Data de vigência | Faixa | Sinal esperado |
|---|---|---|---|---|
| `VENDA` | faixa da modalidade/parcelas (como no Mínimo) | `data_movimento` | modalidade e parcelas da linha | bruto > 0 |
| `ANTECIPACAO` | `ANTECIPACAO` do contrato | `data_movimento` | sem modalidade/parcelas (vazio estrutural, não é erro) | bruto > 0 |
| `ESTORNO` | faixa da modalidade/parcelas **do estorno** | **`data_venda_original`** (CONFIRMADO, P2) | todos os 69 estornos têm modalidade e parcelas | bruto < 0 |
| `REVERSAO ANTECIPACAO` | `ANTECIPACAO` do contrato | **`data_venda_original`** (data da antecipação desfeita) | sem modalidade/parcelas | bruto < 0 |

Consequências, todas obrigatórias:

1. **Mês de competência.** `data_movimento` de toda linha deve estar na competência (erro explícito, como no Mínimo). Estorno de venda de agosto lançado em setembro entra na comissão de **setembro**; agosto não é reaberto. A data da venda original só escolhe a taxa e a vigência.
2. **Estorno cuja venda original não está no arquivo** (9 estornos, todos de agosto) é resolvido por `data_venda_original` + EC, nunca ignorado. Não é necessário achar a original para calcular; a comissão depende só do EC, da data original e da modalidade/parcelas do próprio estorno.
3. **Reversão anula só a taxa da antecipação que reverte.** A contribuição é `q2(bruto_negativo × taxa_antecipacao / 100)`; não toca no MDR da venda que originou a antecipação.
4. **Consistência com a original, quando ela está no arquivo** (`id_referencia` resolvido; 69 casos hoje): o EC da linha deve ser igual ao da original e o tipo da original deve ser compatível (`ESTORNO`→`VENDA`, `REVERSAO ANTECIPACAO`→`ANTECIPACAO`). Falha → pendência `LANCAMENTO_INVALIDO` bloqueante. Não exigir valor oposto (estorno parcial é possível).
5. **Estorno em dobro:** uma segunda linha negativa com o mesmo `id_referencia` vira `LANCAMENTO_INVALIDO` bloqueante com motivo claro. Hoje não ocorre (`HIPOTESES.md` §3.5); é guarda para outubro.
6. **Sinal inconsistente** (venda ≤ 0, estorno/reversão ≥ 0, antecipação ≤ 0) → `VENDA_INVALIDA` para venda, `LANCAMENTO_INVALIDO` para os demais. `data_venda_original` ausente em estorno/reversão, ou posterior à `data_movimento` → `LANCAMENTO_INVALIDO`.
7. **Tipo desconhecido** (`tipo_lancamento` fora dos quatro) → `LANCAMENTO_INVALIDO`. Nada some em silêncio; por isso `fora_escopo_por_tipo` fica vazio.
8. **Linha bloqueada com contrato ausente, inativo, ambíguo ou sem cobertura** segue o roteamento do Mínimo (`CONTRATO_*`, `CADASTRO_NAO_RESOLVIDO`, `ec_sem_cadastro` da configuração), agora para todos os tipos. A pendência rastreia o bruto assinado da linha. Para estorno e reversão a vigência testada é a da data original. Atlas continua `CONTRATO_AUSENTE`/Comercial.
9. **Bridge:** crédito à vista usa 2,59% em venda até 14/09 e 2,19% desde 15/09. **Estorno em ou após 15/09 de venda anterior a 15/09 usa 2,59%**, a taxa da data da venda original. Este é o teste de A2 que distingue as duas datas.
10. `taxas_pct[ANTECIPACAO] is None` bloqueia a linha com `TAXA_AUSENTE`.

`comissao_brl` do lojista pode ser negativo ou zero (só estornos no mês). A linha de comissão continua publicada; a consequência fiscal está em §5.3.

### 5.2 Divergências de checkout

Uma `DivergenciaCalculada` por linha **processada** (com contrato) em que:

- `taxa_aplicada_pct != taxa_contratada_pct` (comparação entre **taxas**, mesma escala, pontos percentuais; nunca o `valor_taxa` truncado da Orbe), **e**
- `abs(q2(valor_bruto × (aplicada − contratada) / 100)) >= regras.checkout.limiar_divergencia_brl`.

`diferenca_brl = q2(valor_bruto × (aplicada − contratada) / 100)`. **Positivo = o lojista pagou a mais.** O sinal acompanha o bruto: estorno de uma venda divergente gera diferença **negativa** (devolução do excesso). Isso é intencional e aparece no rastro 1:1 (`origens = [Origem(arquivo, id_transacao, diferenca_brl)]`). O CSV não tem coluna `tipo_lancamento`; o par venda/estorno se identifica pelo `ref_origem`.

Linhas bloqueadas não geram divergência (sem contrato não há taxa contratada); elas já estão em pendência. As cinco taxas fora da aba vigente (0,99; 1,99; 3,99; 4,09; 4,49) terminam todas ou em divergência ou em pendência de lojista sem contrato (4 são da Atlas, 4,09 é da Rota Global). Nenhuma é silenciada.

**Divergência não é restituição.** Se a diferença deve ser devolvida ao lojista, a pergunta 1 não respondeu; o Alvo só reporta.

### 5.3 Notas fiscais (A)

`gerar_notas` recebe as comissões CHECKOUT e REMESSA e devolve:

- **CHECKOUT:** uma nota por comissão com `comissao_brl > 0`. `tomador` = o lojista, `tomador_cnpj` = o CNPJ do cadastro (`checkout.nf_tomador: lojista`, **[ASSUMIDO]**, P16). O valor é a comissão **líquida** do lojista: MDR + antecipação − estornos − reversões, tudo na mesma nota (`antecipacao_mesma_nota: true`, CONFIRMADO P3). `origens` = as mesmas origens da comissão.
- **Saldo ≤ 0:** não gera nota; devolve em `pendencias` uma `NF_NAO_EMITIDA` (Financeiro) com `ref_origem` = CNPJ do lojista, `valor_brl` = saldo e as mesmas origens da comissão (a soma do rastro fecha com o saldo).
- **Atlas** (e qualquer lojista sem nenhuma linha processada): não tem comissão, portanto não tem nota. A explicação é a pendência por linha já existente (`CONTRATO_AUSENTE`/Comercial). Não criar `NF_NAO_EMITIDA` adicional para quem não tem comissão: duplicaria o alarme.
- **REMESSA:** **uma única** nota. `tomador_cnpj` e `tomador` vêm de `regras.remessa.nf_tomador` (Ponte Câmbio, CNPJ 75374179000146, do e-mail). `valor_brl` = Σ das comissões REMESSA = Σ das origens; `origens` = a união ordenada das origens de todas as comissões REMESSA. Sem nota por lojista. Se a soma for ≤ 0, `NF_NAO_EMITIDA` do mesmo modo.
- **`discriminacao`:** gerada de modelos em `regras.yaml` (§7), com `{competencia}` e `{n_transacoes}` (número de origens). Nunca vazia.

Invariantes testados: `Σ NF CHECKOUT = Σ comissões CHECKOUT` (exceto saldos ≤ 0), `NF REMESSA = Σ comissões REMESSA`.

## 6. Remessa e bancos (B)

### 6.1 Remessa: regras

Lojista identificado **só por CNPJ normalizado**, nunca pelo nome truncado da Ponte. Nome exibido: o do cadastro mestre (CNPJ da comissão presente em algum EC de `lojistas.yaml`); senão o da planilha de taxas, na primeira linha daquele CNPJ. O lojista de remessa **não precisa ter EC**: Kiwi, Novo Horizonte, Nórdica e Ponte Aérea têm operações na Ponte e entram na comissão mesmo sem EC. (A Kiwi tem checkout bloqueado e remessa faturável.)

Cada linha do relatório recebe **um** destino. Aplicar nesta ordem, parando na primeira que casar:

1. **Repetida** (mesmo `Nº Operação` já visto): conta **uma vez**; a primeira ocorrência segue o fluxo normal. As ocorrências seguintes viram `OPERACAO_REPETIDA` (Financeiro), com `valor_brl` = `Spread R$` da linha excedente, `origens = [Origem(eml, "<Nº>#<k>", spread)]`, onde `k` = 2, 3... é a ordem da ocorrência. Sem duplicar o `ref_origem` no rastro, e o prefixo `<Nº>` continua apontando a operação real. Hoje: `PC-0926-0162` (linhas físicas 76 e 77, spread R$ 821,88).
2. **CNPJ fora da planilha de taxas:** `CADASTRO_NAO_RESOLVIDO` (Financeiro), `valor_brl` = `Spread R$`. Hoje: nenhuma.
3. **Spread negativo:** `CONTESTACAO` (Financeiro), `valor_brl` = `Spread R$` (negativo), motivo "trava de 2 horas excedida", e menciona o prazo de 5 dias úteis do e-mail (CONFIRMADO, P9). **Fora da comissão, fora da nota, fora de divergências.** Hoje: 4 (`PC-0926-0210`, `-0326`, `-0491`, `-0545`).
4. **Status `APROVADO C/ RESSALVA`:** entra, se `aprovado_com_ressalva_entra: true` (**[ASSUMIDO]**, P10; 16 operações). Se `false`, `OPERACAO_COM_RESSALVA` bloqueante.
5. **Válida:** comissão `q2(spread_brl × participacao_tarvo)`, com `participacao_tarvo = 0.5` da configuração. Base é o `Spread R$` **realizado**, nunca o estimado D-1 (CONFIRMADO, P6).

**Sinalização sem bloqueio:** duas linhas com `Nº Operação` diferentes e mesmos CNPJ, `Valor ME`, `Moeda` e `Data Contratação` geram `OPERACAO_POSSIVEL_DUPLICIDADE` na segunda, **sem** retirá-la da comissão (**[ASSUMIDO]**, só sinalizar). Linha repetida da regra 1 não reaparece aqui. Hoje: nenhuma além da própria `PC-0926-0162`, que é a regra 1.

**Arredondamento (§10, decisão 1):** a comissão é arredondada **por operação**, como no checkout; a comissão do lojista é a soma das linhas arredondadas e o rastro lista cada operação com a contribuição `q2`. `origens` por comissão ordenadas por `ref_origem`.

**Rodapé:** `total_operacoes` e `spread_total_brl` do rodapé devem igualar a contagem e a soma de **todas as linhas lidas** (incluindo a repetida e os negativos, como o arquivo faz). Diferença → pendência `RODAPE_DIVERGENTE` (Financeiro), `ref_origem` = `Operações!rodape`, `valor_brl` = `Σ linhas − rodapé`, uma origem com esse valor (a evidência do rodapé está no `.eml`). Hoje: 233 e R$ 78.073,59 conferem; a pendência não existe.

**Reconciliação** (`resumo.reconciliacao`, impressa pelo comando e usada em `HIPOTESES.md`):

```
rodape_spread_total_brl         78073.59
(−) repetida                      −821.88
(−) negativos                    −(−1834.05)   -> soma +1834.05
= base_comissao_brl             79085.76
```

Os negativos são subtraídos e portanto **aumentam** a base. Cada parcela é listada com os `Nº Operação` envolvidos.

**Conservação:** `linhas_relatorio = validas + bloqueadas`, onde as bloqueadas incluem repetidas, contestações, cadastro e ressalva (quando bloqueia). Hoje: 233 = 228 + 5 (4 contestações + 1 repetida).

### 6.2 Divergências de remessa

Para cada operação **válida** de lojista com `spread_remessa_pct` numérico:

- `taxa_contratada_pct = spread_remessa_pct`; `taxa_aplicada_pct = spread_pct` da operação (já em pontos percentuais).
- Há divergência só se `abs(taxa_aplicada_pct − taxa_contratada_pct) > tolerancia`, com `tolerancia = 0.001` ponto percentual. É a precisão de cinco casas **da fração** que o relatório traz (`regras.remessa.precisao_spread_pct: 0.00001` está em fração; converter multiplicando por 100). Esta conversão é o ponto mais fácil de errar: `0.00001` em fração é `0.001` em pontos percentuais.
- `diferenca_brl = q2(spread_brl − valor_me × ptax × taxa_contratada_pct / 100)`: o **valor cheio**, não a metade (CONFIRMADO). A base `Spread R$` é a mesma da comissão.
- Uma operação com `Spread %` igual ao contratado e diferença de ~R$ 0,03 só por arredondamento **não** é divergência (critério decidido pelo time, `HIPOTESES.md` §2).
- Operação de lojista com `spread_remessa_pct is None` (padrão ou vazio): comissão calculada normalmente, **divergência não calculada**, sem pendência. A contagem vai em `resumo.sem_spread_contratado` e o fato em `HIPOTESES.md` (pergunta 4). Hoje: 51 operações (Kiwi, Ponte Aérea, Canguru).
- Operação bloqueada não gera divergência.
- `cnpj` da divergência é o do lojista; `linha_negocio = "REMESSA"`; `ref_origem = Nº Operação`; rastro 1:1 com `Origem(eml, Nº Operação, diferenca_brl)`.

### 6.3 Bancos: leitura, classificação e pendências

**Leitores.** Um por fonte, encoding explícito.

- **Aurora** (UTF-8): cabeçalho achado pelo conteúdo (`Data;Lançamento;Documento;...`), não pela linha 7. Lançamentos são as linhas com data válida **depois** do cabeçalho, excluindo `SALDO ANTERIOR`, `SALDO FINAL` e o aviso. Valor em pt-BR com ponto de milhar (`normalize.brl`). `ref_origem = f"L{linha_fisica + offset}"`, onde `offset` vem de `regras.bancos.aurora_ref_offset` (`0` = linha física, `L9…L92`, padrão; `1` = convenção `L10…` do enunciado). A pergunta do `ref_origem` Aurora segue aberta e não bloqueia: muda-se um número de configuração.
- **Meridiano** (CP1252): regex sobre `<STMTTRN>…</STMTTRN>` (SGML sem fechamento; não é XML). `ref_origem = FITID`; valor com **ponto decimal** (`TRNAMT`); data de `DTPOSTED` (os 8 primeiros dígitos); `MEMO` como descrição. Ignorar `LEDGERBAL`.
- **Plano de contas** (ISO-8859-1): `ler_plano` devolve todas as contas; só `ACEITA_LANCTO = "S"` pode receber lançamento.

Datas fora da competência são erro de execução, como na Orbe.

**Classificação.** Regras em `regras.bancos.regras` (§7), em **lista ordenada**; a primeira que casa vence. Casamento sobre a descrição normalizada (sem acento, maiúsculas, espaços colapsados). Ordem importa: `PIX ENVIADO CONTABILIDADE` vem **antes** de `PIX ENVIADO <lojista>`. Cada regra tem `id`, `banco` (`AURORA`, `MERIDIANO` ou `*`), `padrao` (regex), `conta` e, opcionalmente, `pendencia`.

- Linha que casa: `metodo = REGRA`, `confianca = 1`, `conta_codigo` da regra, `regra_id` preenchido.
- `conta_codigo` de toda linha deve estar entre as contas com `ACEITA_LANCTO = S`. Conta de regra fora do plano é **erro de execução** (configuração inválida), não pendência.
- Linha sem regra: `metodo = HUMANO`, `confianca = 0` e pendência `LANCAMENTO_NAO_CLASSIFICADO`. Para o `conta_codigo`, ver §10, decisão 2.
- Regra com `pendencia`: classifica por regra **e** abre a pendência indicada. Hoje: o Pix `SEM IDENTIFICACAO` (`CREDITO_NAO_IDENTIFICADO`, R$ 7.350,00, 16/09, CNPJ 38686002000180 no texto) vai para 1.1.09.002 com `metodo = REGRA` e a pendência. A pendência tem `valor_brl` = valor do lançamento e a mesma origem.
- **Folha e impostos de agosto:** `regras.bancos.folha_e_impostos_de_08` escolhe entre `baixa_provisao` (salários 2.1.04.001, INSS 2.1.04.002, FGTS 2.1.04.003) e `despesa`. No modo `despesa` só há conta para salários (4.1.01); o plano não tem conta de despesa de INSS nem de FGTS, então essas duas regras ficam com `conta: null` e **viram `LANCAMENTO_NAO_CLASSIFICADO`**, não são inventadas. Marcado **[ASSUMIDO]** (P12).
- **Contrapartida de transferência entre contas** (regra com `contrapartida`): cada saída `TRANSF ENTRE CONTAS` do Aurora procura, no Meridiano, uma entrada `TED RECEBIDA TARVO … MESMA TITULARIDADE` de **mesmo valor absoluto** com data entre a do Aurora e `+ janela_contrapartida_dias` (padrão 3). Cada entrada casa no máximo uma vez, por ordem de data. Sem contrapartida → `TRANSFERENCIA_SEM_CONTRAPARTIDA` (Financeiro), valor assinado do lançamento sem par. Hoje: 4 saídas, 3 casam (R$ 350.000 em 02/09, R$ 420.000 em 11/09, R$ 380.000 em 21/09) e **R$ 300.000 de 30/09 não tem par** (pergunta 15, aberta, lote 3). O lançamento continua classificado por regra em 1.1.09.001; a pendência é adicional.
- **Repasse da Ponte de 08/2026** (R$ 61.884,12 em 04/09) vai para 1.1.03.002 por regra, **[ASSUMIDO]** competência de agosto (P14). Não é pendência.

**Conservação:** `total_aurora + total_meridiano = len(lancamentos)`; cada lançamento aparece **uma vez** em `lancamentos` e, quando pendente, também em `pendencias` (a pendência é adicional, não substitui a linha).

## 7. Configuração

`config/regras.yaml` já contém as chaves abaixo; preservar o que existe. **A** completa `checkout` e `notas`; **B** completa `remessa` e `bancos`. Parâmetros numéricos do YAML chegam como `float`: converter com `Decimal(str(valor))` antes de calcular.

```yaml
notas:                                    # A
  discriminacao_checkout: "Comissão de checkout (MDR e antecipação, líquida de estornos), competência {competencia}, {n_transacoes} transações"
  discriminacao_remessa: "Participação de 50% no spread de câmbio, competência {competencia}, {n_transacoes} operações"

remessa:                                  # B (chaves existentes)
  participacao_tarvo: 0.5
  precisao_spread_pct: 0.00001            # FRAÇÃO; o código converte para pontos percentuais
  aprovado_com_ressalva_entra: true
  spread_padrao: null                     # P4 aberta
  nf_tomador: {cnpj: "75374179000146", nome: "Ponte Câmbio"}

bancos:                                   # B
  folha_e_impostos_de_08: baixa_provisao  # ASSUMIDO (P12)
  aurora_ref_offset: 0                    # 0 = L9 (linha física); 1 = convenção L10 do enunciado
  janela_contrapartida_dias: 3            # DECIDIDO (§10)
  regras:                                 # lista ORDENADA; primeira que casa vence
    - {id: pix_contabilidade, banco: AURORA, padrao: '^PIX ENVIADO CONTABILIDADE', conta: "4.2.06"}
    - {id: pix_sem_identificacao, banco: AURORA, padrao: '^PIX RECEBIDO .*SEM IDENTIFICACAO',
       conta: "1.1.09.002", pendencia: CREDITO_NAO_IDENTIFICADO}
    # ... demais regras da tabela de PLANO.md §4 (Lançamentos bancários), uma por linha
```

A lista completa de regras vem da tabela de `PLANO.md` §4 e foi verificada contra os dados (as 184 linhas casam; contagens por padrão confirmadas: Aurora 84, Meridiano 100). Contagens por regra esperadas:

| Banco | Regra (conta) | Qtd |
|---|---|---|
| Aurora | `TED RECEBIDA … ORBE` (1.1.03.001) | 21 |
| Aurora | `PIX ENVIADO <lojista>` (2.1.01.001) | 44 |
| Aurora | `TRANSF ENTRE CONTAS` (1.1.09.001) | 4 |
| Aurora | `PIX ENVIADO CONTABILIDADE` (4.2.06) | 1 |
| Aurora | `DEVOLUCAO PIX` (2.1.01.002) | 1 |
| Aurora | `PIX RECEBIDO … SEM IDENTIFICACAO` (1.1.09.002 + pendência) | 1 |
| Aurora | `TAR …` (4.2.01) | 2 |
| Aurora | Condomínio / AWS / Google (4.2.02 / .03 / .04) | 1 + 1 + 1 |
| Aurora | DARF PIS / COFINS / IRRF, ISS (2.1.03.001 / .002 / .004 / .003) | 1 cada |
| Aurora | Salários / GPS INSS / GRF FGTS (2.1.04.001 / .002 / .003) | 1 cada |
| Meridiano | `PIX RECEB <lojista>` (2.1.02.001) | 64 |
| Meridiano | `TED ENVIADA PONTE … LIQ OPERACOES` (2.1.02.001, **[ASSUMIDO]**) | 21 |
| Meridiano | `TED RECEBIDA TARVO … MESMA TITULARIDADE` (1.1.09.001) | 3 |
| Meridiano | `TED RECEB PONTE … REPASSE COMISSAO` (1.1.03.002, **[ASSUMIDO]**) | 1 |
| Meridiano | Aplicação e resgate CDB (1.1.02.001) | 3 + 3 |
| Meridiano | Rendimento / IOF / Seguro (3.2.01 / 4.3.01 / 4.2.05) | 1 cada |
| Meridiano | `TARIFA …` (4.2.01) | 2 |

## 8. Saídas e execução (B)

CSV UTF-8, `;`, dinheiro com ponto e duas casas, CNPJ como texto, enums válidos, como no Mínimo §7. As colunas dos seis arquivos são as de `ESQUEMAS` em `saida.py` (já implementadas, incluindo a coluna opcional `sugestao` de pendências, que no Alvo não é preenchida).

`main.run` estende o fluxo do Mínimo:

1. Descobrir um arquivo por padrão: `02_*.xlsx`, `03_*.eml`, `04_*.csv`, `05a_*.csv`, `05b_*.ofx`, mais `01_orbe_*.csv` (obrigatório) e `06_orbe_ajustes_*.csv` (opcional), como no Mínimo §10. Ausência ou ambiguidade de qualquer um dos obrigatórios é erro de execução.
2. Ler tudo; validar competência (Orbe, bancos e `Data Contratação` da Ponte). A `Data Liquidação` pode cair no mês seguinte (seis operações em outubro) e **não** é validada.
3. Calcular checkout (A), remessa (B), bancos (B); passar as comissões CHECKOUT + REMESSA a `gerar_notas` (A).
4. Consolidar pendências: checkout + notas + remessa + bancos. Chamar `validar_pendencia` em todas.
5. **Conferir conservação** (generalização de `_conferir_conservacao`): cada linha da Orbe, da Ponte e dos bancos aparece uma vez; `Σ origens` de cada comissão, divergência, nota, lançamento e pendência fecha com o valor; uma comissão por `(cnpj, linha_negocio)`; Σ NF = Σ comissões nas condições do §5.3. Qualquer falha é erro de execução e **nada é publicado**.
6. Ordenar (§2), emitir, gravar em pasta temporária, publicar em `--saida` só após reconferência em disco (já implementado).
7. Imprimir o resumo de conservação: Orbe por tipo e por arquivo; remessa com a reconciliação; bancos por banco e por regra; contagem de pendências por tipo e por `quem_decide`.

B remove `origens`, `contratos_utilizados` e `regra_id` antes de emitir. Colunas extras continuam rejeitadas por `emitir()`.

## 9. Números de referência (data pack de setembro)

Recálculo **independente** (direto da Orbe, da planilha, do anexo da Ponte e dos extratos, sem usar o código do projeto). São **verificações do data pack, não constantes do algoritmo**; o número final sai de `saida/`. Marcar como preliminar até a revisão cruzada.

**Checkout** (soma das linhas arredondadas):

| Tipo | Processadas | Bloqueadas | Comissão (R$) | Bruto bloqueado (R$) |
|---|---|---|---|---|
| `VENDA` | 1.574 | 267 | 180.006,23 | 980.352,88 |
| `ESTORNO` | 57 | 12 | −7.186,48 | −25.597,01 |
| `ANTECIPACAO` | 30 | 8 | 23.105,36 | 351.726,52 |
| `REVERSAO ANTECIPACAO` | 5 | 4 | −4.460,77 | −200.542,38 |
| **Total** | **1.666** | **291** | **191.464,34** | |

`1.666 + 291 = 1.957` linhas da Orbe (1.943 + 14). As 267 vendas e a comissão de vendas (R$ 180.006,23) coincidem com o Mínimo.

**Divergências de checkout:** 92 linhas, sendo 88 vendas (soma R$ 1.674,67) e 4 estornos, com **diferença líquida de R$ 1.576,23**. Rota Global: 87 linhas; Bridge: 5. Antecipações e reversões: nenhuma.

**Remessa:** 233 linhas = 228 válidas + 4 contestações + 1 repetida. 14 CNPJs distintos, todos na planilha. Base da comissão R$ 79.085,76. Comissão com arredondamento por operação: **R$ 39.543,45** (a conta "50% × Σ" daria R$ 39.542,88; diferença de R$ 0,57, ver §10 decisão 1). Divergências: **41 operações, soma R$ 1.419,05**; 51 operações sem spread contratado numérico (sem divergência calculada). Seis operações com `Data Liquidação` em outubro, todas com `Data Contratação` em setembro.

**Bancos:** 84 Aurora + 100 Meridiano = 184, todas classificadas por regra (`HUMANO = 0`). Pendências: 1 `CREDITO_NAO_IDENTIFICADO` (R$ 7.350,00) e 1 `TRANSFERENCIA_SEM_CONTRAPARTIDA` (−R$ 300.000,00).

**Notas:** 18 de CHECKOUT (uma por lojista com comissão) + 1 de REMESSA. Σ NF CHECKOUT esperada R$ 191.464,34 **se nenhum dos 18 lojistas tiver saldo ≤ 0** (a verificar); NF REMESSA R$ 39.543,45.

## 10. Decisões que precisam de confirmação antes de codar

1. **Arredondamento da remessa: por operação (recomendado) ou agregado.** O contrato do Mínimo §6 e `HIPOTESES.md` §2 fixam arredondamento por transação. Aplicado à remessa, `50% × Spread R$` de 228 operações gera R$ 39.543,45 em vez de R$ 39.542,88 (+R$ 0,57), porque metade das operações tem centavos ímpares que o `ROUND_HALF_UP` sobe. A alternativa (arredondar só o total) exigiria linha de ajuste no rastro, que o contrato proíbe. Recomendação: por operação, registrar em `HIPOTESES.md` como **[DECIDIDO]** e avisar que a NF REMESSA será R$ 39.543,45. A primeira versão de `PLANO.md` §6.5 A4 e `HIPOTESES.md` §3.4 citam 39.542,88 como preliminar; atualizar quando decidido.
2. **`conta_codigo` de lançamento `HUMANO`.** O esquema atual exige `conta_codigo` não vazio. Linha sem regra não tem conta. Proposta: B relaxa a validação em `saida.py` só quando `metodo = HUMANO` (aceita vazio; `confianca = 0`). Alternativa: uma conta de trânsito configurável, mas o plano só tem uma conta "não identificada" para créditos. Hoje nenhum lançamento cai aqui; o teste é sintético. Conferir no enunciado se `conta_codigo` vazio é aceito.
3. **Tolerância do spread em pontos percentuais.** `precisao_spread_pct: 0.00001` está em fração; o contrato interno é pontos percentuais. Recomendação: manter a chave como está e converter no código (`× 100`), testando com a operação de ~R$ 0,03.
4. **Janela de contrapartida de transferência:** `janela_contrapartida_dias: 3`. Os três pares do data pack batem no mesmo dia; o parâmetro só precisa existir.
5. **`ref_origem` da operação repetida:** `PC-0926-0162#2`. É a única forma de ter rastro sem duplicar um `ref_origem` já usado na comissão. Alternativa: usar a linha física (`Operações!L77`). Combinar entre A e B porque o rastro e a lista de correção da Ponte dependem disso.

## 11. Como começar em paralelo

1. **B publica `contratos.py`** com os tipos das §3.1 a §3.6 (e o ajuste da §10, decisão 2, se aprovado). Sem isso A não consegue tipar `divergencias` nem `NotaCalculada`.
2. **A ajusta `ler_taxas`** para ler Antecipação e Spread remessa (§3.1). B depende disso para a remessa. É a primeira entrega e deve sair antes das 13h45.
3. **A: ordem sugerida.** (a) Estorno e antecipação/reversão em `calcular_checkout`, com os testes de Bridge e de estorno de agosto. (b) Divergências de checkout, com o teste de arredondamento. (c) `notas.py`, usando comissão REMESSA sintética. Cada item é testável sem o outro lado.
4. **B: ordem sugerida.** (a) `ler_ponte` + `calcular_remessa`, com o exemplo sintético da repetida e um negativo. (b) Leitores de banco e `ler_plano`. (c) `classificar_lancamentos` com a lista de regras em `regras.yaml`. (d) `main.run` generalizado e a conservação.
5. **Integração (14h15 em diante).** B conecta A e conferem os números da §9. Quem não escreveu o código recalcula linhas à mão. A carga de B é maior; se B estiver atrasado às 14h15, A puxa `classificacao` conforme `PLANO.md` §6.9.

## 12. Critérios de integração

Complementam A1–A17 de `PLANO.md` §6.5.

- O comando regenera os seis arquivos, com conteúdo, a partir das entradas intocadas, e duas execuções geram arquivos idênticos (hash).
- **Orbe:** das 1.957 linhas, processadas + bloqueadas = 1.957, com contagem por tipo e por arquivo no log. Nenhum tipo fica "fora do escopo".
- **Checkout:** estorno de setembro de venda de agosto reduz a comissão de setembro; estorno de 15/09 em diante de venda da Bridge anterior a 15/09 usa 2,59%; reversão anula só a taxa da antecipação referenciada; os 9 estornos de agosto são resolvidos por `data_venda_original` + EC.
- **Divergências:** zero alarme por arredondamento (taxa aplicada = contratada com `valor_taxa` truncado não aparece); `taxa_contratada_pct` e `taxa_aplicada_pct` na mesma escala; cada uma das cinco taxas fora da aba termina em divergência ou pendência.
- **Remessa:** 233 linhas lidas; `PC-0926-0162` conta uma vez; os 4 negativos fora da comissão, da nota e de divergências, cada um em `CONTESTACAO`; reconciliação do rodapé impressa e testada; remessa casada por CNPJ.
- **Notas:** 1 NF CHECKOUT por lojista com saldo > 0; 1 NF REMESSA para o CNPJ da Ponte; `discriminacao` preenchida; Atlas sem nota; saldo ≤ 0 em `NF_NAO_EMITIDA`; Σ NF = Σ comissões.
- **Bancos:** 184 linhas, cada uma uma vez; sem saldos e sem o aviso; `conta_codigo ∈` plano com `ACEITA_LANCTO = S`; casos-armadilha cobertos (`PIX ENVIADO CONTABILIDADE` → 4.2.06, `DEVOLUCAO PIX` → 2.1.01.002, Pix sem identificação → 1.1.09.002 **e** pendência); contagem por regra confere com a tabela da §7.
- **Rastro:** para comissão, divergência, nota, lançamento e pendência, soma do rastro = valor publicado, no centavo; toda referência existe nas entradas (`.csv`, `.eml` + `Nº Operação`, `FITID`, `L<n>`, `Taxas vigentes!L<n>`).
- **Pendências:** toda pendência tem `tipo`, `motivo` e `quem_decide`; a contagem por `quem_decide` e por tipo aparece no resumo.
- **Revisão cruzada:** A recalcula 3 linhas de cada saída de B e B recalcula 3 de cada saída de A; erros e correções vão para `MOMENTOS`.

Hipóteses novas a registrar em `HIPOTESES.md` antes do gate: arredondamento da remessa (§10.1), ref da repetida (§10.5), janela de contrapartida (§10.4), `conta_codigo` vazio para `HUMANO` (§10.2), tolerância em pontos percentuais (§10.3), `OPERACAO_POSSIVEL_DUPLICIDADE` só sinaliza, divergência de remessa não calculada para spread padrão (P4), modo `despesa` sem conta para INSS e FGTS.
