"""Interfaces compartilhadas do Mínimo e Alvo (contrato técnico, seção 3). Dono: B."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, NotRequired, TypedDict

from src.core.saida import Origem  # noqa: F401  (reexportado: não duplicar o tipo)


class TransacaoOrbe(TypedDict):
    id_transacao: str
    data_movimento: str  # ISO AAAA-MM-DD
    ec: str
    nome_origem: str
    tipo_lancamento: str  # preserva o enum da fonte
    modalidade: str | None
    qtd_parcelas: int | None
    valor_bruto: Decimal  # mantém o sinal da fonte
    taxa_aplicada_pct: Decimal
    arquivo_origem: str
    ref_origem: str  # igual a id_transacao
    # campos extras preservados da fonte (não usados no nível Mínimo)
    bandeira: NotRequired[str | None]
    valor_taxa: NotRequired[Decimal | None]
    valor_liquido: NotRequired[Decimal | None]
    id_referencia: NotRequired[str | None]
    data_venda_original: NotRequired[str | None]


class TaxasContrato(TypedDict):
    DEBITO: Decimal | None
    CREDITO_A_VISTA: Decimal | None
    CREDITO_2_6: Decimal | None
    CREDITO_7_12: Decimal | None
    PIX: Decimal | None
    ANTECIPACAO: Decimal | None


class ContratoTaxa(TypedDict):
    cnpj: str
    lojista: str
    ec: str | None
    ativo: bool
    vigencia_inicio: str | None  # ISO
    vigencia_fim: str | None  # ISO
    taxas_pct: TaxasContrato
    spread_remessa_pct: Decimal | None
    arquivo_origem: str
    ref_origem: str


class ComissaoCalculada(TypedDict):
    cnpj: str
    lojista: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    comissao_brl: Decimal  # soma das comissões arredondadas por venda
    origens: list[Origem]  # contribuição com duas casas por venda
    contratos_utilizados: list[dict[str, str]]  # {"arquivo_origem", "ref_origem"}


class PendenciaCalculada(TypedDict):
    tipo: str
    ref_origem: str
    valor_brl: Decimal
    motivo: str
    quem_decide: Literal["Financeiro", "Comercial"]
    origens: list[Origem]


class ResumoCheckout(TypedDict):
    total_orbe: int
    vendas_total: int
    vendas_processadas: int
    vendas_bloqueadas: int
    fora_escopo_por_tipo: dict[str, int]
    contagens_por_arquivo: dict[str, int]
    por_tipo: dict[str, dict[str, int]]
    linhas_processadas: int
    linhas_bloqueadas: int


class ResultadoCheckout(TypedDict):
    comissoes: list[ComissaoCalculada]
    divergencias: list[DivergenciaCalculada]
    pendencias: list[PendenciaCalculada]
    resumo: ResumoCheckout


class DivergenciaCalculada(TypedDict):
    cnpj: str
    linha_negocio: Literal['CHECKOUT', 'REMESSA']
    ref_origem: str
    taxa_contratada_pct: Decimal
    taxa_aplicada_pct: Decimal
    diferenca_brl: Decimal
    origens: list[Origem]


class NotaCalculada(TypedDict):
    tomador_cnpj: str
    tomador: str
    linha_negocio: Literal['CHECKOUT', 'REMESSA']
    valor_brl: Decimal
    discriminacao: str
    origens: list[Origem]
    pendencias: list[PendenciaCalculada]


class OperacaoPonte(TypedDict):
    num_operacao: str
    linha: int
    data_contratacao: str
    data_liquidacao: str
    cnpj: str
    cliente_origem: str
    moeda: str
    valor_me: Decimal
    taxa_cliente: Decimal
    ptax: Decimal
    valor_brl: Decimal
    spread_brl: Decimal
    spread_pct: Decimal
    spread_estimado_d1_brl: Decimal | None
    iof_brl: Decimal | None
    status_compliance: str
    observacao: str | None
    arquivo_origem: str
    ref_origem: str


class RodapePonte(TypedDict):
    total_operacoes: int
    spread_total_brl: Decimal


class RelatorioPonte(TypedDict):
    operacoes: list[OperacaoPonte]
    rodape: RodapePonte
    competencia: str | None
    arquivo_origem: str


class ResumoRemessa(TypedDict):
    linhas_relatorio: int
    operacoes_distintas: int
    validas: int
    bloqueadas: int
    sem_spread_contratado: int
    reconciliacao: dict[str, Decimal]


class ResultadoRemessa(TypedDict):
    comissoes: list[ComissaoCalculada]
    divergencias: list[DivergenciaCalculada]
    pendencias: list[PendenciaCalculada]
    resumo: ResumoRemessa


class LancamentoBancario(TypedDict):
    banco: Literal['AURORA', 'MERIDIANO']
    ref_origem: str
    data: str
    descricao: str
    valor: Decimal
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
    metodo: Literal['REGRA', 'IA', 'HUMANO']
    confianca: Decimal
    regra_id: str | None
    origens: list[Origem]


class ResultadoBancos(TypedDict):
    lancamentos: list[LancamentoClassificado]
    pendencias: list[PendenciaCalculada]
    resumo: dict


class ResultadoFechamento(TypedDict):
    checkout: ResultadoCheckout
    remessa: ResultadoRemessa
    bancos: ResultadoBancos
    notas: list[NotaCalculada]
    pendencias: list[PendenciaCalculada]
