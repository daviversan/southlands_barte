from decimal import Decimal

import pytest

from src.core.saida import Origem
from src.regras.notas import calcular_notas, gerar_notas

D = Decimal
REGRAS = {
    "checkout": {"nf_tomador": "lojista", "antecipacao_mesma_nota": True},
    "remessa": {"nf_tomador": {"cnpj": "75374179000146", "nome": "Ponte Câmbio"}},
    "notas": {"discriminacao_checkout": "Checkout {competencia}, {n_transacoes} transações",
              "discriminacao_remessa": "Remessa {competencia}, {n_transacoes} operações"},
}


def comissao(cnpj, linha, *valores, nome="Loja"):
    origens = [Origem("orbe.csv" if linha == "CHECKOUT" else "ponte.eml", f"{cnpj}-{i}", D(v))
               for i, v in enumerate(valores)]
    return {"cnpj": cnpj, "lojista": nome, "linha_negocio": linha,
            "comissao_brl": sum((o.valor for o in origens), D(0)), "origens": origens, "contratos_utilizados": []}


def test_uma_nf_por_lojista_e_uma_so_para_a_ponte():
    cs = [comissao("00000000000002", "CHECKOUT", "100.00", "21.00", "-4.20", nome="B"),
          comissao("00000000000001", "CHECKOUT", "10.00", nome="A"),
          comissao("11111111000111", "REMESSA", "131.01", "0.50"),  # REMESSA sintética (B)
          comissao("22222222000122", "REMESSA", "10.00")]
    notas, pendencias = calcular_notas(cs, "2026-09", REGRAS)
    assert pendencias == []
    assert [(n["linha_negocio"], n["tomador_cnpj"], n["tomador"], n["valor_brl"]) for n in notas] == [
        ("CHECKOUT", "00000000000001", "A", D("10.00")),
        ("CHECKOUT", "00000000000002", "B", D("116.80")),  # MDR + antecipação − reversão, mesma nota
        ("REMESSA", "75374179000146", "Ponte Câmbio", D("141.51")),
    ]
    assert notas[1]["discriminacao"] == "Checkout 2026-09, 3 transações"
    assert notas[2]["discriminacao"] == "Remessa 2026-09, 3 operações"
    # rastro da nota = as mesmas origens das comissões; Σ NF = Σ comissões
    assert notas[1]["origens"] == cs[0]["origens"]
    assert sorted(notas[2]["origens"], key=lambda o: o.ref) == sorted(cs[2]["origens"] + cs[3]["origens"], key=lambda o: o.ref)
    assert sum(n["valor_brl"] for n in notas) == sum(c["comissao_brl"] for c in cs)
    assert gerar_notas(cs, "2026-09", REGRAS) == notas


@pytest.mark.parametrize("valores", [("10.00", "-10.00"), ("-5.00",)])
def test_saldo_nao_positivo_nao_emite_nota_e_vira_pendencia(valores):
    c = comissao("00000000000001", "CHECKOUT", *valores)
    notas, pendencias = calcular_notas([c], "2026-09", REGRAS)
    assert notas == []
    p = pendencias[0]
    assert (p["tipo"], p["quem_decide"], p["ref_origem"], p["valor_brl"]) == (
        "NF_NAO_EMITIDA", "Financeiro", "00000000000001", c["comissao_brl"])
    assert p["origens"] == c["origens"]


def test_sem_comissao_nao_tem_nota_nem_pendencia_extra():
    assert calcular_notas([], "2026-09", REGRAS) == ([], [])


def test_configuracao_invalida_e_erro():
    with pytest.raises(ValueError, match="nf_tomador"):
        calcular_notas([], "2026-09", {**REGRAS, "checkout": {"nf_tomador": "matriz"}})
    with pytest.raises(ValueError, match="discriminacao_checkout"):
        calcular_notas([comissao("00000000000001", "CHECKOUT", "1.00")], "2026-09", {**REGRAS, "notas": {}})
