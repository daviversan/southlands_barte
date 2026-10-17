from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.ingest.bancos import ler_aurora, ler_meridiano
from src.ingest.plano import ler_plano
from src.regras.classificacao import classificar_lancamentos

D = Decimal
PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"
RAIZ = PACK.parent.parent
REGRAS = yaml.safe_load((RAIZ / "config/regras.yaml").read_text(encoding="utf-8"))
PLANO_TXT = """COD_CONTA;DESCRICAO;TIPO;NATUREZA;ACEITA_LANCTO;COD_SUPERIOR;DT_CRIACAO
4.2;DESPESAS ADMINISTRATIVAS;SINTETICA;D;N;4;15/01/2024
"""


def plano_completo():
    return ler_plano(PACK / "04_plano_de_contas_fenix_erp.csv")


def lanc(desc, valor="-10.00", banco="AURORA", ref="L9", data="2026-09-10"):
    return {"banco": banco, "ref_origem": ref, "data": data, "descricao": desc, "valor": D(valor),
            "arquivo_origem": "05a.csv" if banco == "AURORA" else "05b.ofx"}


def classificar(ls, regras=REGRAS):
    return classificar_lancamentos(ls, plano_completo(), regras)


def test_aurora_cabecalho_saldos_aviso_e_offset(tmp_path):
    texto = ("Banco Aurora S.A.;;;;\nPeríodo;;;;\nData;Lançamento;Documento;Valor (R$);Saldo (R$)\n"
             "31/08/2026;SALDO ANTERIOR;;;612.334,81\n01/09/2026;TAR PACOTE SERVICOS PJ;;-389,00;1,00\n"
             "02/09/2026;TED RECEBIDA ORBE;1;1.209.630,03;2,00\n;;;;\n;SALDO FINAL;;;2,00\n"
             ";Os lançamentos estão sujeitos a confirmação.;;;\n")
    p = tmp_path / "05a.csv"
    p.write_text(texto, encoding="utf-8")
    ls = ler_aurora(p)
    assert [(l["ref_origem"], l["data"], l["valor"]) for l in ls] == [
        ("L5", "2026-09-01", D("-389.00")), ("L6", "2026-09-02", D("1209630.03"))]
    assert [l["ref_origem"] for l in ler_aurora(p, {"bancos": {"aurora_ref_offset": 1}})] == ["L6", "L7"]


def test_meridiano_sgml_cp1252(tmp_path):
    corpo = ("OFXHEADER:100\r\n<OFX><BANKTRANLIST>\r\n<STMTTRN>\r\n<TRNTYPE>CREDIT\r\n<DTPOSTED>20260901120000[-3:BRT]\r\n"
             "<TRNAMT>207215.87\r\n<FITID>MRD1\r\n<MEMO>PIX RECEB MUNDO ABERTO INTERCÂMBIO\r\n</STMTTRN>\r\n"
             "</BANKTRANLIST><LEDGERBAL>\r\n<BALAMT>1.00\r\n</LEDGERBAL></OFX>\r\n")
    p = tmp_path / "05b.ofx"
    p.write_bytes(corpo.encode("cp1252"))
    (l,) = ler_meridiano(p)
    assert (l["ref_origem"], l["data"], l["valor"], l["descricao"]) == (
        "MRD1", "2026-09-01", D("207215.87"), "PIX RECEB MUNDO ABERTO INTERCÂMBIO")


def test_plano_so_analiticas_aceitam(tmp_path):
    p = tmp_path / "plano.csv"
    p.write_bytes((PLANO_TXT + "4.2.01;Tarifas bancárias;ANALITICA;D;S;4.2;15/01/2024\n").encode("iso-8859-1"))
    assert [(c["codigo"], c["aceita_lancto"]) for c in ler_plano(p)] == [("4.2", False), ("4.2.01", True)]
    assert ler_plano(p)[1]["descricao"] == "Tarifas bancárias"


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
@pytest.mark.parametrize("desc,valor,conta", [
    ("PIX ENVIADO CONTABILIDADE EXATA LTDA", "-4500.00", "4.2.06"),  # não 2.1.01.001
    ("PIX ENVIADO ROTA GLOBAL INTERCAMBIO LT", "-77106.46", "2.1.01.001"),
    ("DEVOLUCAO PIX - MUNDO ABERTO INTERC", "-1200.00", "2.1.01.002"),
    ("PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO", "7350.00", "1.1.09.002"),
])
def test_casos_armadilha(desc, valor, conta):
    r = classificar([lanc(desc, valor)])
    (l,) = r["lancamentos"]
    assert (l["conta_codigo"], l["metodo"], l["confianca"]) == (conta, "REGRA", D(1))
    if conta == "1.1.09.002":
        (p,) = r["pendencias"]
        assert (p["tipo"], p["valor_brl"], p["origens"][0].ref) == ("CREDITO_NAO_IDENTIFICADO", D("7350.00"), "L9")
    else:
        assert r["pendencias"] == []


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_sem_regra_vira_humano_com_pendencia():
    r = classificar([lanc("COBRANCA DESCONHECIDA XYZ")])
    (l,) = r["lancamentos"]
    assert (l["conta_codigo"], l["metodo"], l["confianca"], l["regra_id"]) == ("", "HUMANO", D(0), None)
    (p,) = r["pendencias"]
    assert (p["tipo"], p["quem_decide"], p["valor_brl"]) == ("LANCAMENTO_NAO_CLASSIFICADO", "Financeiro", D("-10.00"))


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_folha_por_parametro_provisao_ou_despesa():
    ls = [lanc("PAGTO SALARIOS - FOLHA 08/2026", ref="L1"), lanc("GPS INSS 08/2026", ref="L2")]
    contas = [l["conta_codigo"] for l in classificar(ls)["lancamentos"]]
    assert contas == ["2.1.04.001", "2.1.04.002"]
    despesa = {**REGRAS, "bancos": {**REGRAS["bancos"], "folha_e_impostos_de_08": "despesa"}}
    r = classificar(ls, despesa)
    assert [(l["conta_codigo"], l["metodo"]) for l in r["lancamentos"]] == [("4.1.01", "REGRA"), ("", "HUMANO")]
    assert [p["tipo"] for p in r["pendencias"]] == ["LANCAMENTO_NAO_CLASSIFICADO"]


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_contrapartida_de_transferencia_dentro_da_janela():
    ls = [lanc("TRANSF ENTRE CONTAS P/ BCO MERIDIANO", "-350000.00", ref="L1", data="2026-09-02"),
          lanc("TRANSF ENTRE CONTAS P/ BCO MERIDIANO", "-300000.00", ref="L2", data="2026-09-30"),
          lanc("TED RECEBIDA TARVO PAGAMENTOS LTDA 84.626.315/0001-39 MESMA TITULARIDADE", "350000.00",
               banco="MERIDIANO", ref="MRD1", data="2026-09-03")]
    r = classificar(ls)
    assert all(l["conta_codigo"] == "1.1.09.001" for l in r["lancamentos"])
    (p,) = r["pendencias"]
    assert (p["tipo"], p["ref_origem"], p["valor_brl"]) == ("TRANSFERENCIA_SEM_CONTRAPARTIDA", "L2", D("-300000.00"))


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_conta_fora_do_plano_e_erro_de_configuracao():
    ruim = {"bancos": {"regras": [{"id": "x", "banco": "*", "padrao": "X", "conta": "4.2"}]}}  # sintética
    with pytest.raises(ValueError, match="não aceita lançamento"):
        classificar([lanc("X")], ruim)


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_data_pack_184_lancamentos_por_regra():
    a = ler_aurora(PACK / "05a_extrato_banco_aurora_cc4471_set2026.csv", REGRAS)
    m = ler_meridiano(PACK / "05b_extrato_banco_meridiano_cc90233_set2026.ofx")
    assert (len(a), len(m)) == (84, 100)
    assert (a[0]["ref_origem"], a[-1]["ref_origem"]) == ("L9", "L92")
    assert not any("SALDO" in l["descricao"] or "sujeitos" in l["descricao"] for l in a + m)
    r = classificar(a + m)
    analiticas = {c["codigo"] for c in plano_completo() if c["aceita_lancto"]}
    assert all(l["conta_codigo"] in analiticas and l["metodo"] == "REGRA" for l in r["lancamentos"])
    por_regra = r["resumo"]["por_regra"]
    esperado = {"ted_orbe": 21, "pix_lojista": 44, "transf_entre_contas": 4, "pix_contabilidade": 1,
                "devolucao_pix": 1, "pix_sem_identificacao": 1, "tarifa_aurora": 2, "condominio": 1, "aws": 1,
                "google_workspace": 1, "darf_pis": 1, "darf_cofins": 1, "darf_irrf": 1, "iss": 1, "salarios": 1,
                "gps_inss": 1, "grf_fgts": 1, "pix_receb_lojista": 64, "ted_ponte_liquidacao": 21,
                "ted_mesma_titularidade": 3, "repasse_ponte": 1, "aplicacao_cdb": 3, "resgate_cdb": 3,
                "rendimento": 1, "iof": 1, "seguro": 1, "tarifa_meridiano": 2}
    assert por_regra == esperado and sum(esperado.values()) == 184
    assert sorted((p["tipo"], p["valor_brl"]) for p in r["pendencias"]) == [
        ("CREDITO_NAO_IDENTIFICADO", D("7350.00")), ("TRANSFERENCIA_SEM_CONTRAPARTIDA", D("-300000.00"))]
