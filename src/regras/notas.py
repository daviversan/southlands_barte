"""Notas fiscais a emitir (nível Alvo), a partir das comissões já calculadas.

- CHECKOUT (CONFIRMADO, P5): uma nota por lojista no mês, pela comissão **líquida** (MDR +
  antecipação − estornos − reversões, na mesma nota: CONFIRMADO, P3). Tomador = o próprio lojista
  (`checkout.nf_tomador: lojista`, ASSUMIDO, P16).
- REMESSA (CONFIRMADO, P5): **uma** nota para a tomadora configurada em `remessa.nf_tomador` (Ponte
  Câmbio, CNPJ do e-mail), pelo total da participação da Tarvo; sem nota por lojista.
- Saldo <= 0 não emite nota: vira pendência `NF_NAO_EMITIDA` (CONFIRMADO) com as mesmas origens.

O valor de cada nota é a soma exata das origens das comissões que a compõem, sem ajuste, para o
rastro fechar no centavo. Função pura: não grava arquivo.
"""
from __future__ import annotations

from decimal import Decimal

from src.core import normalize
from src.core.contratos import ComissaoCalculada, NotaCalculada, Origem, PendenciaCalculada

_TOMADORES_CHECKOUT = ("lojista",)


def _discriminacao(modelo: str | None, chave: str, competencia: str, n: int) -> str:
    if not modelo or not str(modelo).strip():
        raise ValueError(f"notas.{chave} ausente na configuração")
    texto = str(modelo).format(competencia=competencia, n_transacoes=n).strip()
    if not texto:
        raise ValueError(f"notas.{chave} gera discriminação vazia")
    return texto


def _fmt(valor: Decimal) -> str:
    inteiro, _, frac = f"{normalize.q2(valor):.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    return f"{sinal}{int(inteiro.lstrip('-')):,}".replace(",", ".") + f",{frac}"


def _nao_emitida(cnpj: str, nome: str, linha: str, valor: Decimal, origens: list[Origem]) -> PendenciaCalculada:
    return {
        "tipo": "NF_NAO_EMITIDA",
        "ref_origem": cnpj,
        "valor_brl": valor,
        "motivo": (f"A comissão de {linha.lower()} de {nome} (CNPJ {cnpj}) fechou o mês em R$ {_fmt(valor)}: "
                   "os estornos e reversões superaram as vendas. Nota com saldo zero ou negativo não é emitida. "
                   "O valor mostrado é o saldo da comissão."),
        "quem_decide": "Financeiro",
        "origens": list(origens),
    }


def calcular_notas(
    comissoes: list[ComissaoCalculada], competencia: str, regras: dict
) -> tuple[list[NotaCalculada], list[PendenciaCalculada]]:
    """(notas, pendências `NF_NAO_EMITIDA`). Saldo <= 0 não tem nota para carregar a pendência,
    por isso ela volta em separado."""
    regras = regras or {}
    cfg_notas = regras.get("notas") or {}
    cfg_checkout = regras.get("checkout") or {}
    cfg_remessa = regras.get("remessa") or {}
    tomador = cfg_checkout.get("nf_tomador", "lojista")
    if tomador not in _TOMADORES_CHECKOUT:
        raise ValueError(f"checkout.nf_tomador não suportado: {tomador!r}")
    if not cfg_checkout.get("antecipacao_mesma_nota", True):
        raise ValueError("checkout.antecipacao_mesma_nota: false não é suportado")

    notas: list[NotaCalculada] = []
    pendentes: list[PendenciaCalculada] = []

    for c in sorted((c for c in comissoes if c["linha_negocio"] == "CHECKOUT"), key=lambda c: c["cnpj"]):
        if c["comissao_brl"] <= 0:
            pendentes.append(_nao_emitida(c["cnpj"], c["lojista"], "CHECKOUT", c["comissao_brl"], c["origens"]))
            continue
        notas.append({
            "tomador_cnpj": c["cnpj"],
            "tomador": c["lojista"],
            "linha_negocio": "CHECKOUT",
            "valor_brl": sum((o.valor for o in c["origens"]), Decimal(0)),
            "discriminacao": _discriminacao(cfg_notas.get("discriminacao_checkout"), "discriminacao_checkout",
                                            competencia, len(c["origens"])),
            "origens": list(c["origens"]),
            "pendencias": [],
        })

    remessa = [c for c in comissoes if c["linha_negocio"] == "REMESSA"]
    if remessa:
        nf = cfg_remessa.get("nf_tomador") or {}
        cnpj, nome = normalize.cnpj(nf.get("cnpj")), nf.get("nome")
        if not cnpj or not nome:
            raise ValueError("remessa.nf_tomador precisa de cnpj e nome")
        origens = sorted((o for c in remessa for o in c["origens"]), key=lambda o: (o.arquivo, o.ref))
        total = sum((o.valor for o in origens), Decimal(0))
        if total <= 0:
            pendentes.append(_nao_emitida(cnpj, nome, "REMESSA", total, origens))
        else:
            notas.append({
                "tomador_cnpj": cnpj,
                "tomador": nome,
                "linha_negocio": "REMESSA",
                "valor_brl": total,
                "discriminacao": _discriminacao(cfg_notas.get("discriminacao_remessa"), "discriminacao_remessa",
                                                competencia, len(origens)),
                "origens": origens,
                "pendencias": [],
            })

    return notas, pendentes


def gerar_notas(comissoes: list[ComissaoCalculada], competencia: str, regras: dict) -> list[NotaCalculada]:
    """Interface do contrato (§4): só as notas. Use `calcular_notas` para obter também as pendências."""
    return calcular_notas(comissoes, competencia, regras)[0]
