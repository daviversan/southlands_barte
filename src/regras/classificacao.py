"""Classificação dos lançamentos bancários por regra (nível Alvo; sem IA).

Regras em `regras.bancos.regras`, lista **ordenada**: a primeira que casa vence (padrão específico
antes do genérico, ex.: `PIX ENVIADO CONTABILIDADE` antes de `PIX ENVIADO <lojista>`). O casamento é
sobre a descrição normalizada (sem acento, maiúsculas, espaços colapsados).

Cada regra: `id`, `banco` (AURORA, MERIDIANO ou *), `padrao` (regex) e uma destas formas de conta:
- `conta`: código fixo;
- `conta_por_modo`: {modo: código | null}, escolhido por `bancos.folha_e_impostos_de_08`. Conta
  null = não há conta no plano para esse modo: a linha vira `LANCAMENTO_NAO_CLASSIFICADO`.
Opcionais: `pendencia` (abre a pendência indicada além de classificar) e `contrapartida` (id da regra
do outro banco que deve ter a entrada de mesmo valor; sem par -> `TRANSFERENCIA_SEM_CONTRAPARTIDA`).

Conta fora do plano (ou sintética) é erro de configuração, não pendência. Linha sem regra:
`metodo = HUMANO`, `confianca = 0`, `conta_codigo` vazio e pendência.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from src.core.contratos import (
    ContaContabil,
    LancamentoBancario,
    LancamentoClassificado,
    Origem,
    PendenciaCalculada,
    ResultadoBancos,
)
from src.core.saida import BANCOS
_PENDENCIAS_DE_REGRA = ("CREDITO_NAO_IDENTIFICADO",)
MODOS_FOLHA = ("baixa_provisao", "despesa")


def normalizar_descricao(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _data_br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _banco(nome: str) -> str:
    return nome.capitalize()


def _fmt(valor: Decimal) -> str:
    inteiro, _, frac = f"{valor:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    return f"{sinal}{int(inteiro.lstrip('-')):,}".replace(",", ".") + f",{frac}"


def _preparar_regras(cfg: dict, analiticas: set[str]) -> list[dict]:
    modo = cfg.get("folha_e_impostos_de_08", "baixa_provisao")
    if modo not in MODOS_FOLHA:
        raise ValueError(f"bancos.folha_e_impostos_de_08 deve ser um de {MODOS_FOLHA} (veio {modo!r})")
    regras = cfg.get("regras")
    if not isinstance(regras, list) or not regras:
        raise ValueError("bancos.regras deve ser uma lista não vazia")
    ids: set[str] = set()
    preparadas = []
    for r in regras:
        rid = r.get("id")
        if not rid or rid in ids:
            raise ValueError(f"bancos.regras: id ausente ou repetido ({rid!r})")
        ids.add(rid)
        banco = r.get("banco", "*")
        if banco != "*" and banco not in BANCOS:
            raise ValueError(f"regra {rid}: banco inválido {banco!r}")
        if ("conta" in r) == ("conta_por_modo" in r):
            raise ValueError(f"regra {rid}: informe exatamente um de conta / conta_por_modo")
        if "conta_por_modo" in r:
            por_modo = r["conta_por_modo"] or {}
            if set(por_modo) != set(MODOS_FOLHA):
                raise ValueError(f"regra {rid}: conta_por_modo precisa de {MODOS_FOLHA}")
            conta = por_modo[modo]
        else:
            conta = r["conta"]
        if conta is not None and str(conta) not in analiticas:
            raise ValueError(f"regra {rid}: conta {conta!r} não existe no plano ou não aceita lançamento")
        if r.get("pendencia") and r["pendencia"] not in _PENDENCIAS_DE_REGRA:
            raise ValueError(f"regra {rid}: pendência {r['pendencia']!r} não suportada")
        preparadas.append({"id": rid, "banco": banco, "regex": re.compile(r["padrao"]),
                           "conta": None if conta is None else str(conta),
                           "pendencia": r.get("pendencia"), "contrapartida": r.get("contrapartida")})
    for r in preparadas:
        if r["contrapartida"] and r["contrapartida"] not in ids:
            raise ValueError(f"regra {r['id']}: contrapartida {r['contrapartida']!r} não existe")
    return preparadas


def _pendencia(tipo: str, l: LancamentoBancario, motivo: str) -> PendenciaCalculada:
    return {
        "tipo": tipo,
        "ref_origem": l["ref_origem"],
        "valor_brl": l["valor"],
        "motivo": motivo,
        "quem_decide": "Financeiro",
        "origens": [Origem(l["arquivo_origem"], l["ref_origem"], l["valor"])],
    }


def classificar_lancamentos(
    lancamentos: list[LancamentoBancario],
    plano: list[ContaContabil],
    regras: dict,
) -> ResultadoBancos:
    cfg = (regras or {}).get("bancos") or {}
    analiticas = {c["codigo"] for c in plano if c["aceita_lancto"]}
    lista = _preparar_regras(cfg, analiticas)
    janela = int(cfg.get("janela_contrapartida_dias", 3))

    classificados: list[LancamentoClassificado] = []
    pendencias: list[PendenciaCalculada] = []
    regra_de: dict[int, str] = {}
    por_regra: Counter[str] = Counter()

    for i, l in enumerate(lancamentos):
        desc = normalizar_descricao(l["descricao"])
        regra = next((r for r in lista if r["banco"] in ("*", l["banco"]) and r["regex"].search(desc)), None)
        if regra is not None and regra["conta"] is not None:
            regra_de[i] = regra["id"]
            por_regra[regra["id"]] += 1
            classificados.append({
                **l, "conta_codigo": regra["conta"], "metodo": "REGRA", "confianca": Decimal(1),
                "regra_id": regra["id"], "origens": [Origem(l["arquivo_origem"], l["ref_origem"], l["valor"])],
            })
            if regra["pendencia"] == "CREDITO_NAO_IDENTIFICADO":
                pendencias.append(_pendencia(
                    "CREDITO_NAO_IDENTIFICADO", l,
                    f"Entraram R$ {_fmt(l['valor'])} em {_data_br(l['data'])} no {_banco(l['banco'])} sem identificação "
                    f"de quem pagou (\"{l['descricao']}\"). Não sabemos quem pagou nem por quê; o valor foi lançado "
                    f"provisoriamente em créditos não identificados ({regra['conta']})."))
            continue
        motivo = (f"O lançamento \"{l['descricao']}\" de R$ {_fmt(l['valor'])} em {_data_br(l['data'])} no "
                  f"{_banco(l['banco'])} ")
        if regra is None:
            motivo += "não se encaixa em nenhum padrão conhecido de extrato; falta escolher a conta contábil."
        else:
            motivo += ("é folha ou imposto de agosto e, no tratamento escolhido para esses pagamentos "
                       f"({cfg.get('folha_e_impostos_de_08', 'baixa_provisao').replace('_', ' ')}), "
                       "o plano de contas não tem conta para ele.")
        classificados.append({
            **l, "conta_codigo": "", "metodo": "HUMANO", "confianca": Decimal(0), "regra_id": None,
            "origens": [Origem(l["arquivo_origem"], l["ref_origem"], l["valor"])],
        })
        pendencias.append(_pendencia("LANCAMENTO_NAO_CLASSIFICADO", l, motivo))

    pendencias += _contrapartidas(lancamentos, regra_de, lista, janela)
    humano = sum(1 for c in classificados if c["metodo"] == "HUMANO")
    return {
        "lancamentos": classificados,
        "pendencias": pendencias,
        "resumo": {
            "total_aurora": sum(1 for l in lancamentos if l["banco"] == "AURORA"),
            "total_meridiano": sum(1 for l in lancamentos if l["banco"] == "MERIDIANO"),
            "por_regra": dict(sorted(por_regra.items())),
            "humano": humano,
        },
    }


def _contrapartidas(lancamentos, regra_de, lista, janela) -> list[PendenciaCalculada]:
    """Cada saída de regra com `contrapartida` procura uma entrada de mesmo valor absoluto na regra
    indicada, com data entre a da saída e + janela. Cada entrada casa no máximo uma vez."""
    pendencias: list[PendenciaCalculada] = []
    for regra in (r for r in lista if r["contrapartida"]):
        saidas = sorted((i for i, rid in regra_de.items() if rid == regra["id"]),
                        key=lambda i: (lancamentos[i]["data"], i))
        entradas = sorted((i for i, rid in regra_de.items() if rid == regra["contrapartida"]),
                          key=lambda i: (lancamentos[i]["data"], i))
        usadas: set[int] = set()
        for i in saidas:
            s = lancamentos[i]
            inicio = date.fromisoformat(s["data"])
            fim = (inicio + timedelta(days=janela)).isoformat()
            par = next((j for j in entradas if j not in usadas
                        and abs(lancamentos[j]["valor"]) == abs(s["valor"])
                        and s["data"] <= lancamentos[j]["data"] <= fim), None)
            if par is not None:
                usadas.add(par)
                continue
            pendencias.append(_pendencia(
                "TRANSFERENCIA_SEM_CONTRAPARTIDA", s,
                f"Saíram R$ {_fmt(abs(s['valor']))} do {_banco(s['banco'])} em {_data_br(s['data'])} como transferência "
                f"entre contas da Tarvo, mas a entrada do mesmo valor não aparece no outro banco em até {janela} "
                "dia(s). Pode ser só a virada do mês (a entrada cairia no extrato seguinte). O lançamento continua "
                "classificado normalmente."))
    return pendencias
