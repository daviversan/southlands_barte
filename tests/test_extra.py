"""Nível Extra: conferência automática (E1), pendências explicadas (E2) e outubro sem retrabalho (E3)."""
import base64
import csv
import email
import io
import re
import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from email import policy
from pathlib import Path

import openpyxl
import pytest
import yaml

from src import main
from src.core import conferencia
from src.core.saida import QUEM_DECIDE, Saida, SaidaError
from src.regras.pendencias import explicar_pendencias

PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"
RAIZ = PACK.parent.parent
REGRAS, CADASTRO = RAIZ / "config/regras.yaml", RAIZ / "config/lojistas.yaml"
precisa_pack = pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")


def ler(pasta, nome):
    with (pasta / f"{nome}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def gravar(pasta, nome, linhas):
    with (pasta / f"{nome}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


def copiar_pack(destino: Path) -> Path:
    shutil.copytree(PACK, destino, ignore=shutil.ignore_patterns("*.md"))
    return destino


@pytest.fixture(scope="module")
def publicada(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("extra")
    resultado = main.run(PACK, "2026-09", raiz / "saida", REGRAS, CADASTRO)
    return raiz / "saida", resultado


# --- E1: rastro completo e conferência automática ---------------------------------------------

@precisa_pack
def test_conferencia_fecha_no_data_pack(publicada, capsys):
    _, r = publicada
    checagens = r["conferencia"]
    assert checagens and all(c.ok for c in checagens if c.bloqueia)
    grupos = {c.grupo for c in checagens}
    assert {"Orbe", "Ponte", "Bancos", "Notas", "rastro", "pendencias"} <= grupos


@precisa_pack
def test_conferencia_imprime_relatorio(tmp_path, capsys):
    main.run(PACK, "2026-09", tmp_path / "saida", REGRAS, CADASTRO)
    out = capsys.readouterr().out
    assert "Conferência (saída × rastro × entradas):" in out and " 0 falha(s)" in out
    assert "1666 + 291 = 1957" in out and "228 + 5 = 233" in out


def _entradas():
    arquivos = main._descobrir(PACK)
    regras = yaml.safe_load(REGRAS.read_text(encoding="utf-8"))
    return (main.ler_orbe(PACK), main.ler_ponte(arquivos["ponte"]),
            main.ler_aurora(arquivos["aurora"], regras) + main.ler_meridiano(arquivos["meridiano"]),
            main.ler_taxas(arquivos["taxas"]))


def _sem(linhas, id_saida):
    return [r for r in linhas if r["id_saida"] != id_saida]


def _adulterar_lancamento_sumido(pasta):
    lan = ler(pasta, "lancamentos_classificados")
    alvo = lan[-1]["id_saida"]
    gravar(pasta, "lancamentos_classificados", _sem(lan, alvo))
    gravar(pasta, "rastro", _sem(ler(pasta, "rastro"), alvo))
    return "Bancos"


def _adulterar_origem_inexistente(pasta):
    rastro = ler(pasta, "rastro")
    alvo = next(r for r in rastro if r["id_saida"].startswith("DIV-"))
    alvo["ref_origem"] = "TX00000000"
    gravar(pasta, "rastro", rastro)
    return "rastro"


def _adulterar_pendencia_da_orbe_sumida(pasta):
    pen = ler(pasta, "pendencias")
    alvo = next(r for r in pen if r["tipo"] == "CONTRATO_AUSENTE")["id_saida"]
    gravar(pasta, "pendencias", _sem(pen, alvo))
    gravar(pasta, "rastro", _sem(ler(pasta, "rastro"), alvo))
    return "Orbe"


def _adulterar_nota_maior_que_comissao(pasta):
    # Σ por arquivo continua fechando (NF e rastro mudam juntos), mas NF ≠ comissões.
    notas, rastro = ler(pasta, "notas_a_emitir"), ler(pasta, "rastro")
    nf = next(n for n in notas if n["linha_negocio"] == "CHECKOUT")
    nf["valor_brl"] = str(D(nf["valor_brl"]) + D("1.00"))
    linha = next(r for r in rastro if r["id_saida"] == nf["id_saida"])
    linha["valor"] = str(D(linha["valor"]) + D("1.00"))
    gravar(pasta, "notas_a_emitir", notas)
    gravar(pasta, "rastro", rastro)
    return "Notas"


@precisa_pack
@pytest.mark.parametrize("adulterar", [_adulterar_lancamento_sumido, _adulterar_origem_inexistente,
                                       _adulterar_pendencia_da_orbe_sumida, _adulterar_nota_maior_que_comissao])
def test_conferencia_detecta_saida_adulterada(publicada, tmp_path, adulterar):
    pasta = tmp_path / "saida"
    shutil.copytree(publicada[0], pasta)
    grupo = adulterar(pasta)
    checagens = conferencia.conferir(pasta, *_entradas())
    assert any(c.grupo == grupo and not c.ok for c in checagens)
    with pytest.raises(conferencia.ConferenciaError):
        conferencia.exigir(checagens)


@precisa_pack
def test_conferencia_falha_o_comando_e_preserva_saida(tmp_path, monkeypatch, capsys):
    entrada, destino = copiar_pack(tmp_path / "entrada"), tmp_path / "saida"
    main.run(entrada, "2026-09", destino, REGRAS, CADASTRO)
    antes = {p.name: p.read_bytes() for p in destino.iterdir()}
    original = Saida.gravar

    def gravar_e_perder_lancamento(self, pasta):
        caminhos = original(self, pasta)
        _adulterar_lancamento_sumido(Path(pasta))
        return caminhos

    monkeypatch.setattr(Saida, "gravar", gravar_e_perder_lancamento)
    with pytest.raises(conferencia.ConferenciaError):
        main.run(entrada, "2026-09", destino, REGRAS, CADASTRO)
    assert "[FALHA]" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in destino.iterdir()} == antes
    with pytest.raises(SystemExit) as erro:  # pela CLI: código de saída 1
        main.main(["--entrada", str(entrada), "--competencia", "2026-09", "--saida", str(destino)])
    assert erro.value.code == 1


# --- E2: pendências explicadas --------------------------------------------------------------------

_JARGAO = re.compile(r"\b[a-z]+_[a-z_]+\b|Valor da pendência|assinado|Spread R\$|Nº Operação|#\d")


@precisa_pack
def test_pendencias_em_linguagem_de_negocio(publicada):
    pend = ler(publicada[0], "pendencias")
    assert list(pend[0]) == ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide", "sugestao"]
    for p in pend:
        assert p["quem_decide"] in QUEM_DECIDE
        assert p["sugestao"].strip() and p["motivo"].strip()
        assert not _JARGAO.search(p["motivo"]), (p["id_saida"], p["motivo"])


@precisa_pack
def test_pendencias_cobrem_os_casos_do_dicionario(publicada):
    pend = ler(publicada[0], "pendencias")

    def uma(tipo, **campos):
        achadas = [p for p in pend if p["tipo"] == tipo and all(p[k] == v for k, v in campos.items())]
        assert achadas, (tipo, campos)
        return achadas

    atlas = uma("CONTRATO_AUSENTE", quem_decide="Comercial")
    assert all("Atlas" in p["motivo"] and "não é faturada" in p["motivo"] for p in atlas)
    assert all("Horizonte Viagens ou da Novo Horizonte" in p["motivo"] for p in uma("CONTRATO_AMBIGUO"))
    kiwi = [p for p in uma("CADASTRO_NAO_RESOLVIDO") if "1038867654" in p["motivo"]]
    assert kiwi and all("EC pendente" in p["motivo"] and "Kiwi" in p["sugestao"] for p in kiwi)
    repetida = uma("OPERACAO_REPETIDA", quem_decide="Ponte")
    assert [p["ref_origem"] for p in repetida] == ["PC-0926-0162#2"] and "reprocessada" in repetida[0]["motivo"]
    negativos = uma("CONTESTACAO", quem_decide="Financeiro")
    assert len(negativos) == 4 and all("5 dias úteis" in p["sugestao"] for p in negativos)
    pix = uma("CREDITO_NAO_IDENTIFICADO", valor_brl="7350.00")
    assert "devolver o Pix" in pix[0]["sugestao"]
    ted = uma("TRANSFERENCIA_SEM_CONTRAPARTIDA", valor_brl="-300000.00")
    assert "R$ 300.000,00" in ted[0]["motivo"] and "extrato do mês seguinte" in ted[0]["sugestao"]


def _pend(tipo="CONTESTACAO", **extra):
    return {"tipo": tipo, "ref_origem": "PC-1", "valor_brl": D("-1"), "motivo": "m", "quem_decide": "Financeiro",
            "origens": [], **extra}


def test_explicar_aplica_catalogo_e_preserva_sugestao_especifica():
    regras = {"pendencias": {"tipos": {"CONTESTACAO": {"sugestao": "genérica"},
                                       "OPERACAO_REPETIDA": {"quem_decide": "Ponte", "sugestao": "corrigir"}}}}
    a, b, c = explicar_pendencias([_pend(), _pend("OPERACAO_REPETIDA"), _pend(sugestao="específica")], regras)
    assert (a["quem_decide"], a["sugestao"]) == ("Financeiro", "genérica")
    assert (b["quem_decide"], b["sugestao"]) == ("Ponte", "corrigir")
    assert c["sugestao"] == "específica"


@pytest.mark.parametrize("regras", [
    {},
    {"pendencias": {"tipos": {"OUTRO": {"sugestao": "x"}}}},  # tipo sem explicação
    {"pendencias": {"tipos": {"CONTESTACAO": {"sugestao": " "}}}},
    {"pendencias": {"tipos": {"CONTESTACAO": {"sugestao": "x", "quem_decide": "Diretoria"}}}},
])
def test_explicar_rejeita_catalogo_incompleto(regras):
    with pytest.raises(ValueError):
        explicar_pendencias([_pend()], regras)


def test_quem_decide_fora_da_lista_fechada_nao_e_gravado():
    with pytest.raises(SaidaError, match="quem_decide"):
        Saida().emitir("pendencias", {"tipo": "T", "ref_origem": "R", "valor_brl": D(0), "motivo": "m",
                                      "quem_decide": "Diretoria", "sugestao": "s"}, [])


# --- E3: outubro sem retrabalho -------------------------------------------------------------------

_PROIBIDOS = [
    (r"(?<![\w.])\d{10}(?![\w.])", "EC"),
    (r"(?<![\w.])\d{14}(?![\w.])", "CNPJ"),
    (r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", "CNPJ formatado"),
    (r"\b20\d{2}-\d{2}\b", "data ou competência"),
]


def test_codigo_sem_ec_cnpj_lojista_ou_competencia():
    lojistas = [d["lojista"] for d in yaml.safe_load(CADASTRO.read_text(encoding="utf-8"))["lojistas"].values()]
    achados = []
    for arquivo in sorted((RAIZ / "src").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        achados += [f"{arquivo.name}: {nome} {m.group()}" for padrao, nome in _PROIBIDOS
                    for m in re.finditer(padrao, texto)]
        achados += [f"{arquivo.name}: lojista {n}" for n in lojistas if n.lower() in texto.lower()]
    assert achados == []


def _mais_um_mes(d: date) -> date:
    return d.replace(year=d.year + d.month // 12, month=d.month % 12 + 1)


def _texto_para_outubro(texto: str) -> str:
    texto = re.sub(r"(\d{2})/09/2026", r"\1/10/2026", texto)
    texto = re.sub(r"(\d{2})/08/2026", r"\1/09/2026", texto)
    return re.sub(r"202609(\d{2})", r"202610\1", texto)


def _ponte_para_outubro(eml: Path) -> None:
    msg = email.message_from_bytes(eml.read_bytes(), policy=policy.default)
    parte = next(p for p in msg.walk() if (p.get_filename() or "").lower().endswith(".xlsx"))
    wb = openpyxl.load_workbook(io.BytesIO(parte.get_payload(decode=True)))
    base = datetime(1899, 12, 30)
    for ws in wb.worksheets:
        colunas_data = set()
        for linha in ws.iter_rows():
            for cel in linha:
                v = cel.value
                if isinstance(v, str):
                    if v.strip().lower().startswith("data "):
                        colunas_data.add(cel.column)
                    cel.value = v.replace("09/2026", "10/2026")
                elif isinstance(v, datetime):
                    cel.value = datetime.combine(_mais_um_mes(v.date()), v.time())
                elif isinstance(v, (int, float)) and cel.column in colunas_data and 40000 < v < 60000:
                    cel.value = (datetime.combine(_mais_um_mes((base + timedelta(days=v)).date()),
                                                  datetime.min.time()) - base).days
    novo = io.BytesIO()
    wb.save(novo)
    parte.set_payload(base64.encodebytes(novo.getvalue()).decode())
    eml.write_bytes(msg.as_bytes())


@precisa_pack
def test_roda_em_outubro_sem_mudar_codigo(publicada, tmp_path):
    """O data pack inteiro deslocado um mês: mesmo comando, outra pasta e outra competência."""
    entrada = copiar_pack(tmp_path / "outubro")
    for padrao, encoding in (("01_*.csv", "ascii"), ("06_*.csv", "ascii"), ("05a_*.csv", "utf-8"),
                             ("05b_*.ofx", "cp1252")):
        for arq in entrada.glob(padrao):
            arq.write_bytes(_texto_para_outubro(arq.read_bytes().decode(encoding)).encode(encoding))
    _ponte_para_outubro(next(entrada.glob("03_*.eml")))

    with pytest.raises(ValueError, match="fora da competência"):
        main.run(entrada, "2026-09", tmp_path / "errada", REGRAS, CADASTRO)
    destino = tmp_path / "saida"
    r = main.run(entrada, "2026-10", destino, REGRAS, CADASTRO)
    assert all(c.ok for c in r["conferencia"] if c.bloqueia)
    assert r["checkout"]["resumo"]["total_orbe"] == 1957 and r["remessa"]["resumo"]["linhas_relatorio"] == 233
    assert all("2026-10" in n["discriminacao"] for n in ler(destino, "notas_a_emitir"))
    setembro = publicada[1]
    # Remessa não depende de vigência: a mesma comissão. Checkout muda só pela vigência da Bridge.
    total = lambda res, linha: sum(c["comissao_brl"] for c in res[linha]["comissoes"])  # noqa: E731
    assert total(r, "remessa") == total(setembro, "remessa")
    assert total(r, "checkout") < total(setembro, "checkout")
    assert len(ler(destino, "pendencias")) == len(setembro["pendencias"])


@precisa_pack
def test_lojista_removido_e_data_deslocada(publicada, tmp_path):
    entrada = copiar_pack(tmp_path / "entrada")
    orbe = next(entrada.glob("01_*.csv"))
    linhas = orbe.read_text(encoding="ascii").splitlines(keepends=True)
    sem_casa = [l for l in linhas if ";1018325654;" not in l]  # Casa do Estudante some do mês
    removidas = len(linhas) - len(sem_casa)
    # Venda à vista da Bridge sai de 12/09 (2,59%) para 20/09 (vigência nova, 2,19%).
    sem_casa = [l.replace("TX88424307;12/09/2026", "TX88424307;20/09/2026") for l in sem_casa]
    orbe.write_text("".join(sem_casa), encoding="ascii")

    destino = tmp_path / "saida"
    r = main.run(entrada, "2026-09", destino, REGRAS, CADASTRO)
    assert all(c.ok for c in r["conferencia"] if c.bloqueia)
    assert r["checkout"]["resumo"]["total_orbe"] == 1957 - removidas
    com = ler(destino, "comissoes_por_lojista")
    assert "00520815000100" not in {c["cnpj"] for c in com if c["linha_negocio"] == "CHECKOUT"}
    assert "00520815000100" not in {n["tomador_cnpj"] for n in ler(destino, "notas_a_emitir")}
    rastro = {x["ref_origem"]: x["valor"] for x in ler(destino, "rastro") if x["id_saida"].startswith("COM-")}
    assert rastro["TX88424307"] == "51.86"  # 2.368,21 × 2,19%
    div = {d["ref_origem"]: d for d in ler(destino, "divergencias_taxa")}
    assert (div["TX88424307"]["taxa_aplicada_pct"], div["TX88424307"]["diferenca_brl"]) == ("2.59", "9.47")


@precisa_pack
def test_cabecalho_do_aurora_achado_pelo_conteudo(tmp_path):
    original = next(PACK.glob("05a_*.csv"))
    arq = tmp_path / original.name
    arq.write_text("Relatório exportado\nlinha extra\n" + original.read_text(encoding="utf-8"), encoding="utf-8")
    lidos = main.ler_aurora(arq, {})
    assert len(lidos) == 84 and lidos[0]["ref_origem"] == "L11"  # a numeração segue a linha física
