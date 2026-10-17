"""Tipos compartilhados entre leitores, regras e gravador.

CONTRATO_TECNICO_MINIMO.md §3, estendido por CONTRATO_TECNICO_ALVO.md §3.

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
    ANTECIPACAO: Decimal | None  # coluna "Antecipação" da planilha


class ContratoTaxa(TypedDict):
    cnpj: str
    lojista: str
    ec: str | None
    ativo: bool
    vigencia_inicio: str | None  # ISO
    vigencia_fim: str | None  # ISO
    taxas_pct: TaxasContrato
    spread_remessa_pct: Decimal | None  # pontos percentuais; None = vazio ou "padrão" (P4)
    arquivo_origem: str
    ref_origem: str


class ComissaoCalculada(TypedDict):
    cnpj: str
    lojista: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    comissao_brl: Decimal  # soma das comissões arredondadas por linha de origem
    origens: list[Origem]  # contribuição com duas casas por venda
    contratos_utilizados: list[dict[str, str]]  # {"arquivo_origem", "ref_origem"}


class PendenciaCalculada(TypedDict):
    tipo: str
    ref_origem: str
    valor_brl: Decimal
    motivo: str  # linguagem de negócio (PLANO E2)
    quem_decide: Literal["Financeiro", "Comercial", "Ponte", "Contador"]  # saida.QUEM_DECIDE
    origens: list[Origem]
    sugestao: NotRequired[str]  # próximo passo; preenchida por regras.pendencias.explicar_pendencias


class DivergenciaCalculada(TypedDict):
    cnpj: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    ref_origem: str  # id_transacao ou Nº Operação
    taxa_contratada_pct: Decimal  # pontos percentuais
    taxa_aplicada_pct: Decimal  # pontos percentuais, mesma escala
    diferenca_brl: Decimal  # q2; positivo = lojista pagou a mais
    origens: list[Origem]  # exatamente uma: (arquivo, ref_origem, diferenca_brl)


class ResumoCheckout(TypedDict):
    total_orbe: int
    por_tipo: dict[str, dict[str, int]]  # tipo -> {"total", "processadas", "bloqueadas"}
    linhas_processadas: int
    linhas_bloqueadas: int
    vendas_total: int
    vendas_processadas: int
    vendas_bloqueadas: int
    fora_escopo_por_tipo: dict[str, int]  # no Alvo: sempre {}
    contagens_por_arquivo: dict[str, int]


class ResultadoCheckout(TypedDict):
    comissoes: list[ComissaoCalculada]  # só CHECKOUT
    divergencias: list[DivergenciaCalculada]  # só CHECKOUT
    pendencias: list[PendenciaCalculada]
    resumo: ResumoCheckout


class NotaCalculada(TypedDict):
    tomador_cnpj: str
    tomador: str
    linha_negocio: Literal["CHECKOUT", "REMESSA"]
    valor_brl: Decimal
    discriminacao: str
    origens: list[Origem]  # as mesmas origens da(s) comissão(ões) que a compõem
    pendencias: list[PendenciaCalculada]  # NF não emitida por saldo <= 0


class OperacaoPonte(TypedDict):
    num_operacao: str
    linha: int  # linha física na aba Operações
    data_contratacao: str  # ISO
    data_liquidacao: str | None  # ISO
    cnpj: str
    cliente_origem: str  # truncado em 20 caracteres; nunca é chave
    moeda: str
    valor_me: Decimal
    taxa_cliente: Decimal | None
    ptax: Decimal
    valor_brl: Decimal | None
    spread_brl: Decimal  # "Spread R$" REALIZADO; mantém o sinal
    spread_pct: Decimal  # pontos percentuais (a fonte vem em fração)
    spread_estimado_d1_brl: Decimal | None  # lido, nunca usado como base
    iof_brl: Decimal | None
    status_compliance: str
    observacao: str | None
    arquivo_origem: str  # o .eml
    ref_origem: str  # igual a num_operacao


class RodapePonte(TypedDict):
    total_operacoes: int
    spread_total_brl: Decimal


class RelatorioPonte(TypedDict):
    operacoes: list[OperacaoPonte]  # todas as linhas, na ordem do arquivo, inclusive repetida
    rodape: RodapePonte
    competencia: str | None  # AAAA-MM do cabeçalho "Competência: 09/2026"
    arquivo_origem: str


class ResumoRemessa(TypedDict):
    linhas_relatorio: int
    operacoes_distintas: int
    validas: int
    bloqueadas: int
    sem_spread_contratado: int
    reconciliacao: dict[str, Decimal]
    reconciliacao_operacoes: dict[str, list[str]]  # parcela -> Nº Operação envolvidos


class ResultadoRemessa(TypedDict):
    comissoes: list[ComissaoCalculada]  # uma por CNPJ, REMESSA
    divergencias: list[DivergenciaCalculada]
    pendencias: list[PendenciaCalculada]
    resumo: ResumoRemessa


class LancamentoBancario(TypedDict):
    banco: Literal["AURORA", "MERIDIANO"]
    ref_origem: str  # Aurora 'L9'; Meridiano FITID
    data: str  # ISO
    descricao: str
    valor: Decimal  # assinado: saída negativa
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
    conta_codigo: str  # vazio só quando metodo = HUMANO
    metodo: Literal["REGRA", "IA", "HUMANO"]
    confianca: Decimal  # 1 para REGRA; 0 para HUMANO
    regra_id: str | None  # auditoria; não vai ao CSV
    origens: list[Origem]


class ResultadoBancos(TypedDict):
    lancamentos: list[LancamentoClassificado]
    pendencias: list[PendenciaCalculada]
    resumo: dict  # total_aurora, total_meridiano, por_regra, humano


class ResultadoFechamento(TypedDict):
    checkout: ResultadoCheckout
    remessa: ResultadoRemessa
    bancos: ResultadoBancos
    notas: list[NotaCalculada]
    pendencias: list[PendenciaCalculada]  # consolidadas, explicadas e validadas
    conferencia: NotRequired[list]  # list[core.conferencia.Checagem], preenchida após a publicação
