"""Comissão e divergência de checkout (nível Alvo): todos os tipos de lançamento da Orbe.

Regra (CONFIRMADO, P1): comissão = valor_bruto x taxa_contratada, a taxa inteira, sem descontar o
custo da Orbe e sem usar a taxa aplicada. Arredondamento por linha (ROUND_HALF_UP) e o total do
lojista é a soma das linhas arredondadas (HIPOTESES.md §2). Linhas negativas (estorno, reversão)
contribuem com sinal negativo.

Por tipo (CONTRATO_TECNICO_ALVO.md §5.1):
- VENDA: faixa da modalidade/parcelas, vigência pela `data_movimento`;
- ANTECIPACAO: taxa de antecipação, vigência pela `data_movimento`;
- ESTORNO: faixa do próprio estorno, vigência pela `data_venda_original` (CONFIRMADO, P2);
- REVERSAO ANTECIPACAO: taxa de antecipação, vigência pela `data_venda_original`.
Estorno e reversão abatem o mês em que ocorrem; a data original só escolhe a taxa.

Função pura: recebe registros, devolve registros com as origens. Não grava arquivo e não conhece o
gravador (a fronteira com `core/saida.py` está em CONTRATO_TECNICO_MINIMO.md §1). Nada de EC, CNPJ
ou nome de lojista aqui: identidade vem do cadastro e taxas vêm da planilha.

Cada linha aparece exatamente uma vez: numa origem de comissão ou numa pendência bloqueante.
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
    DivergenciaCalculada,
    Origem,
    PendenciaCalculada,
    ResultadoCheckout,
    TransacaoOrbe,
)

CENTO = Decimal("100")
TIPO_VENDA = "VENDA"
TIPO_ESTORNO = "ESTORNO"
TIPO_ANTECIPACAO = "ANTECIPACAO"
TIPO_REVERSAO = "REVERSAO ANTECIPACAO"
# tipo -> (sinal esperado do bruto, usa data_venda_original?, tipo exigido da original)
_TIPOS = {
    TIPO_VENDA: (1, False, None),
    TIPO_ANTECIPACAO: (1, False, None),
    TIPO_ESTORNO: (-1, True, TIPO_VENDA),
    TIPO_REVERSAO: (-1, True, TIPO_ANTECIPACAO),
}

# (tipo, quem_decide) de cada problema, conforme CONTRATO_TECNICO_MINIMO.md §3
_QUEM = {
    "CADASTRO_NAO_RESOLVIDO": "Financeiro",
    "VENDA_INVALIDA": "Financeiro",
    "LANCAMENTO_INVALIDO": "Financeiro",
    "CONTRATO_AUSENTE": "Comercial",
    "CONTRATO_INATIVO": "Comercial",
    "VIGENCIA_SEM_COBERTURA": "Comercial",
    "TAXA_AUSENTE": "Comercial",
    "CONTRATO_AMBIGUO": "Comercial",
}


# Nomes de negócio para texto de motivo (o enum da fonte continua no dado).
_TIPO_LEGIVEL = {
    TIPO_VENDA: "Venda",
    TIPO_ESTORNO: "Estorno",
    TIPO_ANTECIPACAO: "Antecipação",
    TIPO_REVERSAO: "Reversão de antecipação",
}
_FAIXA_LEGIVEL = {
    "DEBITO": "débito",
    "CREDITO_A_VISTA": "crédito à vista",
    "CREDITO_2_6": "crédito parcelado em 2 a 6 vezes",
    "CREDITO_7_12": "crédito parcelado em 7 a 12 vezes",
    "PIX": "Pix",
    "ANTECIPACAO": "antecipação",
}


class _Problema(tuple):
    """(tipo, quem_decide, motivo, sugestao específica ou None)"""

    def __new__(cls, tipo: str, motivo: str, quem: str | None = None, sugestao: str | None = None):
        return super().__new__(cls, (tipo, quem or _QUEM[tipo], motivo, sugestao))


def _chave(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _fmt(valor: Decimal) -> str:
    """Dinheiro em pt-BR para texto de motivo: 5480.00 -> '5.480,00'."""
    inteiro, _, frac = f"{valor:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    return f"{sinal}{int(inteiro):,}".replace(",", ".") + f",{frac}"


def _data_br(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "data não informada"


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
    if cfg.get("vigencia_estorno", "data_venda_original") != "data_venda_original":
        raise ValueError(f"vigencia_estorno não suportada: {cfg['vigencia_estorno']!r}")
    if cfg.get("estorno_abate_em", "mes_do_estorno") != "mes_do_estorno":
        raise ValueError(f"estorno_abate_em não suportado: {cfg['estorno_abate_em']!r}")
    return cfg


def _problema_de_identidade(t: TransacaoOrbe, rotas: dict) -> _Problema:
    """EC fora do cadastro. Roteamento especial vem de `checkout.ec_sem_cadastro` (config), senão genérico."""
    rota = rotas.get(t["ec"])
    if rota:
        return _Problema(rota["tipo"], f"{t['nome_origem']} (EC {t['ec']} na Orbe): {rota['motivo']}",
                         rota.get("quem_decide"), rota.get("sugestao"))
    return _Problema(
        "CADASTRO_NAO_RESOLVIDO",
        f"{t['nome_origem']} (EC {t['ec']} na Orbe) não consta no cadastro de lojistas da Tarvo, então não "
        "sabemos de qual contrato é. Lojista não é identificado pelo nome.",
    )


def _resolver_contrato(t, data, cnpj_cadastro, por_ec) -> tuple[ContratoTaxa | None, _Problema | None]:
    """Contrato do EC vigente em `data` (a data de vigência do tipo, não necessariamente a do movimento)."""
    candidatos = por_ec.get(t["ec"], [])
    if not candidatos:
        return None, _Problema("CONTRATO_AUSENTE", f"O EC {t['ec']} está no cadastro, mas não há contrato de taxas para ele na aba vigente da planilha.")
    divergentes = sorted({c["ref_origem"] for c in candidatos if c["cnpj"] != cnpj_cadastro})
    if divergentes:
        return None, _Problema(
            "CONTRATO_AMBIGUO",
            f"O CNPJ do cadastro ({cnpj_cadastro}) não é o mesmo da planilha para o EC {t['ec']} "
            f"({', '.join(divergentes)}); não sabemos qual contrato vale.",
        )
    cobrindo = [c for c in candidatos if _cobre(c, data)]
    if not cobrindo:
        if not any(c["ativo"] for c in candidatos):
            return None, _Problema("CONTRATO_INATIVO", f"O contrato do EC {t['ec']} está marcado como inativo na planilha.")
        return None, _Problema(
            "VIGENCIA_SEM_COBERTURA",
            f"Nenhum contrato do EC {t['ec']} estava vigente em {_data_br(data)}.",
        )
    if len(cobrindo) > 1:
        refs = ", ".join(c["ref_origem"] for c in cobrindo)
        return None, _Problema("CONTRATO_AMBIGUO", f"Há mais de um contrato do EC {t['ec']} vigente em {_data_br(data)} "
                                                   f"({refs}); não sabemos qual taxa vale.")
    if not cobrindo[0]["ativo"]:
        return None, _Problema("CONTRATO_INATIVO", f"O contrato do EC {t['ec']} está marcado como inativo na planilha "
                                                   f"({cobrindo[0]['ref_origem']}).")
    return cobrindo[0], None


def _validar_lancamento(t, tipo, por_id, estornados) -> tuple[str | None, str | None, list[_Problema]]:
    """(faixa, data de vigência, problemas de dado). Não olha cadastro nem contrato."""
    invalido = "VENDA_INVALIDA" if tipo == TIPO_VENDA else "LANCAMENTO_INVALIDO"
    if tipo not in _TIPOS:
        return None, None, [_Problema("LANCAMENTO_INVALIDO", f"Tipo de lançamento desconhecido: {t['tipo_lancamento']!r}.")]
    sinal, usa_original, tipo_original = _TIPOS[tipo]
    problemas: list[_Problema] = []

    bruto = t["valor_bruto"]
    if bruto is None or bruto * sinal <= 0:
        esperado = "positivo" if sinal > 0 else "negativo"
        problemas.append(_Problema(invalido, f"{tipo} com valor bruto ausente ou não {esperado} ({bruto})."))

    faixa = None
    if tipo in (TIPO_ANTECIPACAO, TIPO_REVERSAO):
        faixa = "ANTECIPACAO"  # sem modalidade/parcelas: vazio estrutural, não é erro
    else:
        try:
            faixa = faixa_da_venda(t["modalidade"], t["qtd_parcelas"])
        except ValueError as e:
            problemas.append(_Problema(invalido, f"Não foi possível definir a faixa de taxa: {e}."))

    data = t["data_movimento"]
    if usa_original:
        data = t.get("data_venda_original")
        if data is None:
            problemas.append(_Problema("LANCAMENTO_INVALIDO", f"{tipo} sem data da venda original; a taxa não pode ser escolhida."))
        elif data > t["data_movimento"]:
            problemas.append(_Problema("LANCAMENTO_INVALIDO", f"Data da venda original ({data}) posterior ao movimento ({t['data_movimento']})."))
        ref = t.get("id_referencia")
        original = por_id.get(ref) if ref else None
        if original is not None:
            if original["ec"] != t["ec"]:
                problemas.append(_Problema("LANCAMENTO_INVALIDO", f"EC {t['ec']} difere do EC {original['ec']} da original {ref}."))
            if _chave(original["tipo_lancamento"]) != tipo_original:
                problemas.append(_Problema("LANCAMENTO_INVALIDO", f"{tipo} referencia {ref}, que é {original['tipo_lancamento']} (esperado {tipo_original})."))
        if ref:
            if ref in estornados:
                problemas.append(_Problema("LANCAMENTO_INVALIDO", f"Segundo {tipo} para {ref} (o primeiro é {estornados[ref]}); não abate duas vezes."))
            else:
                estornados[ref] = t["id_transacao"]
    return faixa, data, problemas


def _avaliar_linha(t, cadastro, por_ec, rotas, por_id, estornados):
    """Devolve (comissão, contrato, taxa, None) ou (None, None, None, [problemas])."""
    tipo = _chave(t["tipo_lancamento"])
    faixa, data, problemas = _validar_lancamento(t, tipo, por_id, estornados)
    if tipo not in _TIPOS:
        return None, None, None, problemas
    contrato = None

    if t["ec"] not in cadastro:
        problemas.insert(0, _problema_de_identidade(t, rotas))
    elif data is not None:
        contrato, p = _resolver_contrato(t, data, cadastro[t["ec"]]["cnpj"], por_ec)
        if p:
            problemas.insert(0, p)
        elif faixa and contrato["taxas_pct"][faixa] is None:
            problemas.append(_Problema(
                "TAXA_AUSENTE",
                f"O contrato ({contrato['ref_origem']}) não tem taxa para a faixa {_FAIXA_LEGIVEL.get(faixa, faixa)}.",
            ))

    if problemas:
        return None, None, None, problemas
    taxa = contrato["taxas_pct"][faixa]
    return normalize.q2(t["valor_bruto"] * taxa / CENTO), contrato, taxa, None


def _pendencia_de_linha(t: TransacaoOrbe, problemas: list[_Problema]) -> PendenciaCalculada:
    bruto = t["valor_bruto"] if t["valor_bruto"] is not None else Decimal("0")
    tipo_legivel = _TIPO_LEGIVEL.get(_chave(t["tipo_lancamento"]), f"Lançamento {t['tipo_lancamento']}")
    base = (f"{tipo_legivel} de R$ {_fmt(bruto)} em {_data_br(t['data_movimento'])} ficou fora da comissão do mês. "
            "O valor mostrado é o valor bruto da transação, não a comissão, que só pode ser calculada depois "
            "da decisão.")
    tipo, quem, _, sugestao = problemas[0]
    pendencia: PendenciaCalculada = {
        "tipo": tipo,
        "ref_origem": t["ref_origem"],
        "valor_brl": bruto,
        "motivo": " | ".join(p[2] for p in problemas) + " " + base,
        "quem_decide": quem,
        "origens": [Origem(t["arquivo_origem"], t["ref_origem"], bruto)],
    }
    if sugestao:
        pendencia["sugestao"] = sugestao
    return pendencia


def _divergencia(t, cnpj, taxa_contratada, limiar) -> DivergenciaCalculada | None:
    """Compara **taxas** (nunca o valor_taxa truncado da Orbe). Positivo = lojista pagou a mais."""
    aplicada = t["taxa_aplicada_pct"]
    if aplicada is None or aplicada == taxa_contratada:
        return None
    diferenca = normalize.q2(t["valor_bruto"] * (aplicada - taxa_contratada) / CENTO)
    if abs(diferenca) < limiar:
        return None
    return {
        "cnpj": cnpj,
        "linha_negocio": "CHECKOUT",
        "ref_origem": t["ref_origem"],
        "taxa_contratada_pct": taxa_contratada,
        "taxa_aplicada_pct": aplicada,
        "diferenca_brl": diferenca,
        "origens": [Origem(t["arquivo_origem"], t["ref_origem"], diferenca)],
    }


def _pendencias_cadastrais(contratos: list[ContratoTaxa]) -> list[PendenciaCalculada]:
    """Linhas da planilha com checkout previsto e problema de cadastro (valor 0, aponta para a linha)."""
    saida: list[PendenciaCalculada] = []
    for c in contratos:
        if all(v is None for v in c["taxas_pct"].values()):
            continue  # só remessa: não é problema de checkout
        if c["ec"] is None:
            tipo, motivo = "CADASTRO_NAO_RESOLVIDO", (
                f"{c['lojista']} (CNPJ {c['cnpj']}) tem taxas de cartão/Pix na planilha, mas sem o código de "
                "estabelecimento (EC) da Orbe; enquanto o EC não for confirmado, as vendas não podem ser ligadas "
                "a este contrato."
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
            "motivo": motivo + " É um ajuste de cadastro, sem valor no fechamento.",
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
    """Comissão de checkout por lojista (CNPJ), divergências por linha, pendências e resumo de conservação."""
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

    limiar = Decimal(str(cfg.get("limiar_divergencia_brl", "0.01")))
    por_id = {t["id_transacao"]: t for t in transacoes}
    estornados: dict[str, str] = {}
    acum: dict[str, dict] = {}
    pendencias: list[PendenciaCalculada] = []
    divergencias: list[DivergenciaCalculada] = []
    por_tipo: dict[str, dict[str, int]] = {}

    for t in transacoes:
        contagem = por_tipo.setdefault(t["tipo_lancamento"], {"total": 0, "processadas": 0, "bloqueadas": 0})
        contagem["total"] += 1
        comissao, contrato, taxa, problemas = _avaliar_linha(t, cad, por_ec, rotas, por_id, estornados)
        if problemas:
            contagem["bloqueadas"] += 1
            pendencias.append(_pendencia_de_linha(t, problemas))
            continue
        contagem["processadas"] += 1
        ident = cad[t["ec"]]
        a = acum.setdefault(ident["cnpj"], {"lojista": ident["lojista"], "total": Decimal("0"), "origens": [], "contratos": {}})
        a["total"] += comissao
        a["origens"].append(Origem(t["arquivo_origem"], t["ref_origem"], comissao))
        a["contratos"].setdefault((contrato["arquivo_origem"], contrato["ref_origem"]), None)
        div = _divergencia(t, ident["cnpj"], taxa, limiar)
        if div:
            divergencias.append(div)

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

    vendas = por_tipo.get(TIPO_VENDA, {"total": 0, "processadas": 0, "bloqueadas": 0})
    return {
        "comissoes": comissoes,
        "divergencias": divergencias,
        "pendencias": pendencias,
        "resumo": {
            "total_orbe": len(transacoes),
            "por_tipo": dict(sorted(por_tipo.items())),
            "linhas_processadas": sum(c["processadas"] for c in por_tipo.values()),
            "linhas_bloqueadas": sum(c["bloqueadas"] for c in por_tipo.values()),
            "vendas_total": vendas["total"],
            "vendas_processadas": vendas["processadas"],
            "vendas_bloqueadas": vendas["bloqueadas"],
            "fora_escopo_por_tipo": {},
            "contagens_por_arquivo": dict(sorted(Counter(t["arquivo_origem"] for t in transacoes).items())),
        },
    }
