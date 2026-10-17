import csv
from decimal import Decimal

import pytest

from src.core.saida import ESQUEMAS, Origem, Saida, SaidaError, conferir_diretorio

ORBE = "01_orbe_relatorio_comissoes_set2026.csv"
D = Decimal


def com(valor, **kw):
    return {"cnpj": "12345678000190", "lojista": "Lojista X", "linha_negocio": "CHECKOUT",
            "comissao_brl": valor, **kw}


def ler(pasta, nome):
    with (pasta / f"{nome}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_emite_id_com_prefixo_e_rastro():
    s = Saida()
    id1 = s.emitir("comissoes_por_lojista", com(D("30.00")),
                   [Origem(ORBE, "TX1", D("16.37")), (ORBE, "TX2", D("13.63"))])
    id2 = s.emitir("comissoes_por_lojista", com(D("5")), [(ORBE, "TX3", D("5"))])
    assert (id1, id2) == ("COM-0001", "COM-0002")
    assert [r["ref_origem"] for r in s._linhas["rastro"]] == ["TX1", "TX2", "TX3"]


def test_soma_do_rastro_diferente_do_valor_falha():
    with pytest.raises(SaidaError, match="Σ rastro"):
        Saida().emitir("comissoes_por_lojista", com(D("30.01")),
                       [(ORBE, "TX1", D("16.37")), (ORBE, "TX2", D("13.63"))])


def test_valor_sem_origem_falha_mas_zero_sem_origem_passa():
    with pytest.raises(SaidaError):
        Saida().emitir("comissoes_por_lojista", com(D("1.00")), [])
    Saida().emitir("pendencias", {"tipo": "LOJISTA_SEM_CONTRATO", "ref_origem": "EC1",
                                  "valor_brl": D("0"), "motivo": "m", "quem_decide": "Comercial"}, [])


def test_arredondamento_half_up_na_escrita_e_no_rastro():
    s = Saida()
    # 0,125 + 0,125 = 0,25 em precisão total, mas por linha cada um vira 0,13 -> 0,26
    with pytest.raises(SaidaError):
        s.emitir("comissoes_por_lojista", com(D("0.25")), [(ORBE, "A", D("0.125")), (ORBE, "B", D("0.125"))])
    s.emitir("comissoes_por_lojista", com(D("0.26")), [(ORBE, "A", D("0.125")), (ORBE, "B", D("0.125"))])
    assert s._linhas["comissoes_por_lojista"][0]["comissao_brl"] == "0.26"
    assert [r["valor"] for r in s._linhas["rastro"]] == ["0.13", "0.13"]


def test_float_e_rejeitado():
    with pytest.raises(SaidaError, match="float"):
        Saida().emitir("comissoes_por_lojista", com(16.37), [(ORBE, "TX1", D("16.37"))])


@pytest.mark.parametrize("valor", [D("NaN"), D("Infinity"), D("-Infinity")])
def test_valor_nao_finito_e_rejeitado(valor):
    with pytest.raises(SaidaError, match="finito"):
        Saida().emitir("comissoes_por_lojista", com(valor), [(ORBE, "TX1", D("1"))])


@pytest.mark.parametrize("campo,valor", [
    ("cnpj", "123"), ("cnpj", "12.345.678/0001-90"), ("cnpj", None), ("linha_negocio", "OUTRA"),
    ("lojista", " "),
])
def test_formatos_invalidos(campo, valor):
    linha = com(D("1"))
    linha[campo] = valor
    with pytest.raises(SaidaError):
        Saida().emitir("comissoes_por_lojista", linha, [(ORBE, "TX1", D("1"))])


def test_colunas_faltando_ou_extras_nao_declaradas():
    linha = com(D("1"))
    del linha["lojista"]
    with pytest.raises(SaidaError, match="faltam"):
        Saida().emitir("comissoes_por_lojista", linha, [(ORBE, "TX1", D("1"))])
    with pytest.raises(SaidaError, match="não previstas"):
        Saida().emitir("comissoes_por_lojista", com(D("1"), foo="x"), [(ORBE, "TX1", D("1"))])
    with pytest.raises(SaidaError, match="id_saida"):
        Saida().emitir("comissoes_por_lojista", com(D("1"), id_saida="COM-9"), [(ORBE, "TX1", D("1"))])


def test_lancamento_valida_enums_data_e_confianca():
    base = {"banco": "AURORA", "ref_origem": "L9", "data": "2026-09-01", "descricao": "TED",
            "valor": D("-389.00"), "conta_codigo": "4.2.01", "metodo": "REGRA", "confianca": D("1")}
    orig = [("05a_extrato.csv", "L9", D("-389.00"))]
    Saida().emitir("lancamentos_classificados", dict(base), orig)
    for campo, valor in [("banco", "OUTRO"), ("metodo", "LLM"), ("data", "01/09/2026"),
                         ("confianca", D("1.5")), ("conta_codigo", "")]:
        with pytest.raises(SaidaError):
            Saida().emitir("lancamentos_classificados", {**base, campo: valor}, orig)


def test_pendencia_exige_tipo_motivo_e_quem_decide():
    base = {"tipo": "CONTESTACAO", "ref_origem": "PC-1", "valor_brl": D("-10"),
            "motivo": "Trava de 2 horas excedida", "quem_decide": "Financeiro"}
    orig = [("03_ponte.eml", "PC-1", D("-10"))]
    Saida().emitir("pendencias", {**base, "sugestao": "Abrir contestação"}, orig)
    for campo in ("tipo", "motivo", "quem_decide"):
        with pytest.raises(SaidaError):
            Saida().emitir("pendencias", {**base, campo: ""}, orig)


def test_gravar_formato_e_soma_do_rastro_por_arquivo(tmp_path):
    s = Saida()
    s.emitir("comissoes_por_lojista", com(D("30.00")), [(ORBE, "TX1", D("16.37")), (ORBE, "TX2", D("13.63"))])
    s.emitir("divergencias_taxa", {"cnpj": "12345678000190", "linha_negocio": "CHECKOUT",
                                   "ref_origem": "TX9", "taxa_contratada_pct": D("2.19"),
                                   "taxa_aplicada_pct": D("2.59"), "diferenca_brl": D("2.40")},
             [(ORBE, "TX9", D("2.40"))])
    s.emitir("notas_a_emitir", {"tomador_cnpj": "75374179000146", "tomador": "Ponte Câmbio",
                                "linha_negocio": "REMESSA", "valor_brl": D("100.5"),
                                "discriminacao": "Comissão; 2 operações"},
             [("03_ponte.eml", "PC-1", D("60.25")), ("03_ponte.eml", "PC-2", D("40.25"))])
    s.emitir("pendencias", {"tipo": "T", "ref_origem": "R", "valor_brl": D("0"), "motivo": "m",
                            "quem_decide": "Financeiro"}, [])
    caminhos = s.gravar(tmp_path)

    assert set(caminhos) == set(ESQUEMAS)
    for nome, esq in ESQUEMAS.items():
        with (tmp_path / f"{nome}.csv").open(encoding="utf-8") as f:
            assert f.readline().rstrip("\n").split(";") == list(esq.colunas)
    # discriminação com ';' é preservada (aspas), decimal com ponto, 2 casas
    nf = ler(tmp_path, "notas_a_emitir")[0]
    assert nf["discriminacao"] == "Comissão; 2 operações" and nf["valor_brl"] == "100.50"
    assert ler(tmp_path, "divergencias_taxa")[0]["taxa_aplicada_pct"] == "2.59"

    # Σ rastro por id_saida == valor reportado, para todo arquivo que carrega valor
    soma = {}
    for r in ler(tmp_path, "rastro"):
        soma[r["id_saida"]] = soma.get(r["id_saida"], D(0)) + D(r["valor"])
    for nome, esq in ESQUEMAS.items():
        if esq.valor:
            for r in ler(tmp_path, nome):
                assert D(r[esq.valor]) == soma.get(r["id_saida"], D(0)), r["id_saida"]


def test_gravar_vazio_gera_so_cabecalhos(tmp_path):
    Saida().gravar(tmp_path)
    for nome in ESQUEMAS:
        assert len(ler(tmp_path, nome)) == 0


def test_gravar_e_determinístico(tmp_path):
    def rodar(pasta):
        s = Saida()
        s.emitir("comissoes_por_lojista", com(D("1.00")), [(ORBE, "TX1", D("1.00"))])
        s.gravar(pasta)
        return {p.name: p.read_bytes() for p in pasta.iterdir()}
    assert rodar(tmp_path / "a") == rodar(tmp_path / "b")


def test_conferir_diretorio_detecta_arquivo_adulterado(tmp_path):
    s = Saida()
    s.emitir("comissoes_por_lojista", com(D("1.00")), [(ORBE, "TX1", D("1.00"))])
    s.gravar(tmp_path)
    arq = tmp_path / "comissoes_por_lojista.csv"
    arq.write_text(arq.read_text().replace("1.00", "1.01"), encoding="utf-8")
    with pytest.raises(SaidaError, match="COM-0001"):
        conferir_diretorio(tmp_path)
