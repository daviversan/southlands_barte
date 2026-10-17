"""Comissão e divergência de remessa (nível Alvo), a partir do relatório da Ponte.

Regras (CONTRATO_TECNICO_ALVO.md §6.1–6.2):
- lojista identificado **só por CNPJ normalizado**; não precisa ter EC;
- cada linha do relatório recebe um destino, na ordem: repetida -> CNPJ fora da planilha ->
  spread negativo (contestação) -> ressalva (só se configurado para bloquear) -> válida;
- comissão = q2(Spread R$ realizado x participação), **por operação** (HIPOTESES.md H1);
- divergência = valor cheio `Spread R$ − Valor ME × PTAX × spread contratado`, só quando o
  `Spread %` difere do contratado além da precisão do relatório; spread padrão não é calculado.

Função pura: recebe registros, devolve registros com as origens. Nada de CNPJ ou nome aqui.
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.core import normalize
from src.core.contratos import (
    ComissaoCalculada,
    ContratoTaxa,
    DivergenciaCalculada,
    Origem,
    PendenciaCalculada,
    RelatorioPonte,
    ResultadoRemessa,
)

CENTO = Decimal("100")
STATUS_RESSALVA = "APROVADO C/ RESSALVA"
# Pendências que retiram a linha da comissão (contam na conservação). As demais só sinalizam.
TIPOS_BLOQUEANTES = ("OPERACAO_REPETIDA", "CADASTRO_NAO_RESOLVIDO", "CONTESTACAO", "OPERACAO_COM_RESSALVA")


def _fmt(valor: Decimal) -> str:
    inteiro, _, frac = f"{valor:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    return f"{sinal}{int(inteiro.lstrip('-')):,}".replace(",", ".") + f",{frac}"


def ref_ocorrencia(num_operacao: str, k: int) -> str:
    """`ref_origem` da k-ésima ocorrência de um `Nº Operação` (k = 1 é a própria operação)."""
    return num_operacao if k == 1 else f"{num_operacao}#{k}"


def _cobre(c: ContratoTaxa, data: str) -> bool:
    return (c["vigencia_inicio"] is None or c["vigencia_inicio"] <= data) and (
        c["vigencia_fim"] is None or data <= c["vigencia_fim"]
    )


def _spread_contratado(contratos: list[ContratoTaxa], data: str) -> Decimal | None:
    """Spread do CNPJ na data. Sem vigência cobrindo, usa todas as linhas do CNPJ (a vigência da
    planilha é do contrato de cartão). Valores diferentes entre linhas = sem spread único: None."""
    candidatos = [c for c in contratos if _cobre(c, data)] or contratos
    spreads = {c["spread_remessa_pct"] for c in candidatos}
    return spreads.pop() if len(spreads) == 1 else None


def _pendencia(tipo: str, ref: str, valor: Decimal, motivo: str, arquivo: str, ref_rastro: str | None = None,
               valor_rastro: Decimal | None = None) -> PendenciaCalculada:
    return {
        "tipo": tipo,
        "ref_origem": ref,
        "valor_brl": valor,
        "motivo": motivo,
        "quem_decide": "Financeiro",
        "origens": [Origem(arquivo, ref_rastro or ref, valor if valor_rastro is None else valor_rastro)],
    }


def _nomes(contratos: list[ContratoTaxa], cadastro: dict[str, dict[str, str]]) -> dict[str, str]:
    """CNPJ -> nome exibido: cadastro mestre primeiro, senão a primeira linha da planilha."""
    nomes: dict[str, str] = {}
    for c in contratos:
        nomes.setdefault(c["cnpj"], c["lojista"])
    for d in cadastro.values():
        nomes[normalize.cnpj(d["cnpj"])] = d["lojista"]
    return nomes


def calcular_remessa(
    relatorio: RelatorioPonte,
    contratos: list[ContratoTaxa],
    cadastro: dict[str, dict[str, str]],
    competencia: str,
    regras: dict,
) -> ResultadoRemessa:
    cfg = (regras or {}).get("remessa") or {}
    if cfg.get("base_spread", "realizado") != "realizado":
        raise ValueError(f"remessa.base_spread não suportada: {cfg['base_spread']!r}")
    participacao = Decimal(str(cfg.get("participacao_tarvo", "0.5")))
    tolerancia_pp = Decimal(str(cfg.get("precisao_spread_pct", "0.00001"))) * CENTO  # fração -> p.p.
    limiar = Decimal(str(((regras or {}).get("checkout") or {}).get("limiar_divergencia_brl", "0.01")))
    ressalva_entra = bool(cfg.get("aprovado_com_ressalva_entra", True))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia or ""):
        raise ValueError(f"competência inválida (esperado AAAA-MM): {competencia!r}")
    operacoes = relatorio["operacoes"]
    fora = [o["num_operacao"] for o in operacoes if o["data_contratacao"][:7] != competencia]
    if fora:
        raise ValueError(f"{len(fora)} operação(ões) da Ponte fora da competência {competencia}, ex.: {', '.join(fora[:3])}")
    if relatorio.get("competencia") and relatorio["competencia"] != competencia:
        raise ValueError(f"relatório da Ponte é da competência {relatorio['competencia']}, não {competencia}")

    por_cnpj: dict[str, list[ContratoTaxa]] = {}
    for c in contratos:
        por_cnpj.setdefault(c["cnpj"], []).append(c)
    nomes = _nomes(contratos, cadastro)
    arquivo = relatorio["arquivo_origem"]

    ocorrencias: dict[str, int] = {}
    chaves_vistas: dict[tuple, str] = {}
    acum: dict[str, dict] = {}
    pendencias: list[PendenciaCalculada] = []
    divergencias: list[DivergenciaCalculada] = []
    parcelas = {"repetidas": [], "negativos": [], "cadastro": [], "ressalva": []}
    sem_spread = validas = 0

    for op in operacoes:
        num, spread = op["num_operacao"], op["spread_brl"]
        k = ocorrencias[num] = ocorrencias.get(num, 0) + 1
        if k > 1:
            ref = ref_ocorrencia(num, k)
            pendencias.append(_pendencia(
                "OPERACAO_REPETIDA", ref, spread,
                f"Nº Operação {num} aparece {k} vezes no relatório (linha {op['linha']} é a ocorrência {k}). "
                "O número é único: a operação conta uma vez na comissão e esta linha entra na lista de correção "
                f"a pedir para a Ponte. Valor da pendência = Spread R$ da linha excedente (R$ {_fmt(spread)}).",
                arquivo))
            parcelas["repetidas"].append((ref, spread))
            continue

        chave = (op["cnpj"], op["valor_me"], op["moeda"], op["data_contratacao"])
        if chave in chaves_vistas:
            pendencias.append(_pendencia(
                "OPERACAO_POSSIVEL_DUPLICIDADE", num, Decimal("0"),
                f"{num} tem o mesmo CNPJ, valor ({op['moeda']} {op['valor_me']}) e data de {chaves_vistas[chave]}, "
                "com Nº Operação diferente. Só sinalização: a operação continua na comissão até alguém confirmar "
                "com a Ponte. Valor zero (não retira nada do fechamento).",
                arquivo))
        else:
            chaves_vistas[chave] = num

        if op["cnpj"] not in por_cnpj:
            pendencias.append(_pendencia(
                "CADASTRO_NAO_RESOLVIDO", num, spread,
                f"CNPJ {op['cnpj']} ({op['cliente_origem']}) da operação {num} não consta na planilha de taxas; "
                f"a operação não entrou na comissão. Valor da pendência = Spread R$ (R$ {_fmt(spread)}).",
                arquivo))
            parcelas["cadastro"].append((num, spread))
            continue
        if spread < 0:
            pendencias.append(_pendencia(
                "CONTESTACAO", num, spread,
                f"Spread negativo na operação {num} (R$ {_fmt(spread)}): trava de 2 horas excedida. Fora da comissão, "
                "da nota e das divergências; contestar com a Ponte dentro do prazo de 5 dias úteis do e-mail. "
                "Valor da pendência = Spread R$ informado.",
                arquivo))
            parcelas["negativos"].append((num, spread))
            continue
        if op["status_compliance"].upper() == STATUS_RESSALVA and not ressalva_entra:
            pendencias.append(_pendencia(
                "OPERACAO_COM_RESSALVA", num, spread,
                f"Operação {num} com status {STATUS_RESSALVA}; a configuração manda não comissionar até confirmar. "
                f"Valor da pendência = Spread R$ (R$ {_fmt(spread)}).",
                arquivo))
            parcelas["ressalva"].append((num, spread))
            continue

        validas += 1
        comissao = normalize.q2(spread * participacao)
        a = acum.setdefault(op["cnpj"], {"total": Decimal("0"), "origens": []})
        a["total"] += comissao
        a["origens"].append(Origem(arquivo, num, comissao))

        contratado = _spread_contratado(por_cnpj[op["cnpj"]], op["data_contratacao"])
        if contratado is None:
            sem_spread += 1
            continue
        if abs(op["spread_pct"] - contratado) <= tolerancia_pp:
            continue
        diferenca = normalize.q2(spread - op["valor_me"] * op["ptax"] * contratado / CENTO)
        if abs(diferenca) < limiar:
            continue
        divergencias.append({
            "cnpj": op["cnpj"],
            "linha_negocio": "REMESSA",
            "ref_origem": num,
            "taxa_contratada_pct": contratado,
            "taxa_aplicada_pct": op["spread_pct"],
            "diferenca_brl": diferenca,
            "origens": [Origem(arquivo, num, diferenca)],
        })

    comissoes: list[ComissaoCalculada] = [
        {
            "cnpj": cnpj,
            "lojista": nomes[cnpj],
            "linha_negocio": "REMESSA",
            "comissao_brl": a["total"],
            "origens": sorted(a["origens"], key=lambda o: o.ref),
            "contratos_utilizados": [],
        }
        for cnpj, a in sorted(acum.items())
    ]

    soma_linhas = sum((o["spread_brl"] for o in operacoes), Decimal(0))
    rodape = relatorio["rodape"]
    dif_rodape = soma_linhas - rodape["spread_total_brl"]
    if dif_rodape != 0 or rodape["total_operacoes"] != len(operacoes):
        pendencias.append(_pendencia(
            "RODAPE_DIVERGENTE", "Operações!rodape", dif_rodape,
            f"Rodapé da Ponte informa {rodape['total_operacoes']} operações e R$ {_fmt(rodape['spread_total_brl'])}; "
            f"as linhas somam {len(operacoes)} e R$ {_fmt(soma_linhas)}. Valor da pendência = soma das linhas − rodapé.",
            arquivo))

    def total(nome):
        return sum((v for _, v in parcelas[nome]), Decimal(0))

    base = soma_linhas - total("repetidas") - total("negativos") - total("cadastro") - total("ressalva")
    return {
        "comissoes": comissoes,
        "divergencias": divergencias,
        "pendencias": pendencias,
        "resumo": {
            "linhas_relatorio": len(operacoes),
            "operacoes_distintas": len(ocorrencias),
            "validas": validas,
            "bloqueadas": len(operacoes) - validas,
            "sem_spread_contratado": sem_spread,
            "reconciliacao": {
                "rodape_spread_total_brl": rodape["spread_total_brl"],
                "soma_linhas_brl": soma_linhas,
                "repetidas_brl": total("repetidas"),
                "negativos_brl": total("negativos"),
                "cadastro_brl": total("cadastro"),
                "ressalva_brl": total("ressalva"),
                "base_comissao_brl": base,
                "comissao_brl": sum((c["comissao_brl"] for c in comissoes), Decimal(0)),
            },
            "reconciliacao_operacoes": {k: [r for r, _ in v] for k, v in parcelas.items()},
        },
    }
