"""Tipos compartilhados entre leitores, regras e gravador (CONTRATO_TECNICO_MINIMO.md, seção 3).

Dono: B. Publicado por A, copiando o contrato, para destravar o desenvolvimento em paralelo;
qualquer mudança de interface deve ser combinada entre A e B.
"""
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


class ContratoTaxa(TypedDict):
    cnpj: str
    lojista: str
    ec: str | None
    ativo: bool
    vigencia_inicio: str | None  # ISO
    vigencia_fim: str | None  # ISO
    taxas_pct: TaxasContrato
    arquivo_origem: str
    ref_origem: str


class ComissaoCalculada(TypedDict):
    cnpj: str
    lojista: str
    linha_negocio: Literal["CHECKOUT"]
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


class ResultadoCheckout(TypedDict):
    comissoes: list[ComissaoCalculada]
    pendencias: list[PendenciaCalculada]
    resumo: ResumoCheckout
