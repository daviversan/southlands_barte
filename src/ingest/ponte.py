"""Leitor do relatório da Ponte Câmbio: e-mail `.eml` -> anexo xlsx -> aba de operações.

O anexo é lido em memória (stdlib `email` + `openpyxl`), sem extrair arquivo. Cabeçalho e rodapé
são localizados pelo conteúdo, não pelo número da linha. Datas vêm como data/serial Excel; CNPJ em
dois formatos (normalizado); `Spread %` em fração (convertido para pontos percentuais).
O arquivo de origem do rastro é o próprio `.eml`; `ref_origem` = `Nº Operação`.
"""
from __future__ import annotations

import email
import io
import re
import unicodedata
from email import policy
from pathlib import Path

import openpyxl

from src.core import normalize
from src.core.contratos import OperacaoPonte, RelatorioPonte

# cabeçalho normalizado -> campo interno
_COLUNAS = {
    "no operacao": "num_operacao",
    "data contratacao": "data_contratacao",
    "data liquidacao": "data_liquidacao",
    "cnpj cliente": "cnpj",
    "cliente": "cliente_origem",
    "moeda": "moeda",
    "valor me": "valor_me",
    "taxa cliente": "taxa_cliente",
    "ptax ref.": "ptax",
    "valor r$": "valor_brl",
    "spread r$": "spread_brl",
    "spread %": "spread_pct",
    "spread estimado r$ (d-1)": "spread_estimado_d1_brl",
    "iof r$": "iof_brl",
    "status compliance": "status_compliance",
    "observacao": "observacao",
}
_OBRIGATORIAS = ("num_operacao", "data_contratacao", "cnpj", "moeda", "valor_me", "ptax",
                 "spread_brl", "spread_pct", "status_compliance")


def _chave(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def _anexo_xlsx(caminho: Path) -> bytes:
    with caminho.open("rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    anexos = [p for p in msg.walk() if (p.get_filename() or "").lower().endswith(".xlsx")]
    if len(anexos) != 1:
        raise ValueError(f"{caminho.name}: esperado exatamente um anexo .xlsx, encontrados {len(anexos)}")
    return anexos[0].get_payload(decode=True)


def _aba_operacoes(wb):
    for ws in wb.worksheets:
        for linha in ws.iter_rows(max_row=20, values_only=True):
            if any(v is not None and _chave(v) == "no operacao" for v in linha):
                return ws
    raise ValueError("aba com cabeçalho 'Nº Operação' não encontrada no anexo da Ponte")


def _texto(x) -> str | None:
    return None if normalize._vazio(x) else str(x).strip()


def ler_ponte(caminho: Path) -> RelatorioPonte:
    caminho = Path(caminho)
    rotulo = caminho.name
    wb = openpyxl.load_workbook(io.BytesIO(_anexo_xlsx(caminho)), data_only=True)
    ws = _aba_operacoes(wb)
    linhas = list(ws.iter_rows(values_only=True))

    competencia = None
    cab, col = None, {}
    for numero, linha in enumerate(linhas, start=1):
        for v in linha:
            m = re.search(r"compet[eê]ncia:\s*(\d{2})/(\d{4})", str(v or ""), re.I)
            if m and competencia is None:
                competencia = f"{m.group(2)}-{m.group(1)}"
        mapa = {_COLUNAS[_chave(v)]: i for i, v in enumerate(linha) if v is not None and _chave(v) in _COLUNAS}
        if "num_operacao" in mapa:
            cab, col = numero, mapa
            break
    if cab is None:
        raise ValueError(f"{rotulo}: cabeçalho da Ponte não encontrado")
    faltam = [c for c in _OBRIGATORIAS if c not in col]
    if faltam:
        raise ValueError(f"{rotulo}: colunas ausentes {faltam}")

    def cel(linha, campo):
        i = col.get(campo)
        return linha[i] if i is not None and i < len(linha) else None

    operacoes: list[OperacaoPonte] = []
    total_operacoes = spread_total = None
    for numero, linha in enumerate(linhas[cab:], start=cab + 1):
        primeiro = _texto(linha[0] if linha else None)
        if primeiro is None:
            continue
        rotulo_rodape = _chave(primeiro)
        if rotulo_rodape.startswith("total de operacoes"):
            total_operacoes = int(linha[1])
            continue
        if rotulo_rodape.startswith("spread total"):
            spread_total = normalize.brl(linha[1])
            continue
        try:
            num = _texto(cel(linha, "num_operacao"))
            spread_pct = normalize.pct(cel(linha, "spread_pct"), fracao=True)
            operacoes.append({
                "num_operacao": num,
                "linha": numero,
                "data_contratacao": normalize.data(cel(linha, "data_contratacao")),
                "data_liquidacao": normalize.data(cel(linha, "data_liquidacao")),
                "cnpj": normalize.cnpj(cel(linha, "cnpj")),
                "cliente_origem": _texto(cel(linha, "cliente_origem")) or "",
                "moeda": _texto(cel(linha, "moeda")),
                "valor_me": normalize.brl(cel(linha, "valor_me")),
                "taxa_cliente": normalize.brl(cel(linha, "taxa_cliente")),
                "ptax": normalize.brl(cel(linha, "ptax")),
                "valor_brl": normalize.brl(cel(linha, "valor_brl")),
                "spread_brl": normalize.brl(cel(linha, "spread_brl")),
                "spread_pct": spread_pct,
                "spread_estimado_d1_brl": normalize.brl(cel(linha, "spread_estimado_d1_brl")),
                "iof_brl": normalize.brl(cel(linha, "iof_brl")),
                "status_compliance": _texto(cel(linha, "status_compliance")) or "",
                "observacao": _texto(cel(linha, "observacao")),
                "arquivo_origem": rotulo,
                "ref_origem": num,
            })
            op = operacoes[-1]
            for campo in ("cnpj", "data_contratacao", "moeda", "valor_me", "ptax", "spread_brl", "spread_pct"):
                if op[campo] is None:
                    raise ValueError(f"{campo} vazio")
        except (ValueError, TypeError) as e:
            raise ValueError(f"{rotulo}, {ws.title}!L{numero}: {e}") from e
    if total_operacoes is None or spread_total is None:
        raise ValueError(f"{rotulo}: rodapé (Total de operações / Spread total R$) não encontrado")
    return {
        "operacoes": operacoes,
        "rodape": {"total_operacoes": total_operacoes, "spread_total_brl": spread_total},
        "competencia": competencia,
        "arquivo_origem": rotulo,
    }
