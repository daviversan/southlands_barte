# Contrato técnico — nível Mínimo

Este documento complementa `PLANO.md` e fixa as interfaces para A e B desenvolverem em paralelo. É uma decisão técnica de implementação; não representa novas respostas do financeiro. Regras de negócio ainda assumidas continuam identificadas como tal no plano e devem ser registradas em `HIPOTESES.md`.

## 1. Entrega e responsabilidades

O comando deve ler os arquivos originais e gerar comissão de checkout **somente das vendas**, rastro e pendências. Estornos, antecipações e reversões ficam contabilizados como fora do escopo; não viram pendências apenas por não serem processados neste nível.

| Responsável | Arquivos de sua responsabilidade | O que entrega ao outro |
|---|---|---|
| A | `src/core/normalize.py`, `src/ingest/orbe.py`, `src/ingest/taxas.py`, `src/regras/checkout.py`, `config/lojistas.yaml`, seção `checkout` de `config/regras.yaml` | Dados normalizados e resultado do cálculo, em memória, com origens e pendências |
| B | `src/core/contratos.py`, `src/core/saida.py`, `src/regras/pendencias.py`, `src/main.py` | Tipos compartilhados, gravação dos CSVs, validação do rastro, registro de pendências e execução integrada |

A escreve os testes de normalização, leitores e cálculo. B escreve os testes de formato, rastro e integração. Ambos revisam os resultados com as entradas originais. O arquivo de contratos é de B; mudanças de interface devem ser combinadas com A antes da edição.

**Fronteira:** A calcula e devolve registros; B grava esses registros. O módulo de checkout não importa `saida.py` e não escreve arquivos. Assim A consegue trabalhar antes de o gravador existir, e B consegue trabalhar com exemplos antes de os leitores existirem.

## 2. Convenções compartilhadas

- Python 3.12 (referência registrada em `HIPOTESES.md`); dinheiro e taxas em `Decimal`, nunca `float` nos cálculos. Converter números de Excel com `Decimal(str(valor))`.
- Datas internas em `str` ISO `AAAA-MM-DD`, conforme `normalize.data()`; competência recebida como `AAAA-MM`.
- CNPJ e EC são `str`. CNPJ normalizado tem 14 dígitos, preservando zeros à esquerda. EC não é convertido em inteiro.
- Taxas internas estão em **pontos percentuais**: `Decimal("2.59")` significa 2,59%. Fórmula: `bruto * taxa_pct / Decimal("100")`.
- Normalização de taxa exige escala explícita: `pct(valor, fracao=True)` para células numéricas de taxas; `pct(valor, fracao=False)` para Orbe. Texto com `%` já indica pontos percentuais. Não inferir escala pela magnitude.
- Valores ausentes são `None`, nunca zero, `NaN`, string vazia ou taxa padrão inventada.
- Leitores retornam `list[TypedDict]`. DataFrames podem ser usados internamente, mas não são a interface entre A e B.
- `arquivo_origem` é o caminho relativo à pasta passada em `--entrada`, com `/` como separador; não contém caminho absoluto. Exemplo: `01_orbe_relatorio_comissoes_set2026.csv`.
- `ref_origem` da Orbe é o `id_transacao`; o da planilha é `Taxas vigentes!L6`, usando o número físico da linha da aba.

## 3. Tipos que B publica em `src/core/contratos.py`

Os nomes abaixo são o contrato. As estruturas são `TypedDict`; os comentários indicam os tipos dos campos.

### TransacaoOrbe

```python
{
    "id_transacao": str,
    "data_movimento": str,  # ISO AAAA-MM-DD
    "ec": str,
    "nome_origem": str,
    "tipo_lancamento": str,       # preservar enum da fonte
    "modalidade": str | None,
    "qtd_parcelas": int | None,
    "valor_bruto": Decimal,       # manter o sinal da fonte
    "taxa_aplicada_pct": Decimal,
    "arquivo_origem": str,
    "ref_origem": str,            # igual a id_transacao
}
```

O leitor entrega todas as linhas, inclusive as que não são vendas. Campos adicionais da fonte podem ser preservados, mas não são necessários ao cálculo mínimo.

### ContratoTaxa

```python
{
    "cnpj": str,
    "lojista": str,
    "ec": str | None,
    "ativo": bool,
    "vigencia_inicio": str | None,  # ISO
    "vigencia_fim": str | None,  # ISO
    "taxas_pct": {
        "DEBITO": Decimal | None,
        "CREDITO_A_VISTA": Decimal | None,
        "CREDITO_2_6": Decimal | None,
        "CREDITO_7_12": Decimal | None,
        "PIX": Decimal | None,
    },
    "arquivo_origem": str,
    "ref_origem": str,
}
```

Uma linha por vigência. Limites de vigência são inclusivos; `None` significa limite aberto, não autorização para usar lojista inativo. Bridge: fim em 14/09 e início em 15/09. Identidade por EC exato; o nome nunca resolve ambiguidade.

### Origem — tipo existente, não duplicar

```python
from src.core.saida import Origem
# Dataclass frozen já implementada:
# Origem(arquivo: str, ref: str, valor: Decimal)
```

`arquivo` e `ref` tornam-se `arquivo_origem` e `ref_origem` no CSV. Em comissão, `valor` é a comissão da venda arredondada com `q2`, não o bruto. A planilha é evidência auxiliar, não uma segunda contribuição monetária.

### ComissaoCalculada

```python
{
    "cnpj": str,
    "lojista": str,
    "linha_negocio": Literal["CHECKOUT"],
    "comissao_brl": Decimal,      # soma das comissões arredondadas por venda
    "origens": list[Origem], # contribuição com duas casas por venda
    "contratos_utilizados": list[dict[str, str]],
    # cada item: {"arquivo_origem": ..., "ref_origem": ...}
}
```

Uma comissão por CNPJ. O nome exibido vem do cadastro mestre, não da grafia de uma transação. `contratos_utilizados` contém referências distintas à planilha e serve para explicar a taxa escolhida.

### PendenciaCalculada

```python
{
    "tipo": str,
    "ref_origem": str,
    "valor_brl": Decimal,
    "motivo": str,
    "quem_decide": Literal["Financeiro", "Comercial"],
    "origens": list[Origem],
}
```

Pendência de venda bloqueada usa o **valor bruto assinado da venda** em `valor_brl` e no rastro, pois a comissão ainda é desconhecida. O motivo explicita essa base. Pendência apenas cadastral usa zero e aponta para a linha da planilha. Esses valores medem problemas distintos e não devem ser apresentados como um total de comissão perdida.

Tipos mínimos: `CADASTRO_NAO_RESOLVIDO` → Financeiro; `CONTRATO_AUSENTE`, `CONTRATO_INATIVO`, `VIGENCIA_SEM_COBERTURA`, `TAXA_AUSENTE`, `CONTRATO_AMBIGUO` → Comercial; `VENDA_INVALIDA` → Financeiro. Atlas fica com Comercial.

### ResultadoCheckout

```python
{
    "comissoes": list[ComissaoCalculada],
    "pendencias": list[PendenciaCalculada],
    "resumo": {
        "total_orbe": int,
        "vendas_total": int,
        "vendas_processadas": int,
        "vendas_bloqueadas": int,
        "fora_escopo_por_tipo": dict[str, int],
    },
}
```

Cada venda aparece exatamente uma vez: em uma origem de comissão ou em uma pendência bloqueante. Havendo vários problemas na mesma venda, registrar uma pendência com todos os motivos; não duplicar o valor. Pendências cadastrais são adicionais e não entram na contagem de vendas bloqueadas.

## 4. Interfaces dos módulos

```python
# A — caminhos resolvidos pela CLI; leitores não dependem do cwd
ler_orbe(entrada: Path) -> list[TransacaoOrbe]  # pasta; agrega arquivos Orbe
ler_taxas(caminho: Path) -> list[ContratoTaxa]
calcular_checkout(
    transacoes: list[TransacaoOrbe],
    contratos: list[ContratoTaxa],
    cadastro: dict[str, dict[str, str]],  # EC -> {cnpj, lojista}
    competencia: str,
    regras: dict,
) -> ResultadoCheckout

# B — src/regras/pendencias.py; valida campos, não decide regra de negócio
validar_pendencia(pendencia: PendenciaCalculada) -> None

# B — src/core/saida.py; já implementado
class Saida:
    def __init__(self) -> None: ...
    def emitir(self, arquivo: str, linha: dict,
               origens: list[Origem | tuple]) -> str: ...
    def gravar(self, destino: str | Path) -> dict[str, Path]: ...

conferir_diretorio(pasta: str | Path) -> None

# B — src/main.py; ainda a implementar
run(entrada: Path, competencia: str, saida: Path,
    regras_path: Path, cadastro_path: Path) -> ResultadoCheckout
```

Reutilizar `Saida`, `Origem`, `SaidaError` e `conferir_diretorio`; não criar `EscritorSaida` nem `finalizar()`. Exemplo real: `saida = Saida()`, `saida.emitir("comissoes_por_lojista", linha, origens)` e `saida.gravar(destino)`.

`arquivo` é a chave sem `.csv`. `linha` não leva `id_saida` nem campos internos. B remove `origens` e `contratos_utilizados` antes de emitir. O esquema atual rejeita colunas extras não declaradas: referências de contratos ficam em memória até uma extensão explícita de `ESQUEMAS` e dos testes.

`emitir()` valida formato e soma do rastro; `gravar()` escreve os seis CSVs e reconfere em disco. A escrita atual não é atômica: B deve integrar usando uma pasta temporária de execução e publicar os arquivos em `--saida` somente após o sucesso.

Arquivo ausente ou ilegível é erro de execução. Problema de negócio em uma venda vira pendência. `contratos.py`, leitores, cálculo, API de pendências e CLI ainda precisam ser implementados; os tipos descritos neste documento continuam sendo o contrato proposto para essa etapa.

## 5. Configurações que A fornece e B carrega

`config/lojistas.yaml` é um mapa EC → identidade canônica. Pode conter apenas correspondências exatas da planilha ou confirmadas por pessoa; não preencher por semelhança de nome.

```yaml
# Exemplo sintético; não copiar para o cadastro real.
lojistas:
  "1234567890":
    cnpj: "00123456000199"
    lojista: "Lojista Exemplo"
```

`config/lojistas.yaml` já contém `lojistas: {}`. B passa `conteudo["lojistas"]` ao cálculo; A preenche esse mapa com correspondências válidas.

`config/regras.yaml` já existe. Preservar seus demais campos e usar as chaves atuais:

```yaml
checkout:
  base_comissao: taxa_contratada
  vigencia_venda: data_movimento  # ASSUMIDO no plano
```

`tipos_processados` não existe no YAML atual: processar somente `VENDA` é o escopo desta etapa, sem exigir essa chave. `safe_load` pode produzir floats para parâmetros numéricos; converter com `Decimal(str(valor))` antes de calcular.

Nenhuma taxa ou identidade é fixada no código. Modalidades e faixas de parcelas seguem o contrato: débito, crédito à vista, crédito parcelado de 2–6 e 7–12, Pix. Modalidade desconhecida, parcelas incompatíveis ou ausência de taxa bloqueiam a venda; não usar a taxa aplicada como substituta.

## 6. Arredondamento — decisão implementada na fase 0

`HIPOTESES.md` §2 e `tests/test_saida.py` fixam arredondamento **por transação**, sem rateio. Essa decisão substitui a proposta de arredondamento agregado da versão anterior deste contrato. O trecho de `PLANO.md` §3 sobre arredondar apenas na escrita permanece divergente e deve ser harmonizado; para a integração, seguir o comportamento implementado e testado.

1. A calcula `bruto * taxa_pct / Decimal("100")` e aplica `normalize.q2()` por venda.
2. A monta cada `Origem` com essa comissão arredondada e soma essas contribuições para `comissao_brl`.
3. B passa total e origens a `Saida.emitir()`, que aplica `q2` e falha se a soma diferir.

Exemplo: duas comissões exatas de `1.005` viram `1.01` cada; total publicado `2.02`. Passar total agregado `2.01` gera `SaidaError`. Não há ajuste de resíduo nem colunas de ajuste no rastro. É decisão técnica do time, não nova confirmação do financeiro.

## 7. Saídas e execução — B

CSV UTF-8, separador `;`, dinheiro com ponto e duas casas, CNPJ preservado como texto. B deve ordenar antes de emitir; `Saida` gera IDs pela ordem de emissão e não ordena. Ordenar comissões por CNPJ e pendências por `(tipo, arquivo da primeira origem, ref_origem)`: `COM-0001`, `PEN-0001` etc. IDs são estáveis para a mesma entrada; não se promete estabilidade após mudanças nos dados.

| Arquivo | Colunas obrigatórias, nesta ordem |
|---|---|
| `comissoes_por_lojista.csv` | `id_saida;cnpj;lojista;linha_negocio;comissao_brl` |
| `pendencias.csv` | `id_saida;tipo;ref_origem;valor_brl;motivo;quem_decide` |
| `rastro.csv` | `id_saida;arquivo_origem;ref_origem;valor` |

O gravador atual regenera os **seis CSVs**, mesmo vazios. No mínimo, somente comissões, pendências e rastro têm conteúdo; divergências, notas e lançamentos ficam com cabeçalho. Não gerar registros fora do escopo. Usar uma pasta de saída própria para o mínimo, evitando misturar resultados de níveis diferentes.

```powershell
python -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/
```

A CLI oferece também `--regras` e `--cadastro`, com padrões `config/regras.yaml` e `config/lojistas.yaml`. B carrega YAML com `safe_load`, valida a competência, chama os leitores de A, calcula, grava e imprime o resumo de conservação. Transações fora da competência são erro explícito neste nível, não são descartadas silenciosamente.

## 8. Como começar em paralelo

1. B reutiliza `normalize.py`, `Saida` e `Origem`, e publica `contratos.py` com os tipos acima. A pode começar imediatamente pelos leitores e pela normalização seguindo este documento.
2. B desenvolve o gravador usando o exemplo sintético: venda `EXEMPLO-001`, bruto `1000.00`, taxa `2.59`, contribuição `25.90`; uma comissão com uma origem. Também testa uma venda bloqueada e o caso de arredondamento da seção 6.
3. A desenvolve `calcular_checkout()` sem importar a infraestrutura de B, e confere vendas reais diretamente nos arquivos.
4. B conecta o resultado de A ao gravador. Não deve ser necessário renomear campos nem recalcular comissão na CLI.
5. Ambos executam o data pack e fazem revisão cruzada antes de considerar o mínimo pronto.

## 9. Critérios de integração

- O comando regenera os seis arquivos, com conteúdo limitado ao mínimo, a partir das entradas intocadas.
- Das 1.957 linhas conhecidas da Orbe (`01_` + `06_`): 1.841 vendas = processadas + bloqueadas; as outras 116 são contadas por tipo como fora do escopo. Esses totais são verificações do data pack, não constantes do algoritmo.
- Cada venda processada usa contrato ativo e vigência única, EC exato, faixa correta e a taxa contratada.
- Bridge usa 2,59% até 14/09 e 2,19% desde 15/09 para crédito à vista.
- Atlas, identidade ambígua, cadastro incompleto e inatividade recebem tratamento explícito. Pendência cadastral só se aplica a cadastro com checkout previsto, não a lojista exclusivamente de remessa sem EC.
- Para cada comissão e pendência, soma do rastro publicado = valor publicado, no centavo; referências existem nas entradas.
- Duas execuções com as mesmas entradas produzem os mesmos arquivos.
- A e B conferem cinco vendas contra os arquivos originais e registram hipóteses e limitações.

Esses critérios complementam M1–M8 de `PLANO.md`; não substituem os entregáveis documentais do enunciado.

## 10. Ajustes tardios e conservação

A descobre arquivos por `01_orbe_*.csv` e `06_orbe_ajustes_*.csv`, ordenados por nome. O arquivo principal é obrigatório; ausência de ajustes em outro mês é válida. `ler_orbe(entrada)` recebe a pasta e agrega esses arquivos, preservando o nome real de origem. ID repetido dentro ou entre arquivos é erro explícito, sem deduplicação silenciosa.

O novo `06_` tem 14 linhas: uma venda e 13 lançamentos negativos. No mínimo, a venda `TX88447225`, da Kiwi, vira pendência por cadastro não resolvido; os 13 negativos são contados fora do escopo. Totais combinados: 1.841 vendas, 69 estornos, 38 antecipações e nove reversões. Adicionar ao resumo `contagens_por_arquivo: dict[str, int]`. Incluir ajustes em setembro segue como hipótese registrada em `HIPOTESES.md` §3.5.

## 11. Ambiente e estado da fase 0

Revisão baseada no commit `9378773` e no arquivo adicional de ajustes. Já existem normalização, gravador/rastro, configurações iniciais, hipóteses e testes. Cadastro preenchido, leitores, cálculo, pendências e CLI ainda faltam; a fundação não executa o fechamento.

- Referência da fase 0: Python 3.12. `requirements.txt`: pandas >=2.2, openpyxl >=3.1, PyYAML >=6.0 e pytest >=8.0. Streamlit é opcional.
- `pytest.ini` já define `pythonpath = .` e `testpaths = tests`. Executar na raiz.
- O Git não instala dependências nem fornece o ambiente virtual. Com Python 3.12 disponível no launcher Windows, preparar com os comandos abaixo.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

Na revisão local, `venv\Scripts\python.exe` informou Python 3.15.0 e não encontrou `pytest`; não havia `.venv`. Os 45 testes citados no sumário da fase 0 são evidência da sessão original, não uma execução reproduzida nesta revisão.

O sumário ainda registra pendências de transcript original, horários das perguntas, comunicação ao financeiro e Checkpoint 1. Não presumir conclusão dessas ações a partir do código.
