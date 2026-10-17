"""Front fino (E4): os auxiliares só leem a saída e nenhuma regra de negócio vive em app.py."""
import ast
import sys
from io import BytesIO
from datetime import date
from pathlib import Path

import pytest

from src import app
from src.core.saida import QUEM_DECIDE

PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"


def test_entrada_e_saida_sao_as_pastas_do_repositorio():
    assert app.ENTRADA == app.RAIZ / "context" / "tarvo_data_pack" and app.SAIDA == app.RAIZ / "saida"


def test_app_nao_importa_regras_nem_leitores():
    arvore = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    modulos = {n.module for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module}
    modulos |= {a.name for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names}
    internos = {m for m in modulos if m.startswith("src")}
    assert internos == {"src", "src.core.saida"}  # `from src import main`: só a mesma entrada da CLI


def test_cada_sessao_tem_pasta_de_saida_propria_e_vazia():
    uma, outra = {}, {}
    pasta = app.pasta_da_sessao(uma)
    assert pasta.is_dir() and not any(pasta.iterdir())
    assert app.pasta_da_sessao(uma) == pasta  # a mesma sessão reaproveita a pasta entre cliques
    assert app.pasta_da_sessao(outra) != pasta and pasta != app.SAIDA


def test_competencia_padrao_e_o_mes_anterior():
    assert app.competencia_padrao(date(2026, 10, 17)) == "2026-09"
    assert app.competencia_padrao(date(2027, 1, 5)) == "2026-12"


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_executar_le_saida_rastro_e_fila(tmp_path):
    ok, texto, checagens = app.executar("2026-09", PACK, tmp_path)
    assert ok and "Conferência" in texto and checagens
    saidas = app.ler_saida(tmp_path)
    cartoes = {c["titulo"]: c for c in app.cartoes(saidas)}
    assert cartoes["Comissões"]["valor"] == "R$ 231.007,79"
    assert cartoes["Comissões"]["detalhes"] == ["Checkout: R$ 191.464,34", "Remessa: R$ 39.543,45"]
    assert cartoes["Notas a emitir"]["detalhes"] == ["18 notas de checkout", "1 nota de remessa"]
    # sem somas que misturam naturezas diferentes
    assert cartoes["Lançamentos bancários"]["valor"] == "184 lançamentos"
    assert cartoes["Lançamentos bancários"]["detalhes"] == ["Aurora: 84", "Meridiano: 100", "184 por regra, 0 aguardando conta"]
    assert cartoes["Pendências"]["valor"] == "302 pendências"
    assert cartoes["Pendências"]["detalhes"] == ["Financeiro: 170", "Comercial: 131", "Ponte: 1"]
    assert not any("R$" in d for c in ("Lançamentos bancários", "Pendências") for d in cartoes[c]["detalhes"])

    nf = saidas["notas_a_emitir"][0]
    assert app.linha_de(saidas, nf["id_saida"]) == ("notas_a_emitir", nf)
    assert sum(float(o["valor"]) for o in app.rastro_de(saidas, nf["id_saida"])) == pytest.approx(float(nf["valor_brl"]))

    fila = app.fila_pendencias(saidas)
    assert list(fila) == [q for q in QUEM_DECIDE if q in fila]
    assert sum(len(ps) for ps in fila.values()) == len(saidas["pendencias"])
    contestacoes = [p for p in fila["Financeiro"] if p["tipo"] == "CONTESTACAO"]
    assert len(contestacoes) == 4


def test_executar_devolve_erro_sem_levantar(tmp_path):
    ok, texto, checagens = app.executar("2026-09", tmp_path / "nao_existe", tmp_path / "saida")
    assert not ok and "Erro" in texto and checagens == []
    assert app.ler_saida(tmp_path / "saida")["pendencias"] == []


class _StreamlitFalso:
    """Registra as chamadas de `render()` sem Streamlit instalado: pega erro de nome/fluxo da tela."""

    def __init__(self):
        self.session_state, self.chamadas = {}, []
        self.documentos = []

    def _widget(self, nome):
        def chamar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            if nome == "text_input":
                return args[1]
            if nome == "selectbox":
                return list(args[1])[0] if list(args[1]) else None
            if nome == "button":
                return True
            if nome == 'file_uploader':
                return self.documentos
            if nome in ("tabs", "columns"):
                n = args[0] if isinstance(args[0], int) else len(args[0])
                return [self for _ in range(n)]
            return self
        return chamar

    def __getattr__(self, nome):
        return self if nome == "sidebar" else self._widget(nome)  # st.sidebar é objeto, não função

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_render_informa_acesso_negado_sem_quebrar(monkeypatch):
    falso = _StreamlitFalso()
    monkeypatch.setitem(sys.modules, 'streamlit', falso)
    monkeypatch.setattr(app, 'executar', lambda *args: (False, 'Sem acesso', []))
    def negar(_):
        raise PermissionError(13, 'Permission denied', 'comissoes_por_lojista.csv')
    monkeypatch.setattr(app, 'ler_saida', negar)
    app.render()
    mensagens = [args[0] for nome, args, _ in falso.chamadas if nome == 'error']
    assert any('Sem permissão' in m and 'comissoes_por_lojista.csv' in m for m in mensagens)
    assert not any(nome == 'tabs' for nome, _, _ in falso.chamadas)


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_render_percorre_todas_as_telas(tmp_path, monkeypatch):
    falso = _StreamlitFalso()
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    monkeypatch.setattr(app, "competencia_padrao", lambda: "2026-09")
    executar, ler_saida = app.executar, app.ler_saida  # a saída vai para tmp_path, não para saida/
    monkeypatch.setattr(app, "executar", lambda competencia, *_: executar(competencia, PACK, tmp_path))
    monkeypatch.setattr(app, "ler_saida", lambda _: ler_saida(tmp_path))
    app.render()
    ok, _, checagens = falso.session_state["execucao"]
    assert ok and checagens
    nomes = [c[0] for c in falso.chamadas]
    assert {"tabs", "container", "dataframe", "selectbox", "success"} <= set(nomes)
    assert "error" not in nomes and "info" not in nomes
    metricas = [c for c in falso.chamadas if c[0] == "metric"]
    assert all(len(args) == 2 and "delta" not in kw for _, args, kw in metricas)  # sem seta de variação
    rotulos = [c[1][0] for c in falso.chamadas if c[0] == "text_input"]
    assert rotulos == ["mês analizado"]  # sem campos de pasta
    textos = " ".join(str(a) for c in falso.chamadas if c[0] == "markdown" for a in c[1])
    assert "\\$ 231.007,79" in textos and "R$ 231" not in textos.replace("R\\$", "")


class Documento(BytesIO):
    def __init__(self, nome, conteudo):
        super().__init__(conteudo)
        self.name = nome


def documentos_pack():
    return [Documento(p.name, p.read_bytes()) for p in sorted(PACK.iterdir())
            if p.suffix.lower() in ('.csv', '.xlsx', '.eml', '.ofx')]


@pytest.mark.skipif(not PACK.exists(), reason='data pack ausente')
def test_upload_processa_arquivos_originais_e_preserva_rastro(tmp_path):
    documentos = documentos_pack()
    uploads, saida = tmp_path/'uploads', tmp_path/'saida'
    ok, resumo, checagens = app.executar_documentos('2026-09', documentos, uploads, saida)
    assert ok, resumo
    assert all(c.ok for c in checagens if c.bloqueia)
    lote, = uploads.iterdir()
    assert {p.name:p.read_bytes() for p in lote.iterdir()} == {d.name:d.getvalue() for d in documentos}
    resultados = app.ler_saida(saida)
    assert len(resultados['notas_a_emitir']) == 19
    assert len(resultados['lancamentos_classificados']) == 184
    assert all((lote/r['arquivo_origem']).exists() for r in resultados['rastro'])


@pytest.mark.parametrize('documentos', [[], [Documento('../fora.csv', b'x')],
    [Documento('a.csv', b'a'), Documento('A.csv', b'b')], [Documento('arquivo.exe', b'x')]])
def test_upload_rejeita_nomes_invalidos_e_duplicados(tmp_path, documentos):
    with pytest.raises(ValueError):
        app.salvar_documentos(documentos, tmp_path/'lote')
    assert not (tmp_path/'lote').exists()


def test_upload_incompleto_preserva_saida(tmp_path):
    saida = tmp_path/'saida'
    saida.mkdir()
    anterior = saida/'comissoes_por_lojista.csv'
    anterior.write_bytes(b'anterior')
    ok, mensagem, _ = app.executar_documentos('2026-09', [Documento('01_orbe_teste.csv', b'x')],
                                             tmp_path/'uploads', saida)
    assert not ok and '02_*.xlsx' in mensagem
    assert '03_*.eml' in mensagem and 'comissões e divergências de remessa' in mensagem
    assert not (tmp_path/'uploads').exists()
    assert anterior.read_bytes() == b'anterior'


@pytest.mark.parametrize('faltante,parte', [
    ('01_orbe_teste.csv', 'comissões, divergências e notas de checkout'),
    ('02_taxas.xlsx', 'taxas e os spreads contratados'),
    ('03_ponte.eml', 'nota de remessa'),
    ('04_plano.csv', 'contas contábeis corretas'),
    ('05a_aurora.csv', 'lançamentos do Aurora'),
    ('05b_meridiano.ofx', 'lançamentos do Meridiano'),
])
def test_upload_falta_documento_explica_parte_da_analise(tmp_path, faltante, parte):
    nomes = ['01_orbe_teste.csv', '02_taxas.xlsx', '03_ponte.eml', '04_plano.csv',
             '05a_aurora.csv', '05b_meridiano.ofx']
    documentos = [Documento(n, b'x') for n in nomes if n != faltante]
    ok, mensagem, _ = app.executar_documentos('2026-09', documentos, tmp_path/'uploads', tmp_path/'saida')
    assert not ok and parte in mensagem and 'Falta' in mensagem
    assert not (tmp_path/'uploads').exists()


def test_upload_xlsx_duplicado_e_email_ausente_mostra_ambos(tmp_path):
    documentos = [Documento('02_taxas.xlsx', b'x'), Documento('02_taxas_copia.xlsx', b'x')]
    ok, mensagem, _ = app.executar_documentos('2026-09', documentos, tmp_path/'uploads', tmp_path/'saida')
    assert not ok
    assert '2 arquivos de planilha de taxas' in mensagem
    assert 'Mantenha apenas um' in mensagem and 'checkout' in mensagem
    assert '03_*.eml' in mensagem and 'remessa' in mensagem
    assert not (tmp_path/'uploads').exists()


def test_render_encaminha_documentos_enviados(monkeypatch):
    falso = _StreamlitFalso()
    falso.documentos = [Documento('01_orbe_teste.csv', b'x')]
    monkeypatch.setitem(sys.modules, 'streamlit', falso)
    monkeypatch.setattr(app, 'competencia_padrao', lambda:'2026-09')
    recebidos = []
    def executar(competencia, documentos, saida):
        recebidos.append((competencia, documentos, saida))
        return False, 'Lote incompleto', []
    monkeypatch.setattr(app, 'executar_documentos', executar)
    monkeypatch.setattr(app, 'ler_saida', lambda _:{n:[] for n in app.ESQUEMAS})
    app.render()
    assert recebidos == [('2026-09', falso.documentos, Path(falso.session_state['pasta_saida']))]
    uploader, = [c for c in falso.chamadas if c[0] == 'file_uploader']
    assert uploader[2]['accept_multiple_files'] is True
