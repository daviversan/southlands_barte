from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.regras.checkout import calcular_checkout, faixa_da_venda

D = Decimal
ARQ = "orbe.csv"


def tx(id_, data="2026-09-10", ec="111", mod="CREDITO A VISTA", parc=1, bruto="1000.00", tipo="VENDA"):
    return {"id_transacao": id_, "data_movimento": data, "ec": ec, "nome_origem": "NOME QUALQUER",
            "tipo_lancamento": tipo, "modalidade": mod, "qtd_parcelas": parc, "valor_bruto": D(bruto),
            "taxa_aplicada_pct": D("9.99"), "arquivo_origem": ARQ, "ref_origem": id_}


def contrato(ec="111", cnpj="00123456000199", ini=None, fim=None, ativo=True, ref="P!L1", **taxas):
    t = {"DEBITO": D("1.49"), "CREDITO_A_VISTA": D("2.59"), "CREDITO_2_6": D("3.19"),
         "CREDITO_7_12": D("3.79"), "PIX": D("0.89")}
    t.update({k: (None if v is None else D(v)) for k, v in taxas.items()})
    return {"cnpj": cnpj, "lojista": "Contrato", "ec": ec, "ativo": ativo, "vigencia_inicio": ini,
            "vigencia_fim": fim, "taxas_pct": t, "arquivo_origem": "taxas.xlsx", "ref_origem": ref}


CAD = {"111": {"cnpj": "00123456000199", "lojista": "Lojista Exemplo"}}


def calc(transacoes, contratos, cad=CAD, regras=None):
    return calcular_checkout(transacoes, contratos, cad, "2026-09", regras or {})


def test_comissao_usa_taxa_contratada_e_nao_a_aplicada():
    r = calc([tx("EXEMPLO-001")], [contrato()])
    c = r["comissoes"][0]
    assert c["comissao_brl"] == D("25.90")  # 1000 x 2,59%; a aplicada (9,99) é ignorada
    assert [(o.ref, o.valor) for o in c["origens"]] == [("EXEMPLO-001", D("25.90"))]
    assert c["lojista"] == "Lojista Exemplo" and c["linha_negocio"] == "CHECKOUT"
    assert c["contratos_utilizados"] == [{"arquivo_origem": "taxas.xlsx", "ref_origem": "P!L1"}]


def test_bridge_vigencia_14_e_15_de_setembro():
    cs = [contrato(fim="2026-09-14", ref="P!L6"),
          contrato(ini="2026-09-15", ref="P!L7", CREDITO_A_VISTA="2.19")]
    r = calc([tx("A", data="2026-09-14"), tx("B", data="2026-09-15")], cs)
    valores = {o.ref: o.valor for o in r["comissoes"][0]["origens"]}
    assert valores == {"A": D("25.90"), "B": D("21.90")}
    assert len(r["comissoes"][0]["contratos_utilizados"]) == 2


@pytest.mark.parametrize("mod,parc,faixa", [
    ("DEBITO", 1, "DEBITO"), ("PIX", 1, "PIX"), ("CREDITO A VISTA", 1, "CREDITO_A_VISTA"),
    ("CREDITO PARCELADO", 2, "CREDITO_2_6"), ("CREDITO PARCELADO", 6, "CREDITO_2_6"),
    ("CREDITO PARCELADO", 7, "CREDITO_7_12"), ("CREDITO PARCELADO", 12, "CREDITO_7_12"),
])
def test_faixas(mod, parc, faixa):
    assert faixa_da_venda(mod, parc) == faixa


@pytest.mark.parametrize("mod,parc", [("CREDITO PARCELADO", 1), ("CREDITO PARCELADO", 13),
                                      ("CREDITO A VISTA", 3), ("DEBITO", None), ("BOLETO", 1), (None, 1)])
def test_faixa_invalida(mod, parc):
    with pytest.raises(ValueError):
        faixa_da_venda(mod, parc)


def test_arredondamento_meio_para_cima():
    # 100,50 x 1,00% = 1,005 -> 1,01 (o round() do Python daria 1,00)
    r = calc([tx("A", bruto="100.50"), tx("B", bruto="100.50")], [contrato(CREDITO_A_VISTA="1.00")])
    c = r["comissoes"][0]
    assert [o.valor for o in c["origens"]] == [D("1.01"), D("1.01")]
    assert c["comissao_brl"] == D("2.02")


def test_taxa_ausente_bloqueia_sem_usar_taxa_aplicada():
    r = calc([tx("A", mod="PIX")], [contrato(PIX=None)])
    assert r["comissoes"] == []
    p = r["pendencias"][0]
    assert (p["tipo"], p["quem_decide"], p["valor_brl"]) == ("TAXA_AUSENTE", "Comercial", D("1000.00"))
    assert "valor bruto" in p["motivo"]


def test_ec_fora_do_cadastro_e_pendencia_nunca_erro():
    r = calc([tx("A", ec="999")], [contrato()])
    p = r["pendencias"][0]
    assert (p["tipo"], p["quem_decide"]) == ("CADASTRO_NAO_RESOLVIDO", "Financeiro")
    assert p["origens"][0].valor == D("1000.00")


def test_roteamento_por_config_vai_para_o_comercial():
    regras = {"checkout": {"ec_sem_cadastro": {"999": {"tipo": "CONTRATO_AUSENTE", "quem_decide": "Comercial", "motivo": "sem contrato"}}}}
    p = calc([tx("A", ec="999")], [contrato()], regras=regras)["pendencias"][0]
    assert (p["tipo"], p["quem_decide"]) == ("CONTRATO_AUSENTE", "Comercial")


def test_contrato_inativo_e_vigencia_sem_cobertura():
    assert calc([tx("A")], [contrato(ativo=False)])["pendencias"][0]["tipo"] == "CONTRATO_INATIVO"
    r = calc([tx("A", data="2026-09-01")], [contrato(ini="2026-09-15")])
    assert r["pendencias"][0]["tipo"] == "VIGENCIA_SEM_COBERTURA"


def test_vigencias_sobrepostas_sao_ambiguas():
    r = calc([tx("A")], [contrato(ref="P!L1"), contrato(ref="P!L2")])
    assert r["pendencias"][0]["tipo"] == "CONTRATO_AMBIGUO"


def test_cnpj_do_cadastro_diferente_da_planilha_e_ambiguo():
    r = calc([tx("A")], [contrato(cnpj="99999999000199")])
    assert r["pendencias"][0]["tipo"] == "CONTRATO_AMBIGUO"


def test_varios_problemas_numa_venda_geram_uma_so_pendencia():
    r = calc([tx("A", ec="999", mod="BOLETO")], [])
    assert len(r["pendencias"]) == 1
    assert "não consta no cadastro" in r["pendencias"][0]["motivo"] and "faixa" in r["pendencias"][0]["motivo"]


def test_so_remessa_sem_ec_nao_gera_pendencia_cadastral_mas_checkout_sem_ec_gera():
    vazio = dict(DEBITO=None, CREDITO_A_VISTA=None, CREDITO_2_6=None, CREDITO_7_12=None, PIX=None)
    so_remessa = contrato(ec=None, ref="P!L2", **vazio)
    com_checkout = contrato(ec=None, ref="P!L3")
    inativo = contrato(ec="222", ativo=False, ref="P!L4")
    p = calc([], [so_remessa, com_checkout, inativo])["pendencias"]
    assert [(x["ref_origem"], x["tipo"], x["valor_brl"]) for x in p] == [
        ("P!L3", "CADASTRO_NAO_RESOLVIDO", D("0")), ("P!L4", "CONTRATO_INATIVO", D("0"))]


def test_fora_de_escopo_conta_por_tipo_e_nao_vira_pendencia():
    ts = [tx("A"), tx("B", tipo="ESTORNO", bruto="-10.00"), tx("C", tipo="ANTECIPACAO", mod=None, parc=None),
          tx("D", tipo="REVERSAO ANTECIPACAO", mod=None, parc=None)]
    r = calc(ts, [contrato()])
    assert r["pendencias"] == []
    assert r["resumo"] == {"total_orbe": 4, "vendas_total": 1, "vendas_processadas": 1, "vendas_bloqueadas": 0,
                           "fora_escopo_por_tipo": {"ANTECIPACAO": 1, "ESTORNO": 1, "REVERSAO ANTECIPACAO": 1},
                           "contagens_por_arquivo": {ARQ: 4}}


def test_transacao_fora_da_competencia_e_erro_explicito():
    with pytest.raises(ValueError, match="fora da competência"):
        calc([tx("A", data="2026-10-01")], [contrato()])
    with pytest.raises(ValueError, match="competência inválida"):
        calcular_checkout([], [], {}, "09/2026", {})


def test_mesma_entrada_mesma_saida():
    ts = [tx("A"), tx("B", bruto="55.55")]
    assert calc(ts, [contrato()]) == calc(ts, [contrato()])


PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"
RAIZ = PACK.parent.parent


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_data_pack_conservacao_e_casos_de_borda():
    from src.ingest.orbe import ler_orbe
    from src.ingest.taxas import ler_taxas

    ts = ler_orbe(PACK)
    cs = ler_taxas(PACK / "02_tabela_taxas_contratadas.xlsx")
    cad = yaml.safe_load((RAIZ / "config/lojistas.yaml").read_text(encoding="utf-8"))["lojistas"]
    regras = yaml.safe_load((RAIZ / "config/regras.yaml").read_text(encoding="utf-8"))
    r = calcular_checkout(ts, cs, cad, "2026-09", regras)
    res = r["resumo"]
    assert res["total_orbe"] == 1957 and res["vendas_total"] == 1841
    assert res["vendas_processadas"] + res["vendas_bloqueadas"] == 1841
    assert res["fora_escopo_por_tipo"] == {"ANTECIPACAO": 38, "ESTORNO": 69, "REVERSAO ANTECIPACAO": 9}
    assert sorted(res["contagens_por_arquivo"].values()) == [14, 1943]
    # cada venda exatamente uma vez: comissão ou pendência bloqueante
    em_comissao = [o.ref for c in r["comissoes"] for o in c["origens"]]
    em_pendencia = [p["ref_origem"] for p in r["pendencias"] if p["ref_origem"].startswith("TX")]
    assert len(em_comissao) + len(em_pendencia) == 1841
    assert len(set(em_comissao) | set(em_pendencia)) == 1841
    # Σ origens = comissão (centavo exato)
    assert all(sum(o.valor for o in c["origens"]) == c["comissao_brl"] for c in r["comissoes"])
    # Atlas -> Comercial; Kiwi (inclusive o ajuste tardio) -> Financeiro; EC desconhecido nunca erro
    por_ref = {p["ref_origem"]: p for p in r["pendencias"]}
    assert por_ref["TX88447225"]["tipo"] == "CADASTRO_NAO_RESOLVIDO"
    assert por_ref["TX88447225"]["origens"][0].arquivo.startswith("06_")
    assert {p["tipo"]: p["quem_decide"] for p in r["pendencias"] if p["tipo"] == "CONTRATO_AUSENTE"} == {"CONTRATO_AUSENTE": "Comercial"}
    assert any(p["tipo"] == "CONTRATO_INATIVO" and p["valor_brl"] == 0 for p in r["pendencias"])
    # Bridge: 14/09 usa 2,59% e 15/09 em diante 2,19% (conferido na origem)
    bridge = next(c for c in r["comissoes"] if c["cnpj"] == "22224579000109")
    por_id = {t["id_transacao"]: t for t in ts}
    for o in bridge["origens"]:
        t = por_id[o.ref]
        if t["modalidade"] == "CREDITO A VISTA":
            taxa = D("2.59") if t["data_movimento"] <= "2026-09-14" else D("2.19")
            assert o.valor == (t["valor_bruto"] * taxa / 100).quantize(D("0.01"), rounding="ROUND_HALF_UP")
