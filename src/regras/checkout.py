"""Comissão de checkout (nível Mínimo): só `VENDA`, pela taxa **contratada**.

Regra (CONFIRMADO, P1): comissão = valor_bruto x taxa_contratada, a taxa inteira, sem descontar o
custo da Orbe e sem usar a taxa aplicada. Arredondamento por venda (ROUND_HALF_UP) e o total do
lojista é a soma das linhas arredondadas (HIPOTESES.md §2).

Função pura: recebe registros, devolve registros com as origens. Não grava arquivo e não conhece o
gravador (a fronteira com `core/saida.py` está em CONTRATO_TECNICO_MINIMO.md §1). Nada de EC, CNPJ
ou nome de lojista aqui: identidade vem do cadastro e taxas vêm da planilha.

Cada venda aparece exatamente uma vez: numa origem de comissão ou numa pendência bloqueante.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from decimal import Decimal

from src.core import normalize
from src.core.contratos import (
    ComissaoCalculada,
    ContratoTaxa,
    Origem,
    PendenciaCalculada,
    ResultadoCheckout,
    TransacaoOrbe,
)

CENTO = Decimal("100")
TIPO_VENDA = "VENDA"

# (tipo, quem_decide) de cada problema, conforme CONTRATO_TECNICO_MINIMO.md §3
_QUEM = {
    "CADASTRO_NAO_RESOLVIDO": "Financeiro",
    "VENDA_INVALIDA": "Financeiro",
    "CONTRATO_AUSENTE": "Comercial",
    "CONTRATO_INATIVO": "Comercial",
    "VIGENCIA_SEM_COBERTURA": "Comercial",
    "TAXA_AUSENTE": "Comercial",
    "CONTRATO_AMBIGUO": "Comercial",
}


class _Problema(tuple):
    """(tipo, quem_decide, motivo)"""

    def __new__(cls, tipo: str, motivo: str, quem: str | None = None):
        return super().__new__(cls, (tipo, quem or _QUEM[tipo], motivo))


def _chave(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _fmt(valor: Decimal) -> str:
    """Dinheiro em pt-BR para texto de motivo: 5480.00 -> '5.480,00'."""
    inteiro, _, frac = f"{valor:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    return f"{sinal}{int(inteiro):,}".replace(",", ".") + f",{frac}"


def faixa_da_venda(modalidade: str | None, parcelas: int | None) -> str:
    """Faixa de taxa (chave de `taxas_pct`) da venda. Levanta ValueError se modalidade/parcelas não fecham."""
    mod = _chave(modalidade) if modalidade else ""
    if mod in ("DEBITO", "PIX", "CREDITO A VISTA"):
        if parcelas != 1:
            raise ValueError(f"modalidade {mod} com {parcelas!r} parcela(s); esperado 1")
        return {"DEBITO": "DEBITO", "PIX": "PIX", "CREDITO A VISTA": "CREDITO_A_VISTA"}[mod]
    if mod == "CREDITO PARCELADO":
        if parcelas is not None and 2 <= parcelas <= 6:
            return "CREDITO_2_6"
        if parcelas is not None and 7 <= parcelas <= 12:
            return "CREDITO_7_12"
        raise ValueError(f"crédito parcelado com {parcelas!r} parcela(s); esperado de 2 a 12")
    raise ValueError(f"modalidade desconhecida: {modalidade!r}")


def _cobre(c: ContratoTaxa, data: str) -> bool:
    """Vigência com limites inclusivos; None = limite aberto. Datas ISO comparam como texto."""
    return (c["vigencia_inicio"] is None or c["vigencia_inicio"] <= data) and (
        c["vigencia_fim"] is None or data <= c["vigencia_fim"]
    )


def _checar_regras(regras: dict) -> dict:
    cfg = (regras or {}).get("checkout", {}) or {}
    if cfg.get("base_comissao", "taxa_contratada") != "taxa_contratada":
        raise ValueError(f"base_comissao não suportada: {cfg['base_comissao']!r}")
    if cfg.get("vigencia_venda", "data_movimento") != "data_movimento":
        raise ValueError(f"vigencia_venda não suportada: {cfg['vigencia_venda']!r}")
    return cfg


def _problema_de_identidade(t: TransacaoOrbe, rotas: dict) -> _Problema:
    """EC fora do cadastro. Roteamento especial vem de `checkout.ec_sem_cadastro` (config), senão genérico."""
    rota = rotas.get(t["ec"])
    if rota:
        return _Problema(rota["tipo"], f"EC {t['ec']} ({t['nome_origem']}): {rota['motivo']}", rota.get("quem_decide"))
    return _Problema(
        "CADASTRO_NAO_RESOLVIDO",
        f"EC {t['ec']} ({t['nome_origem']}) não consta no cadastro de lojistas; "
        "o nome não é usado para identificar o lojista.",
    )


def _resolver_contrato(t, cnpj_cadastro, por_ec) -> tuple[ContratoTaxa | None, _Problema | None]:
    candidatos = por_ec.get(t["ec"], [])
    if not candidatos:
        return None, _Problema("CONTRATO_AUSENTE", f"EC {t['ec']} está no cadastro mas não tem contrato de taxas na planilha vigente.")
    divergentes = sorted({c["ref_origem"] for c in candidatos if c["cnpj"] != cnpj_cadastro})
    if divergentes:
        return None, _Problema(
            "CONTRATO_AMBIGUO",
            f"CNPJ do cadastro ({cnpj_cadastro}) difere do CNPJ da planilha para o EC {t['ec']} ({', '.join(divergentes)}).",
        )
    cobrindo = [c for c in candidatos if _cobre(c, t["data_movimento"])]
    if not cobrindo:
        if not any(c["ativo"] for c in candidatos):
            return None, _Problema("CONTRATO_INATIVO", f"Contrato do EC {t['ec']} está inativo na planilha.")
        return None, _Problema(
            "VIGENCIA_SEM_COBERTURA",
            f"Nenhuma vigência do EC {t['ec']} cobre a data {t['data_movimento']}.",
        )
    if len(cobrindo) > 1:
        refs = ", ".join(c["ref_origem"] for c in cobrindo)
        return None, _Problema("CONTRATO_AMBIGUO", f"Mais de uma vigência cobre {t['data_movimento']} para o EC {t['ec']} ({refs}).")
    if not cobrindo[0]["ativo"]:
        return None, _Problema("CONTRATO_INATIVO", f"Contrato do EC {t['ec']} está inativo na planilha ({cobrindo[0]['ref_origem']}).")
    return cobrindo[0], None


def _avaliar_venda(t, cadastro, por_ec, rotas):
    """Devolve (comissão, contrato, None) ou (None, None, [problemas])."""
    problemas: list[_Problema] = []
    contrato = None
    faixa = None

    bruto = t["valor_bruto"]
    if bruto is None or bruto <= 0:
        problemas.append(_Problema("VENDA_INVALIDA", f"Venda com valor bruto ausente ou não positivo ({bruto})."))
    try:
        faixa = faixa_da_venda(t["modalidade"], t["qtd_parcelas"])
    except ValueError as e:
        problemas.append(_Problema("VENDA_INVALIDA", f"Não foi possível definir a faixa de taxa: {e}."))

    if t["ec"] not in cadastro:
        problemas.insert(0, _problema_de_identidade(t, rotas))
    else:
        contrato, p = _resolver_contrato(t, cadastro[t["ec"]]["cnpj"], por_ec)
        if p:
            problemas.insert(0, p)
        elif faixa and contrato["taxas_pct"][faixa] is None:
            problemas.append(_Problema(
                "TAXA_AUSENTE",
                f"Contrato {contrato['ref_origem']} não tem taxa para a faixa {faixa}.",
            ))

    if problemas:
        return None, None, problemas
    taxa = contrato["taxas_pct"][faixa]
    return normalize.q2(bruto * taxa / CENTO), contrato, None


def _pendencia_de_venda(t: TransacaoOrbe, problemas: list[_Problema]) -> PendenciaCalculada:
    bruto = t["valor_bruto"] if t["valor_bruto"] is not None else Decimal("0")
    base = f"Valor da pendência = valor bruto da venda (R$ {_fmt(bruto)}), não a comissão, que ainda é desconhecida. A venda não entrou na comissão."
    tipo, quem, _ = problemas[0]
    motivo = " | ".join(p[2] for p in problemas) + " " + base
    return {
        "tipo": tipo,
        "ref_origem": t["ref_origem"],
        "valor_brl": bruto,
        "motivo": motivo,
        "quem_decide": quem,
        "origens": [Origem(t["arquivo_origem"], t["ref_origem"], bruto)],
    }


def _pendencias_cadastrais(contratos: list[ContratoTaxa]) -> list[PendenciaCalculada]:
    """Linhas da planilha com checkout previsto e problema de cadastro (valor 0, aponta para a linha)."""
    saida: list[PendenciaCalculada] = []
    for c in contratos:
        if all(v is None for v in c["taxas_pct"].values()):
            continue  # só remessa: não é problema de checkout
        if c["ec"] is None:
            tipo, motivo = "CADASTRO_NAO_RESOLVIDO", (
                f"{c['lojista']} (CNPJ {c['cnpj']}) tem taxas de cartão/Pix na planilha mas não tem EC da Orbe; "
                "vendas só serão ligadas a este contrato depois que uma pessoa confirmar o EC."
            )
        elif not c["ativo"]:
            tipo, motivo = "CONTRATO_INATIVO", (
                f"{c['lojista']} (EC {c['ec']}) está marcado como inativo na planilha; "
                "vendas desse EC não geram comissão até o Comercial reativar o contrato."
            )
        else:
            continue
        saida.append({
            "tipo": tipo,
            "ref_origem": c["ref_origem"],
            "valor_brl": Decimal("0"),
            "motivo": motivo + " Pendência cadastral: valor zero.",
            "quem_decide": _QUEM[tipo],
            "origens": [Origem(c["arquivo_origem"], c["ref_origem"], Decimal("0"))],
        })
    return saida


def calcular_checkout(
    transacoes: list[TransacaoOrbe],
    contratos: list[ContratoTaxa],
    cadastro: dict[str, dict[str, str]],
    competencia: str,
    regras: dict,
) -> ResultadoCheckout:
    """Comissão de checkout das vendas, por lojista (CNPJ), mais pendências e resumo de conservação."""
    cfg = _checar_regras(regras)
    rotas = cfg.get("ec_sem_cadastro") or {}
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia or ""):
        raise ValueError(f"competência inválida (esperado AAAA-MM): {competencia!r}")
    fora = [t["id_transacao"] for t in transacoes if t["data_movimento"][:7] != competencia]
    if fora:
        raise ValueError(
            f"{len(fora)} transação(ões) fora da competência {competencia}, ex.: {', '.join(fora[:3])}"
        )

    cad = {ec: {"cnpj": normalize.cnpj(d["cnpj"]), "lojista": d["lojista"]} for ec, d in cadastro.items()}
    por_ec: dict[str, list[ContratoTaxa]] = {}
    for c in contratos:
        if c["ec"] is not None:
            por_ec.setdefault(c["ec"], []).append(c)

    acum: dict[str, dict] = {}
    pendencias: list[PendenciaCalculada] = []
    fora_escopo: Counter[str] = Counter()
    vendas = processadas = 0

    for t in transacoes:
        if _chave(t["tipo_lancamento"]) != TIPO_VENDA:
            fora_escopo[t["tipo_lancamento"]] += 1
            continue
        vendas += 1
        comissao, contrato, problemas = _avaliar_venda(t, cad, por_ec, rotas)
        if problemas:
            pendencias.append(_pendencia_de_venda(t, problemas))
            continue
        processadas += 1
        ident = cad[t["ec"]]
        a = acum.setdefault(ident["cnpj"], {"lojista": ident["lojista"], "total": Decimal("0"), "origens": [], "contratos": {}})
        a["total"] += comissao
        a["origens"].append(Origem(t["arquivo_origem"], t["ref_origem"], comissao))
        a["contratos"].setdefault((contrato["arquivo_origem"], contrato["ref_origem"]), None)

    comissoes: list[ComissaoCalculada] = [
        {
            "cnpj": cnpj,
            "lojista": a["lojista"],
            "linha_negocio": "CHECKOUT",
            "comissao_brl": a["total"],
            "origens": a["origens"],
            "contratos_utilizados": [{"arquivo_origem": f, "ref_origem": r} for f, r in a["contratos"]],
        }
        for cnpj, a in sorted(acum.items())
    ]
    pendencias += _pendencias_cadastrais(contratos)

    return {
        "comissoes": comissoes,
        "pendencias": pendencias,
        "resumo": {
            "total_orbe": len(transacoes),
            "vendas_total": vendas,
            "vendas_processadas": processadas,
            "vendas_bloqueadas": vendas - processadas,
            "fora_escopo_por_tipo": dict(sorted(fora_escopo.items())),
            "contagens_por_arquivo": dict(sorted(Counter(t["arquivo_origem"] for t in transacoes).items())),
        },
    }
