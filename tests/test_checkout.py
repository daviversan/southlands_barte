from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.regras.checkout import calcular_checkout, faixa_da_venda

D = Decimal
ARQ = "orbe.csv"


def tx(id_, data="2026-09-10", ec="111", mod="CREDITO A VISTA", parc=1, bruto="1000.00", tipo="VENDA",
       aplicada="9.99", ref=None, original=None):
    return {"id_transacao": id_, "data_movimento": data, "ec": ec, "nome_origem": "NOME QUALQUER",
            "tipo_lancamento": tipo, "modalidade": mod, "qtd_parcelas": parc, "valor_bruto": D(bruto),
            "taxa_aplicada_pct": D(aplicada), "arquivo_origem": ARQ, "ref_origem": id_,
            "id_referencia": ref, "data_venda_original": original}


def contrato(ec="111", cnpj="00123456000199", ini=None, fim=None, ativo=True, ref="P!L1", **taxas):
    t = {"DEBITO": D("1.49"), "CREDITO_A_VISTA": D("2.59"), "CREDITO_2_6": D("3.19"),
         "CREDITO_7_12": D("3.79"), "PIX": D("0.89"), "ANTECIPACAO": D("2.10")}
    t.update({k: (None if v is None else D(v)) for k, v in taxas.items()})
    return {"cnpj": cnpj, "lojista": "Contrato", "ec": ec, "ativo": ativo, "vigencia_inicio": ini,
            "vigencia_fim": fim, "taxas_pct": t, "spread_remessa_pct": None,
            "arquivo_origem": "taxas.xlsx", "ref_origem": ref}


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
    vazio = dict(DEBITO=None, CREDITO_A_VISTA=None, CREDITO_2_6=None, CREDITO_7_12=None, PIX=None, ANTECIPACAO=None)
    so_remessa = contrato(ec=None, ref="P!L2", **vazio)
    com_checkout = contrato(ec=None, ref="P!L3")
    inativo = contrato(ec="222", ativo=False, ref="P!L4")
    p = calc([], [so_remessa, com_checkout, inativo])["pendencias"]
    assert [(x["ref_origem"], x["tipo"], x["valor_brl"]) for x in p] == [
        ("P!L3", "CADASTRO_NAO_RESOLVIDO", D("0")), ("P!L4", "CONTRATO_INATIVO", D("0"))]


def test_todos_os_tipos_entram_e_resumo_conserva():
    ts = [tx("A"), tx("B", tipo="ESTORNO", bruto="-10.00", ref="A", original="2026-09-10"),
          tx("C", tipo="ANTECIPACAO", mod=None, parc=None),
          tx("D", tipo="REVERSAO ANTECIPACAO", mod=None, parc=None, bruto="-200.00", ref="C", original="2026-09-10")]
    r = calc(ts, [contrato()])
    assert r["pendencias"] == []
    assert {o.ref: o.valor for o in r["comissoes"][0]["origens"]} == {
        "A": D("25.90"), "B": D("-0.26"), "C": D("21.00"), "D": D("-4.20")}
    assert r["comissoes"][0]["comissao_brl"] == D("42.44")
    res = r["resumo"]
    assert res["fora_escopo_por_tipo"] == {}
    assert res["linhas_processadas"] + res["linhas_bloqueadas"] == res["total_orbe"] == 4
    assert res["por_tipo"]["ESTORNO"] == {"total": 1, "processadas": 1, "bloqueadas": 0}


def test_estorno_de_agosto_abate_setembro_com_taxa_da_venda_original():
    # venda original fora do arquivo: resolvido por data_venda_original + EC, nunca ignorado
    cs = [contrato(fim="2026-08-31", ref="P!L1", CREDITO_A_VISTA="3.00"), contrato(ini="2026-09-01", ref="P!L2")]
    r = calc([tx("V"), tx("E", data="2026-09-05", tipo="ESTORNO", bruto="-1000.00", ref="TX-AGOSTO",
                       original="2026-08-20", aplicada="3.00")], cs)
    c = r["comissoes"][0]
    assert {o.ref: o.valor for o in c["origens"]} == {"V": D("25.90"), "E": D("-30.00")}
    assert c["comissao_brl"] == D("-4.10")  # a comissão de setembro cai; agosto não reabre
    assert [d["ref_origem"] for d in r["divergencias"]] == ["V"]  # estorno: aplicada = contratada de agosto


def test_bridge_estorno_depois_de_15_09_de_venda_anterior_usa_2_59():
    cs = [contrato(fim="2026-09-14", ref="P!L6"), contrato(ini="2026-09-15", ref="P!L7", CREDITO_A_VISTA="2.19")]
    ts = [tx("V", data="2026-09-10", aplicada="2.59"),
          tx("E", data="2026-09-20", tipo="ESTORNO", bruto="-1000.00", ref="V", original="2026-09-10", aplicada="2.59")]
    r = calc(ts, cs)
    assert {o.ref: o.valor for o in r["comissoes"][0]["origens"]} == {"V": D("25.90"), "E": D("-25.90")}
    assert r["divergencias"] == []  # 2,59 aplicada = 2,59 contratada na data original


def test_reversao_anula_so_a_taxa_da_antecipacao():
    ts = [tx("V", bruto="5000.00"), tx("ANT", tipo="ANTECIPACAO", mod=None, parc=None, bruto="4000.00"),
          tx("REV", tipo="REVERSAO ANTECIPACAO", mod=None, parc=None, bruto="-4000.00", ref="ANT", original="2026-09-10")]
    origens = {o.ref: o.valor for o in calc(ts, [contrato()])["comissoes"][0]["origens"]}
    assert origens == {"V": D("129.50"), "ANT": D("84.00"), "REV": D("-84.00")}  # MDR da venda intacto


def test_antecipacao_sem_taxa_bloqueia():
    r = calc([tx("ANT", tipo="ANTECIPACAO", mod=None, parc=None)], [contrato(ANTECIPACAO=None)])
    assert r["pendencias"][0]["tipo"] == "TAXA_AUSENTE"


@pytest.mark.parametrize("linha,trecho", [
    (tx("E", tipo="ESTORNO", bruto="10.00", ref="X", original="2026-09-01"), "não negativo"),
    (tx("E", tipo="ESTORNO", bruto="-10.00", ref="X", original=None), "sem data da venda original"),
    (tx("E", tipo="ESTORNO", bruto="-10.00", ref="X", original="2026-09-20"), "posterior"),
    (tx("ANT", tipo="ANTECIPACAO", mod=None, parc=None, bruto="-1.00"), "não positivo"),
    (tx("Z", tipo="AJUSTE MISTERIOSO"), "desconhecido"),
])
def test_lancamento_invalido_vira_pendencia_com_bruto_assinado(linha, trecho):
    r = calc([linha], [contrato()])
    p = r["pendencias"][0]
    assert (p["tipo"], p["quem_decide"]) == ("LANCAMENTO_INVALIDO", "Financeiro")
    assert trecho in p["motivo"] and p["valor_brl"] == linha["valor_bruto"]
    assert r["resumo"]["linhas_bloqueadas"] == 1 and r["resumo"]["fora_escopo_por_tipo"] == {}


def test_estorno_incompativel_com_a_original_e_estorno_em_dobro():
    ts = [tx("V"), tx("ANT", tipo="ANTECIPACAO", mod=None, parc=None),
          tx("E1", tipo="ESTORNO", bruto="-10.00", ref="V", original="2026-09-10"),
          tx("E2", tipo="ESTORNO", bruto="-10.00", ref="V", original="2026-09-10"),
          tx("E3", tipo="ESTORNO", bruto="-10.00", ref="ANT", original="2026-09-10")]
    r = calc(ts, [contrato()])
    por_ref = {p["ref_origem"]: p for p in r["pendencias"]}
    assert set(por_ref) == {"E2", "E3"}
    assert "Segundo ESTORNO" in por_ref["E2"]["motivo"] and "esperado VENDA" in por_ref["E3"]["motivo"]


def test_divergencia_compara_taxas_com_sinal_e_ignora_truncamento():
    ts = [tx("IGUAL", bruto="608.88", aplicada="2.59"),  # Orbe truncaria a taxa: não é divergência
          tx("MAIOR", aplicada="3.09"),
          tx("EST", tipo="ESTORNO", bruto="-500.00", ref="MAIOR", original="2026-09-10", aplicada="3.09"),
          tx("NFIM", bruto="0.50", aplicada="3.59")]  # 0,50 x 1 p.p. = 0,005 -> 0,01 >= limiar
    r = calc(ts, [contrato()], regras={"checkout": {"limiar_divergencia_brl": 0.01}})
    d = {x["ref_origem"]: x for x in r["divergencias"]}
    assert set(d) == {"MAIOR", "EST", "NFIM"}
    assert (d["MAIOR"]["taxa_contratada_pct"], d["MAIOR"]["taxa_aplicada_pct"], d["MAIOR"]["diferenca_brl"]) == (
        D("2.59"), D("3.09"), D("5.00"))
    assert d["EST"]["diferenca_brl"] == D("-2.50")  # devolução do excesso: sinal acompanha o bruto
    assert d["MAIOR"]["origens"] == [type(d["MAIOR"]["origens"][0])(ARQ, "MAIOR", D("5.00"))]
    r = calc([tx("P", bruto="0.40", aplicada="3.59")], [contrato()], regras={"checkout": {"limiar_divergencia_brl": 0.01}})
    assert r["divergencias"] == []  # 0,004 -> 0,00 < limiar


def test_linha_bloqueada_nao_gera_divergencia():
    r = calc([tx("A", ec="999", aplicada="4.49")], [contrato()])
    assert r["divergencias"] == [] and r["pendencias"][0]["tipo"] == "CADASTRO_NAO_RESOLVIDO"


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
    assert res["linhas_processadas"] + res["linhas_bloqueadas"] == 1957
    assert res["fora_escopo_por_tipo"] == {}
    assert {t: c["total"] for t, c in res["por_tipo"].items()} == {
        "ANTECIPACAO": 38, "ESTORNO": 69, "REVERSAO ANTECIPACAO": 9, "VENDA": 1841}
    assert sorted(res["contagens_por_arquivo"].values()) == [14, 1943]
    # cada linha exatamente uma vez: comissão ou pendência bloqueante
    em_comissao = [o.ref for c in r["comissoes"] for o in c["origens"]]
    em_pendencia = [p["ref_origem"] for p in r["pendencias"] if p["origens"][0].arquivo.endswith(".csv")]
    assert len(em_comissao) + len(em_pendencia) == 1957
    assert len(set(em_comissao) | set(em_pendencia)) == 1957
    # Σ origens = comissão (centavo exato)
    assert all(sum(o.valor for o in c["origens"]) == c["comissao_brl"] for c in r["comissoes"])
    # as 5 taxas fora da aba vigente terminam em divergência ou pendência; nenhuma silenciada
    divergentes = {d["ref_origem"] for d in r["divergencias"]}
    for t in ts:
        if t["taxa_aplicada_pct"] in {D("0.99"), D("1.99"), D("3.99"), D("4.09"), D("4.49")}:
            assert t["id_transacao"] in divergentes or t["id_transacao"] in em_pendencia
    # estornos com a venda original fora do arquivo (agosto) são resolvidos, nunca ignorados
    ids = {t["id_transacao"] for t in ts}
    agosto = [t for t in ts if t["tipo_lancamento"] == "ESTORNO" and t["id_referencia"] not in ids]
    assert len(agosto) == 9 and all(t["data_venda_original"] < "2026-09-01" for t in agosto)
    assert all(t["id_transacao"] in em_comissao or t["id_transacao"] in em_pendencia for t in agosto)
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
            data = t["data_venda_original"] if t["tipo_lancamento"] == "ESTORNO" else t["data_movimento"]
            taxa = D("2.59") if data <= "2026-09-14" else D("2.19")
            assert o.valor == (t["valor_bruto"] * taxa / 100).quantize(D("0.01"), rounding="ROUND_HALF_UP")
