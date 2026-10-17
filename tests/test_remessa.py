from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.regras.remessa import calcular_remessa

D = Decimal
EML = "03_ponte.eml"
REGRAS = {"remessa": {"participacao_tarvo": 0.5, "precisao_spread_pct": 0.00001,
                      "aprovado_com_ressalva_entra": True}}
PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"
RAIZ = PACK.parent.parent


def op(num, cnpj="11111111000111", spread="100.01", pct="1.5", me="1000", ptax="6.6667", data="2026-09-10",
       moeda="USD", status="APROVADO", linha=6):
    return {"num_operacao": num, "linha": linha, "data_contratacao": data, "data_liquidacao": data, "cnpj": cnpj,
            "cliente_origem": "NOME TRUNCADO", "moeda": moeda, "valor_me": D(me), "taxa_cliente": None,
            "ptax": D(ptax), "valor_brl": None, "spread_brl": D(spread), "spread_pct": D(pct),
            "spread_estimado_d1_brl": D("999"), "iof_brl": None, "status_compliance": status, "observacao": None,
            "arquivo_origem": EML, "ref_origem": num}


def contrato(cnpj="11111111000111", spread="1.5", nome="Loja Planilha"):
    return {"cnpj": cnpj, "lojista": nome, "ec": None, "ativo": True, "vigencia_inicio": None, "vigencia_fim": None,
            "taxas_pct": {}, "spread_remessa_pct": None if spread is None else D(spread),
            "arquivo_origem": "taxas.xlsx", "ref_origem": "T!L1"}


def relatorio(ops, total=None, spread_total=None):
    return {"operacoes": ops, "arquivo_origem": EML, "competencia": "2026-09",
            "rodape": {"total_operacoes": len(ops) if total is None else total,
                       "spread_total_brl": sum((o["spread_brl"] for o in ops), D(0)) if spread_total is None else D(spread_total)}}


def calc(ops, contratos=None, cadastro=None, regras=REGRAS, **rodape):
    return calcular_remessa(relatorio(ops, **rodape), contratos or [contrato()], cadastro or {}, "2026-09", regras)


def test_comissao_50_do_realizado_por_operacao_e_nome_do_cadastro():
    r = calc([op("PC-1", spread="100.01"), op("PC-2", spread="0.03", data="2026-09-11")],
             cadastro={"123": {"cnpj": "11111111000111", "lojista": "Loja Cadastro"}})
    c = r["comissoes"][0]
    assert (c["linha_negocio"], c["lojista"], c["contratos_utilizados"]) == ("REMESSA", "Loja Cadastro", [])
    assert [(o.arquivo, o.ref, o.valor) for o in c["origens"]] == [(EML, "PC-1", D("50.01")), (EML, "PC-2", D("0.02"))]
    assert c["comissao_brl"] == D("50.03")  # por operação (H1); o estimado D-1 nunca é base


def test_repetida_negativo_e_reconciliacao():
    ops = [op("PC-1", spread="821.88"), op("PC-1", spread="821.88", linha=7), op("PC-2", spread="-687.52", data="2026-09-11"),
           op("PC-3", spread="200.00", data="2026-09-12")]
    r = calc(ops)
    por_tipo = {p["tipo"]: p for p in r["pendencias"]}
    rep, cont = por_tipo["OPERACAO_REPETIDA"], por_tipo["CONTESTACAO"]
    assert (rep["ref_origem"], rep["valor_brl"], rep["origens"][0].ref) == ("PC-1#2", D("821.88"), "PC-1#2")
    assert (cont["ref_origem"], cont["valor_brl"], cont["quem_decide"]) == ("PC-2", D("-687.52"), "Financeiro")
    assert "trava de 2 horas excedida" in cont["motivo"] and "5 dias úteis" in cont["motivo"]
    assert "OPERACAO_POSSIVEL_DUPLICIDADE" not in por_tipo  # repetida não reaparece como duplicidade
    assert [o.ref for o in r["comissoes"][0]["origens"]] == ["PC-1", "PC-3"]
    assert r["divergencias"] == []
    res = r["resumo"]
    assert (res["linhas_relatorio"], res["operacoes_distintas"], res["validas"], res["bloqueadas"]) == (4, 3, 2, 2)
    rec = res["reconciliacao"]
    assert rec["base_comissao_brl"] == rec["rodape_spread_total_brl"] - D("821.88") + D("687.52") == D("1021.88")
    assert res["reconciliacao_operacoes"]["negativos"] == ["PC-2"]


def test_possivel_duplicidade_so_sinaliza():
    r = calc([op("PC-1"), op("PC-9")])
    p = next(p for p in r["pendencias"] if p["tipo"] == "OPERACAO_POSSIVEL_DUPLICIDADE")
    assert (p["ref_origem"], p["valor_brl"]) == ("PC-9", D("0"))
    assert len(r["comissoes"][0]["origens"]) == 2


def test_cnpj_fora_da_planilha_ressalva_e_rodape():
    r = calc([op("PC-1", cnpj="99999999000199")])
    assert [p["tipo"] for p in r["pendencias"]] == ["CADASTRO_NAO_RESOLVIDO"] and r["comissoes"] == []
    sem_ressalva = {"remessa": {**REGRAS["remessa"], "aprovado_com_ressalva_entra": False}}
    assert calc([op("PC-1", status="APROVADO C/ RESSALVA")], regras=sem_ressalva)["pendencias"][0]["tipo"] == "OPERACAO_COM_RESSALVA"
    assert calc([op("PC-1", status="APROVADO C/ RESSALVA")])["comissoes"][0]["comissao_brl"] == D("50.01")
    p = calc([op("PC-1")], total=2, spread_total="90.00")["pendencias"][0]
    assert (p["tipo"], p["ref_origem"], p["valor_brl"]) == ("RODAPE_DIVERGENTE", "Operações!rodape", D("10.01"))


def test_divergencia_valor_cheio_e_tolerancia_em_pontos_percentuais():
    # Spread % igual ao contratado; Spread R$ difere ~R$ 0,03 do cálculo pelo percentual: não é divergência
    ok = op("PC-OK", spread="150.03", pct="1.50000", me="1000", ptax="10")
    dentro = op("PC-DENTRO", spread="150.10", pct="1.50090", me="1000", ptax="10", data="2026-09-11")  # 0,0009 p.p.
    fora = op("PC-FORA", spread="250.00", pct="2.50000", me="1000", ptax="10", data="2026-09-12")
    r = calc([ok, dentro, fora])
    assert [(d["ref_origem"], d["taxa_contratada_pct"], d["taxa_aplicada_pct"], d["diferenca_brl"]) for d in r["divergencias"]] == [
        ("PC-FORA", D("1.5"), D("2.50000"), D("100.00"))]  # cheio: 250 − 1000×10×1,5%, não a metade
    assert r["divergencias"][0]["origens"][0].valor == D("100.00")


def test_spread_padrao_nao_calcula_divergencia_mas_comissiona():
    r = calc([op("PC-1", pct="3.0")], contratos=[contrato(spread=None)])
    assert r["divergencias"] == [] and r["resumo"]["sem_spread_contratado"] == 1
    assert r["comissoes"][0]["comissao_brl"] == D("50.01")


def test_fora_da_competencia_e_erro():
    with pytest.raises(ValueError, match="fora da competência"):
        calc([op("PC-1", data="2026-10-01")])


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_data_pack_ponte():
    from src.ingest.ponte import ler_ponte
    from src.ingest.taxas import ler_taxas

    rel = ler_ponte(PACK / "03_email_ponte_cambio_relatorio_set2026.eml")
    assert len(rel["operacoes"]) == 233 and rel["competencia"] == "2026-09"
    assert rel["rodape"] == {"total_operacoes": 233, "spread_total_brl": D("78073.59")}
    assert sum(o["spread_brl"] for o in rel["operacoes"]) == D("78073.59")
    assert all(len(o["cnpj"]) == 14 for o in rel["operacoes"])
    assert rel["operacoes"][0]["arquivo_origem"].endswith(".eml")
    cs = ler_taxas(PACK / "02_tabela_taxas_contratadas.xlsx")
    cad = yaml.safe_load((RAIZ / "config/lojistas.yaml").read_text(encoding="utf-8"))["lojistas"]
    regras = yaml.safe_load((RAIZ / "config/regras.yaml").read_text(encoding="utf-8"))
    r = calcular_remessa(rel, cs, cad, "2026-09", regras)
    res = r["resumo"]
    assert (res["validas"], res["bloqueadas"], res["sem_spread_contratado"]) == (228, 5, 51)
    assert res["reconciliacao"]["base_comissao_brl"] == D("79085.76")
    assert sum(c["comissao_brl"] for c in r["comissoes"]) == D("39543.45")
    assert len(r["comissoes"]) == 14
    contestacoes = sorted(p["ref_origem"] for p in r["pendencias"] if p["tipo"] == "CONTESTACAO")
    assert contestacoes == ["PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"]
    assert [p["ref_origem"] for p in r["pendencias"] if p["tipo"] == "OPERACAO_REPETIDA"] == ["PC-0926-0162#2"]
    em_comissao = {o.ref for c in r["comissoes"] for o in c["origens"]}
    assert not em_comissao & set(contestacoes)
    assert not {d["ref_origem"] for d in r["divergencias"]} & set(contestacoes)
    assert len(r["divergencias"]) == 41
