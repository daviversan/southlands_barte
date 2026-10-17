"""Front fino do fechamento (nível Extra, E4): rodar, ver as saídas, seguir o rastro, fila de pendências.

Sem regra de negócio: a execução é `main.run()` (a mesma da CLI) e o resto só lê os CSVs de `saida/`.
O Streamlit é opcional e só é importado em `render()`; os auxiliares de leitura são testáveis sem ele.

    pip install streamlit
    streamlit run src/app.py
"""
from __future__ import annotations

import contextlib
import csv
import io
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:  # `streamlit run` executa o arquivo como script, fora do pacote
    sys.path.insert(0, str(RAIZ))

from src import main  # noqa: E402
from src.core.saida import ARQUIVOS_EMISSIVEIS, ESQUEMAS, QUEM_DECIDE  # noqa: E402

TITULOS = {
    "comissoes_por_lojista": "Comissões por lojista",
    "divergencias_taxa": "Divergências de taxa",
    "notas_a_emitir": "Notas a emitir",
    "lancamentos_classificados": "Lançamentos classificados",
    "pendencias": "Pendências",
}


def competencia_padrao(hoje: date | None = None) -> str:
    """Mês anterior ao atual: o fechamento roda depois de o mês acabar."""
    hoje = hoje or date.today()
    ano, mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    return f"{ano:04d}-{mes:02d}"


def ler_saida(pasta: str | Path) -> dict[str, list[dict[str, str]]]:
    """Os CSVs publicados em `pasta` (arquivo ausente = lista vazia)."""
    pasta = Path(pasta)
    saidas = {}
    for nome in ESQUEMAS:
        caminho = pasta / f"{nome}.csv"
        if not caminho.exists():
            saidas[nome] = []
            continue
        with caminho.open(encoding="utf-8", newline="") as f:
            saidas[nome] = list(csv.DictReader(f, delimiter=";"))
    return saidas


def totais(saidas: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    """Linhas e Σ da coluna de valor de cada arquivo, como publicados."""
    resumo = []
    for nome in ARQUIVOS_EMISSIVEIS:
        col = ESQUEMAS[nome].valor
        soma = sum((Decimal(r[col]) for r in saidas[nome]), Decimal(0))
        resumo.append({"arquivo": TITULOS[nome], "linhas": str(len(saidas[nome])), "total": brl(soma)})
    return resumo


def linha_de(saidas: dict[str, list[dict[str, str]]], id_saida: str) -> tuple[str, dict[str, str]] | None:
    for nome in ARQUIVOS_EMISSIVEIS:
        for r in saidas[nome]:
            if r["id_saida"] == id_saida:
                return nome, r
    return None


def rastro_de(saidas: dict[str, list[dict[str, str]]], id_saida: str) -> list[dict[str, str]]:
    return [r for r in saidas["rastro"] if r["id_saida"] == id_saida]


def fila_pendencias(saidas: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    """Pendências por `quem_decide`, na ordem da lista fechada; maiores valores primeiro."""
    fila: dict[str, list[dict[str, str]]] = {q: [] for q in QUEM_DECIDE}
    for p in saidas["pendencias"]:
        fila.setdefault(p["quem_decide"], []).append(p)
    return {q: sorted(ps, key=lambda p: -abs(Decimal(p["valor_brl"]))) for q, ps in fila.items() if ps}


def brl(valor: Decimal) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def executar(entrada: str, competencia: str, saida: str) -> tuple[bool, str, list]:
    """Roda `main.run` capturando o resumo impresso. (sucesso, texto do resumo ou erro, checagens)."""
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            resultado = main.run(Path(entrada), competencia, Path(saida),
                                 RAIZ / "config/regras.yaml", RAIZ / "config/lojistas.yaml")
    except (OSError, ValueError) as erro:
        return False, f"{buffer.getvalue()}\nErro: {erro}".strip(), []
    return True, buffer.getvalue(), resultado.get("conferencia", [])


def render() -> None:  # pragma: no cover - interface; a lógica testável está nos auxiliares acima
    import streamlit as st

    st.set_page_config(page_title="Fechamento Tarvo", layout="wide")
    st.title("Fechamento Tarvo")

    with st.sidebar:
        st.header("Rodar o fechamento")
        entrada = st.text_input("Pasta de entrada (arquivos como vêm)", str(RAIZ / "context" / "tarvo_data_pack"))
        competencia = st.text_input("Competência (AAAA-MM)", competencia_padrao())
        pasta_saida = st.text_input("Pasta de saída", str(RAIZ / "saida"))
        if st.button("Rodar", type="primary"):
            with st.spinner("Lendo arquivos, calculando e conferindo..."):
                st.session_state["execucao"] = executar(entrada, competencia, pasta_saida)
        st.caption("O mesmo comando da CLI. Se a conferência falhar, a saída anterior é mantida.")

    execucao = st.session_state.get("execucao")
    if execucao:
        ok, texto, checagens = execucao
        (st.success if ok else st.error)("Fechamento publicado." if ok else "Fechamento não publicado.")
        with st.expander("Resumo da execução", expanded=not ok):
            st.code(texto or "(sem saída)", language=None)
        if checagens:
            falhas = [c for c in checagens if not c.ok and c.bloqueia]
            st.caption(f"Conferência: {len(checagens)} checagens, {len(falhas)} falha(s).")

    try:
        saidas = ler_saida(pasta_saida)
    except PermissionError as erro:
        st.error(f"Sem permissão para ler o arquivo {erro.filename or pasta_saida}. "
                 "Verifique as permissões da pasta de saída e se o arquivo está aberto em outro programa.")
        return
    except OSError as erro:
        st.error(f"Não foi possível ler os arquivos de saída: {erro}")
        return
    if not any(saidas[n] for n in ARQUIVOS_EMISSIVEIS):
        st.info("Nenhuma saída nesta pasta ainda. Rode o fechamento pela barra lateral.")
        return

    aba_resumo, aba_saidas, aba_rastro, aba_pend = st.tabs(["Resumo", "Saídas", "Rastro", "Pendências"])

    with aba_resumo:
        colunas = st.columns(len(ARQUIVOS_EMISSIVEIS))
        for coluna, t in zip(colunas, totais(saidas)):
            coluna.metric(t["arquivo"], t["total"], f"{t['linhas']} linhas", delta_color="off")
        if execucao and execucao[2]:
            st.subheader("Conferência (saída × rastro × entradas)")
            st.dataframe([{"grupo": c.grupo, "checagem": c.descricao, "obtido": c.obtido,
                           "esperado": c.esperado, "situação": "ok" if c.ok else ("falha" if c.bloqueia else "aviso")}
                          for c in execucao[2]], use_container_width=True, hide_index=True)

    with aba_saidas:
        nome = st.selectbox("Arquivo", list(ARQUIVOS_EMISSIVEIS), format_func=TITULOS.get)
        st.dataframe(saidas[nome], use_container_width=True, hide_index=True)
        st.caption("Copie um id_saida e veja de onde o número veio na aba Rastro.")

    with aba_rastro:
        ids = [r["id_saida"] for n in ARQUIVOS_EMISSIVEIS for r in saidas[n]]
        escolhido = st.selectbox("id_saida", ids)
        achado = linha_de(saidas, escolhido) if escolhido else None
        if achado:
            nome, linha = achado
            st.markdown(f"**{TITULOS[nome]}**")
            st.dataframe([linha], use_container_width=True, hide_index=True)
            origens = rastro_de(saidas, escolhido)
            st.markdown(f"**Linhas de origem ({len(origens)})** — soma "
                        f"{brl(sum((Decimal(o['valor']) for o in origens), Decimal(0)))}")
            st.dataframe(origens, use_container_width=True, hide_index=True)

    with aba_pend:
        fila = fila_pendencias(saidas)
        colunas = st.columns(max(len(fila), 1))
        for coluna, (quem, ps) in zip(colunas, fila.items()):
            coluna.metric(quem, f"{len(ps)} pendência(s)")
        for quem, ps in fila.items():
            with st.expander(f"{quem} — {len(ps)} pendência(s)"):
                st.dataframe([{k: p.get(k, "") for k in ("id_saida", "tipo", "ref_origem", "valor_brl",
                                                         "motivo", "sugestao")} for p in ps],
                             use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render()
