"""Integração de B com as interfaces de A substituídas por exemplos do contrato."""
from copy import deepcopy
import csv
from decimal import Decimal as D
from pathlib import Path

import pytest

from src import main
from src.core.saida import ESQUEMAS, Origem, Saida, SaidaError, conferir_diretorio


@pytest.fixture
def fechamento(tmp_path, monkeypatch):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    (entrada / "02_taxas.xlsx").touch()
    regras = tmp_path / "regras.yaml"
    regras.write_text("checkout:\n  base_comissao: taxa_contratada\n", encoding="utf-8")
    cadastro = tmp_path / "cadastro.yaml"
    cadastro.write_text('lojistas:\n  "001":\n    cnpj: "00123456000199"\n    lojista: Exemplo\n', encoding="utf-8")
    transacoes = [dict(id_transacao=ref, ref_origem=ref, arquivo_origem=arquivo,
                       data_movimento="2026-09-30", tipo_lancamento=tipo, valor_bruto=D(bruto))
                  for ref, arquivo, tipo, bruto in [
                      ("TX1", "01_orbe.csv", "VENDA", "1000"),
                      ("TX2", "06_orbe_ajustes.csv", "VENDA", "5480"),
                      ("TX3", "06_orbe_ajustes.csv", "ESTORNO", "-100"),
                  ]]
    resultado = dict(
        comissoes=[dict(cnpj="00123456000199", lojista="Exemplo", linha_negocio="CHECKOUT",
                        comissao_brl=D("25.90"), origens=[Origem("01_orbe.csv", "TX1", D("25.90"))],
                        contratos_utilizados=[dict(arquivo_origem="02_taxas.xlsx", ref_origem="Taxas vigentes!L6")])],
        pendencias=[dict(tipo="CADASTRO_NAO_RESOLVIDO", ref_origem="TX2", valor_brl=D("5480"),
                         motivo="Bruto da venda; comissão desconhecida", quem_decide="Financeiro",
                         origens=[Origem("06_orbe_ajustes.csv", "TX2", D("5480"))])],
        resumo=dict(total_orbe=3, vendas_total=2, vendas_processadas=1, vendas_bloqueadas=1,
                    fora_escopo_por_tipo={"ESTORNO": 1},
                    contagens_por_arquivo={"01_orbe.csv": 1, "06_orbe_ajustes.csv": 2}))

    def calcular(t, c, cad, comp, reg):
        assert t is transacoes and c == [] and comp == "2026-09"
        assert cad["001"]["cnpj"] == "00123456000199"
        assert reg["checkout"]["base_comissao"] == "taxa_contratada"
        return deepcopy(resultado)

    def orbe(pasta):
        assert pasta == entrada.resolve()
        return transacoes

    def taxas(caminho):
        assert caminho == entrada / "02_taxas.xlsx"
        return []

    monkeypatch.setattr(main, "_componentes_checkout", lambda: (orbe, taxas, calcular))
    return entrada, regras, cadastro, transacoes, resultado


def executar(fechamento, destino):
    entrada, regras, cadastro, _, _ = fechamento
    return main.run_minimo(entrada, "2026-09", destino, regras, cadastro)


def test_publica_seis_csvs_rastro_e_resumo(fechamento, tmp_path, capsys):
    destino = tmp_path / "saida"
    resultado = executar(fechamento, destino)
    assert resultado == fechamento[4]
    assert {p.stem for p in destino.iterdir()} == set(ESQUEMAS)
    conferir_diretorio(destino)
    with (destino / "comissoes_por_lojista.csv").open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    assert linhas[0]["cnpj"] == "00123456000199"
    assert linhas[0]["comissao_brl"] == "25.90"
    for nome in ("divergencias_taxa", "notas_a_emitir", "lancamentos_classificados"):
        assert len((destino / f"{nome}.csv").read_text().splitlines()) == 1
    assert "ESTORNO: 1 fora do escopo" in capsys.readouterr().out
    antes = {p.name: p.read_bytes() for p in destino.iterdir()}
    executar(fechamento, destino)
    assert antes == {p.name: p.read_bytes() for p in destino.iterdir()}


def test_ordenacao_de_ids(fechamento, tmp_path):
    _, _, _, transacoes, resultado = fechamento
    transacoes.append({**transacoes[0], "id_transacao": "TX4", "ref_origem": "TX4"})
    resultado["comissoes"].append({**resultado["comissoes"][0], "cnpj": "00000000000001",
                                 "origens": [Origem("01_orbe.csv", "TX4", D("25.90"))]})
    resultado["resumo"].update(total_orbe=4, vendas_total=3, vendas_processadas=2,
                               contagens_por_arquivo={"01_orbe.csv": 2, "06_orbe_ajustes.csv": 2})
    destino = tmp_path / "saida"
    executar(fechamento, destino)
    assert (destino / "comissoes_por_lojista.csv").read_text().splitlines()[1].startswith(
        "COM-0001;00000000000001;")


@pytest.mark.parametrize("competencia", ["2026-9", "2026-00", "2026-13", "0000-09"])
def test_competencia_invalida(competencia):
    with pytest.raises(ValueError):
        main._validar_competencia(competencia)


def test_fora_competencia_nao_publica(fechamento, tmp_path):
    fechamento[3][2]["data_movimento"] = "2026-08-31"
    with pytest.raises(ValueError, match="fora da competência"):
        executar(fechamento, tmp_path / "saida")
    assert not (tmp_path / "saida").exists()


@pytest.mark.parametrize("defeito", ["resumo", "venda_ausente", "bruto", "rastro", "duplicada"])
def test_falha_preserva_saida_anterior(fechamento, tmp_path, defeito):
    destino = tmp_path / "saida"
    executar(fechamento, destino)
    antes = {p.name: p.read_bytes() for p in destino.iterdir()}
    resultado = fechamento[4]
    if defeito == "resumo":
        resultado["resumo"]["total_orbe"] = 999
    elif defeito == "venda_ausente":
        resultado["pendencias"].clear()
    elif defeito == "bruto":
        resultado["pendencias"][0].update(valor_brl=D(1), origens=[Origem("06_orbe_ajustes.csv", "TX2", D(1))])
    elif defeito == "rastro":
        resultado["comissoes"][0]["comissao_brl"] = D("25.91")
    else:
        fechamento[3].append(fechamento[3][0])
    with pytest.raises(ValueError):
        executar(fechamento, destino)
    assert antes == {p.name: p.read_bytes() for p in destino.iterdir()}


def test_falha_de_gravacao_nao_publica(fechamento, tmp_path, monkeypatch):
    destino = tmp_path / "saida"
    executar(fechamento, destino)
    antes = {p.name: p.read_bytes() for p in destino.iterdir()}

    def falhar(self, pasta):
        (Path(pasta) / "comissoes_por_lojista.csv").write_text("parcial")
        raise SaidaError("Erro na conferência")

    monkeypatch.setattr(Saida, "gravar", falhar)
    with pytest.raises(SaidaError):
        executar(fechamento, destino)
    assert antes == {p.name: p.read_bytes() for p in destino.iterdir()}
    assert not list(tmp_path.glob(".fechamento-*"))


def test_arredondamento_por_venda_sem_rateio(fechamento, tmp_path):
    _, _, _, transacoes, resultado = fechamento
    transacoes.append({**transacoes[0], "id_transacao": "TX4", "ref_origem": "TX4"})
    resultado["comissoes"][0].update(
        comissao_brl=D("2.02"),
        origens=[Origem("01_orbe.csv", ref, D("1.01")) for ref in ("TX1", "TX4")])
    resultado["resumo"].update(total_orbe=4, vendas_total=3, vendas_processadas=2,
                               contagens_por_arquivo={"01_orbe.csv": 2, "06_orbe_ajustes.csv": 2})
    destino = tmp_path / "saida"
    executar(fechamento, destino)
    conferir_diretorio(destino)
    resultado["comissoes"][0]["comissao_brl"] = D("2.01")
    with pytest.raises(SaidaError, match="Σ rastro"):
        executar(fechamento, destino)


@pytest.mark.parametrize("defeito", ["taxas_ausentes", "taxas_ambiguas", "yaml", "cadastro"])
def test_entradas_invalidas(fechamento, tmp_path, defeito):
    entrada, regras, cadastro, _, _ = fechamento
    if defeito == "taxas_ausentes":
        (entrada / "02_taxas.xlsx").unlink()
    elif defeito == "taxas_ambiguas":
        (entrada / "02_outras_taxas.xlsx").touch()
    elif defeito == "yaml":
        regras.write_text("[]", encoding="utf-8")
    else:
        cadastro.write_text("lojistas: []", encoding="utf-8")
    with pytest.raises(ValueError):
        executar(fechamento, tmp_path / "saida")
    assert not (tmp_path / "saida").exists()


def test_cli_ajuda_e_erro(capsys):
    with pytest.raises(SystemExit) as erro:
        main.main(["--help"])
    assert erro.value.code == 0
    assert "--cadastro" in capsys.readouterr().out
    with pytest.raises(SystemExit) as erro:
        main.main(["--entrada", ".", "--competencia", "2026-13", "--saida", "saida"])
    assert erro.value.code == 1
