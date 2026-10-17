"""Integração do Alvo: pipeline real sobre uma cópia do data pack, formato e conservação."""
import csv
import hashlib
import re
import shutil
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

import pytest

from src import main
from src.core.saida import BANCOS, ESQUEMAS, LINHAS_NEGOCIO, METODOS, Origem, Saida, SaidaError, conferir_diretorio

PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"
RAIZ = PACK.parent.parent
REGRAS, CADASTRO = RAIZ / "config/regras.yaml", RAIZ / "config/lojistas.yaml"
pytestmark = pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")


@pytest.fixture
def entrada(tmp_path):
    destino = tmp_path / "entrada"
    shutil.copytree(PACK, destino, ignore=shutil.ignore_patterns("*.md"))
    return destino


def executar(entrada, destino, regras=REGRAS, cadastro=CADASTRO):
    return main.run(entrada, "2026-09", destino, regras, cadastro)


def ler(pasta, nome):
    with (pasta / f"{nome}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def hashes(pasta):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pasta.iterdir())}


@pytest.fixture(scope="module")
def publicada(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("alvo")
    destino = raiz / "saida"
    resultado = main.run(PACK, "2026-09", destino, REGRAS, CADASTRO)
    return destino, resultado


def test_seis_csvs_formato_e_enums(publicada):
    destino, _ = publicada
    assert {p.stem for p in destino.iterdir()} == set(ESQUEMAS)
    conferir_diretorio(destino)  # Σ rastro por id_saida = valor reportado, para todos os arquivos
    for nome, esq in ESQUEMAS.items():
        linhas = ler(destino, nome)
        assert linhas, f"{nome} vazio"
        assert list(linhas[0])[:len(esq.colunas)] == list(esq.colunas)
        for r in linhas:
            for c in esq.cnpj:
                assert re.fullmatch(r"\d{14}", r[c])
            for c in esq.datas:
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r[c])
            if esq.valor:
                assert re.fullmatch(r"-?\d+\.\d{2}", r[esq.valor])
            if "linha_negocio" in r:
                assert r["linha_negocio"] in LINHAS_NEGOCIO
    for r in ler(destino, "lancamentos_classificados"):
        assert r["banco"] in BANCOS and r["metodo"] in METODOS
    for r in ler(destino, "pendencias"):
        assert r["tipo"].strip() and r["motivo"].strip() and r["quem_decide"] in ("Financeiro", "Comercial")


def test_numeros_de_referencia_do_data_pack(publicada):
    destino, r = publicada
    com = ler(destino, "comissoes_por_lojista")
    total = defaultdict(D)
    for c in com:
        total[c["linha_negocio"]] += D(c["comissao_brl"])
    assert (total["CHECKOUT"], total["REMESSA"]) == (D("191464.34"), D("39543.45"))
    assert [c["id_saida"] for c in com if c["linha_negocio"] == "CHECKOUT"][-1] == "COM-0018"  # ids do Mínimo
    assert sum(1 for c in com if c["linha_negocio"] == "REMESSA") == 14
    div = ler(destino, "divergencias_taxa")
    assert sum(1 for d in div if d["linha_negocio"] == "CHECKOUT") == 92
    assert sum(D(d["diferenca_brl"]) for d in div if d["linha_negocio"] == "CHECKOUT") == D("1576.23")
    assert sum(D(d["diferenca_brl"]) for d in div if d["linha_negocio"] == "REMESSA") == D("1419.05")
    assert len(ler(destino, "lancamentos_classificados")) == 184
    resumo = r["checkout"]["resumo"]
    assert resumo["linhas_processadas"] + resumo["linhas_bloqueadas"] == 1957


def test_notas_e_invariantes_fiscais(publicada):
    destino, _ = publicada
    notas = ler(destino, "notas_a_emitir")
    com = ler(destino, "comissoes_por_lojista")
    ck = [n for n in notas if n["linha_negocio"] == "CHECKOUT"]
    rm = [n for n in notas if n["linha_negocio"] == "REMESSA"]
    assert len(rm) == 1 and rm[0]["tomador_cnpj"] == "75374179000146"
    assert D(rm[0]["valor_brl"]) == sum(D(c["comissao_brl"]) for c in com if c["linha_negocio"] == "REMESSA")
    positivas = {c["cnpj"]: D(c["comissao_brl"]) for c in com if c["linha_negocio"] == "CHECKOUT" and D(c["comissao_brl"]) > 0}
    assert {n["tomador_cnpj"]: D(n["valor_brl"]) for n in ck} == positivas
    assert all(n["discriminacao"].strip() for n in notas)
    assert "76801732" not in "".join(n["tomador"] for n in notas)
    # Atlas não tem nota; a explicação é a pendência por linha para o Comercial
    pend = ler(destino, "pendencias")
    assert any(p["tipo"] == "CONTRATO_AUSENTE" and p["quem_decide"] == "Comercial" for p in pend)
    # rastro da NF repete as origens da comissão
    rastro = defaultdict(list)
    for x in ler(destino, "rastro"):
        rastro[x["id_saida"]].append((x["arquivo_origem"], x["ref_origem"], x["valor"]))
    por_cnpj = {c["cnpj"]: c["id_saida"] for c in com if c["linha_negocio"] == "CHECKOUT"}
    for n in ck:
        assert sorted(rastro[n["id_saida"]]) == sorted(rastro[por_cnpj[n["tomador_cnpj"]]])


def test_remessa_contestacao_repetida_e_rastro_aponta_para_entradas(publicada):
    destino, _ = publicada
    pend = ler(destino, "pendencias")
    contestacoes = {p["ref_origem"] for p in pend if p["tipo"] == "CONTESTACAO"}
    assert len(contestacoes) == 4
    assert not contestacoes & {d["ref_origem"] for d in ler(destino, "divergencias_taxa")}
    assert [p["ref_origem"] for p in pend if p["tipo"] == "OPERACAO_REPETIDA"] == ["PC-0926-0162#2"]
    arquivos = {p.name for p in PACK.iterdir()}
    for x in ler(destino, "rastro"):
        assert x["arquivo_origem"] in arquivos


def test_determinismo(entrada, tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    executar(entrada, a)
    executar(entrada, b)
    assert hashes(a) == hashes(b)
    out = capsys.readouterr().out
    assert "base da comissão R$ 79.085,76" in out and "quem decide Comercial" in out


def test_lojista_sem_cadastro_vira_pendencia_nunca_erro(entrada, tmp_path):
    cadastro = tmp_path / "cad.yaml"
    texto = CADASTRO.read_text(encoding="utf-8")
    cadastro.write_text(re.sub(r'  "1074504011":\n(    .*\n){2}', "", texto), encoding="utf-8")  # sem Rota Global
    r = executar(entrada, tmp_path / "saida", cadastro=cadastro)
    assert "95927868000148" not in {c["cnpj"] for c in r["checkout"]["comissoes"]}
    assert "95927868000148" in {c["cnpj"] for c in r["remessa"]["comissoes"]}  # remessa é por CNPJ


def _corromper(monkeypatch, alvo, mutacao):
    original = getattr(main, alvo)

    def corrompido(*args, **kwargs):
        resultado = original(*args, **kwargs)
        mutacao(resultado)
        return resultado

    monkeypatch.setattr(main, alvo, corrompido)


@pytest.mark.parametrize("alvo,mutacao", [
    ("calcular_checkout", lambda r: r["pendencias"].pop(0)),  # linha da Orbe some
    ("calcular_checkout", lambda r: r["resumo"].update(total_orbe=1)),
    ("calcular_checkout", lambda r: r["comissoes"][0].update(comissao_brl=r["comissoes"][0]["comissao_brl"] + D("0.01"))),
    ("calcular_remessa", lambda r: r["pendencias"].clear()),  # repetida e negativos somem
    ("calcular_remessa", lambda r: r["comissoes"].append(r["comissoes"][0])),  # comissão duplicada
    ("classificar_lancamentos", lambda r: r["lancamentos"].pop()),
    ("classificar_lancamentos", lambda r: r["lancamentos"][0].update(conta_codigo="4.2")),
    ("calcular_notas", lambda r: r[0].pop()),
])
def test_falha_preserva_saida_anterior(entrada, tmp_path, monkeypatch, alvo, mutacao):
    destino = tmp_path / "saida"
    executar(entrada, destino)
    antes = hashes(destino)
    _corromper(monkeypatch, alvo, mutacao)
    with pytest.raises((ValueError, SaidaError)):
        executar(entrada, destino)
    assert hashes(destino) == antes
    assert not list(tmp_path.glob(".fechamento-*"))


def test_falha_de_gravacao_nao_publica(entrada, tmp_path, monkeypatch):
    destino = tmp_path / "saida"
    executar(entrada, destino)
    antes = hashes(destino)

    def falhar(self, pasta):
        (Path(pasta) / "comissoes_por_lojista.csv").write_text("parcial")
        raise SaidaError("Erro na conferência")

    monkeypatch.setattr(Saida, "gravar", falhar)
    with pytest.raises(SaidaError):
        executar(entrada, destino)
    assert hashes(destino) == antes


def test_fora_competencia_nao_publica(entrada, tmp_path, monkeypatch):
    original = main.ler_meridiano
    monkeypatch.setattr(main, "ler_meridiano", lambda p: [{**l, "data": "2026-10-01"} for l in original(p)])
    with pytest.raises(ValueError, match="fora da competência"):
        executar(entrada, tmp_path / "saida")
    assert not (tmp_path / "saida").exists()


@pytest.mark.parametrize("defeito", ["eml_ausente", "taxas_ambiguas", "yaml", "cadastro", "sem_bancos"])
def test_entradas_invalidas(entrada, tmp_path, defeito):
    regras = tmp_path / "regras.yaml"
    regras.write_text(REGRAS.read_text(encoding="utf-8"), encoding="utf-8")
    cadastro = tmp_path / "cadastro.yaml"
    cadastro.write_text(CADASTRO.read_text(encoding="utf-8"), encoding="utf-8")
    if defeito == "eml_ausente":
        next(entrada.glob("03_*.eml")).unlink()
    elif defeito == "taxas_ambiguas":
        shutil.copy(next(entrada.glob("02_*.xlsx")), entrada / "02_outra.xlsx")
    elif defeito == "yaml":
        regras.write_text("[]", encoding="utf-8")
    elif defeito == "cadastro":
        cadastro.write_text("lojistas: []", encoding="utf-8")
    else:
        regras.write_text("checkout: {}\nremessa: {}\nnotas: {}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        executar(entrada, tmp_path / "saida", regras, cadastro)
    assert not (tmp_path / "saida").exists()


@pytest.mark.parametrize("competencia", ["2026-9", "2026-00", "2026-13", "0000-09"])
def test_competencia_invalida(competencia):
    with pytest.raises(ValueError):
        main._validar_competencia(competencia)


def test_cli_ajuda_e_erro(capsys):
    with pytest.raises(SystemExit) as erro:
        main.main(["--help"])
    assert erro.value.code == 0
    assert "--cadastro" in capsys.readouterr().out
    with pytest.raises(SystemExit) as erro:
        main.main(["--entrada", ".", "--competencia", "2026-13", "--saida", "saida"])
    assert erro.value.code == 1


def test_origem_reexportada():
    assert Origem("a", "b", D(1)).valor == D(1)
