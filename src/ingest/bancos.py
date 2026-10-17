"""Leitores dos extratos bancários: Aurora (CSV, UTF-8) e Meridiano (OFX SGML, CP1252).

Um leitor por fonte, encoding explícito. Nenhum texto de descrição é usado para filtrar linhas:
- Aurora: cabeçalho achado pelo conteúdo (`Data`, `Lançamento`, `Valor`); lançamento = linha com
  data válida **e** valor preenchido (saldo anterior, saldo final e o aviso não têm valor);
  `ref_origem = L<linha física + offset>` (`bancos.aurora_ref_offset`).
- Meridiano: regex sobre `<STMTTRN>` (SGML sem fechamento de tag; não é XML). `ref_origem = FITID`.
  Saldo (`LEDGERBAL`) fica fora dos blocos de transação.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from src.core import normalize
from src.core.contratos import LancamentoBancario

ENCODING_AURORA = "utf-8"
ENCODING_MERIDIANO = "cp1252"
_DATA_BR = re.compile(r"\d{2}/\d{2}/\d{4}")


def _chave(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def ler_aurora(caminho: Path, regras: dict | None = None) -> list[LancamentoBancario]:
    caminho = Path(caminho)
    offset = int(((regras or {}).get("bancos") or {}).get("aurora_ref_offset", 0))
    texto = caminho.read_text(encoding=ENCODING_AURORA)
    linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=";"))
    if len(linhas) != len(texto.splitlines()):
        raise ValueError(f"{caminho.name}: campo com quebra de linha; a numeração física não seria confiável")

    cab = col = None
    for numero, linha in enumerate(linhas, start=1):
        chaves = [_chave(c) for c in linha]
        if "data" in chaves and "lancamento" in chaves:
            valor = next((i for i, c in enumerate(chaves) if c.startswith("valor")), None)
            if valor is not None:
                cab, col = numero, {"data": chaves.index("data"), "descricao": chaves.index("lancamento"), "valor": valor}
                break
    if cab is None:
        raise ValueError(f"{caminho.name}: cabeçalho (Data; Lançamento; Valor) não encontrado")

    saida: list[LancamentoBancario] = []
    for numero, linha in enumerate(linhas[cab:], start=cab + 1):
        def cel(campo):
            i = col[campo]
            return linha[i].strip() if i < len(linha) else ""

        if not _DATA_BR.fullmatch(cel("data")) or not cel("valor"):
            continue
        try:
            saida.append({
                "banco": "AURORA",
                "ref_origem": f"L{numero + offset}",
                "data": normalize.data(cel("data")),
                "descricao": cel("descricao"),
                "valor": normalize.brl(cel("valor")),
                "arquivo_origem": caminho.name,
            })
        except ValueError as e:
            raise ValueError(f"{caminho.name}, linha {numero}: {e}") from e
    return saida


def _tag(bloco: str, nome: str) -> str | None:
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco)
    return m.group(1).strip() if m else None


def ler_meridiano(caminho: Path) -> list[LancamentoBancario]:
    caminho = Path(caminho)
    texto = caminho.read_text(encoding=ENCODING_MERIDIANO)
    saida: list[LancamentoBancario] = []
    vistos: set[str] = set()
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, re.S):
        fitid, valor, data, memo = (_tag(bloco, t) for t in ("FITID", "TRNAMT", "DTPOSTED", "MEMO"))
        if not fitid or valor is None or not data or memo is None:
            raise ValueError(f"{caminho.name}: transação sem FITID/TRNAMT/DTPOSTED/MEMO ({fitid!r})")
        if fitid in vistos:
            raise ValueError(f"{caminho.name}: FITID repetido {fitid}")
        vistos.add(fitid)
        saida.append({
            "banco": "MERIDIANO",
            "ref_origem": fitid,
            "data": f"{data[:4]}-{data[4:6]}-{data[6:8]}",
            "descricao": memo,
            "valor": Decimal(valor),  # OFX: ponto decimal, sem milhar
            "arquivo_origem": caminho.name,
        })
    if not saida:
        raise ValueError(f"{caminho.name}: nenhuma transação <STMTTRN>")
    return saida
