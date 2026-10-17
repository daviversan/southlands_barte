"""Front fino (E4): os auxiliares só leem a saída e nenhuma regra de negócio vive em app.py."""
import ast
import sys
from datetime import date
from pathlib import Path

import pytest

from src import app
from src.core.saida import QUEM_DECIDE

PACK = Path(__file__).resolve().parent.parent / "context" / "tarvo_data_pack"


def test_app_nao_importa_regras_nem_leitores():
    arvore = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    modulos = {n.module for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module}
    modulos |= {a.name for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names}
    internos = {m for m in modulos if m.startswith("src")}
    assert internos == {"src", "src.core.saida"}  # `from src import main`: só a mesma entrada da CLI


def test_competencia_padrao_e_o_mes_anterior():
    assert app.competencia_padrao(date(2026, 10, 17)) == "2026-09"
    assert app.competencia_padrao(date(2027, 1, 5)) == "2026-12"


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_executar_le_saida_rastro_e_fila(tmp_path):
    ok, texto, checagens = app.executar(str(PACK), "2026-09", str(tmp_path))
    assert ok and "Conferência" in texto and checagens
    saidas = app.ler_saida(tmp_path)
    totais = {t["arquivo"]: t for t in app.totais(saidas)}
    assert totais["Notas a emitir"]["linhas"] == "19"

    nf = saidas["notas_a_emitir"][0]
    assert app.linha_de(saidas, nf["id_saida"]) == ("notas_a_emitir", nf)
    assert sum(float(o["valor"]) for o in app.rastro_de(saidas, nf["id_saida"])) == pytest.approx(float(nf["valor_brl"]))

    fila = app.fila_pendencias(saidas)
    assert list(fila) == [q for q in QUEM_DECIDE if q in fila]
    assert sum(len(ps) for ps in fila.values()) == len(saidas["pendencias"])
    contestacoes = [p for p in fila["Financeiro"] if p["tipo"] == "CONTESTACAO"]
    assert len(contestacoes) == 4


def test_executar_devolve_erro_sem_levantar(tmp_path):
    ok, texto, checagens = app.executar(str(tmp_path / "nao_existe"), "2026-09", str(tmp_path / "saida"))
    assert not ok and "Erro" in texto and checagens == []
    assert app.ler_saida(tmp_path / "saida")["pendencias"] == []


class _StreamlitFalso:
    """Registra as chamadas de `render()` sem Streamlit instalado: pega erro de nome/fluxo da tela."""

    def __init__(self):
        self.session_state, self.chamadas = {}, []

    def _widget(self, nome):
        def chamar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            if nome == "text_input":
                return args[1]
            if nome == "selectbox":
                return list(args[1])[0] if list(args[1]) else None
            if nome == "button":
                return True
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


@pytest.mark.skipif(not PACK.exists(), reason="data pack ausente")
def test_render_percorre_todas_as_telas(tmp_path, monkeypatch):
    falso = _StreamlitFalso()
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    monkeypatch.setattr(app, "competencia_padrao", lambda: "2026-09")
    executar, ler_saida = app.executar, app.ler_saida  # a saída vai para tmp_path, não para saida/
    monkeypatch.setattr(app, "executar", lambda entrada, competencia, _: executar(entrada, competencia, str(tmp_path)))
    monkeypatch.setattr(app, "ler_saida", lambda _: ler_saida(tmp_path))
    app.render()
    ok, _, checagens = falso.session_state["execucao"]
    assert ok and checagens
    nomes = [c[0] for c in falso.chamadas]
    assert {"tabs", "metric", "dataframe", "selectbox", "success"} <= set(nomes)
    assert "error" not in nomes and "info" not in nomes
