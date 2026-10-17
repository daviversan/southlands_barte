"""Leitor do plano de contas do ERP Fênix (CSV `;`, ISO-8859-1)."""
from __future__ import annotations

import csv
from pathlib import Path

from src.core.contratos import ContaContabil

ENCODING = "iso-8859-1"


def ler_plano(caminho: Path) -> list[ContaContabil]:
    """Todas as contas; só as com `ACEITA_LANCTO = S` podem receber lançamento."""
    caminho = Path(caminho)
    with caminho.open(encoding=ENCODING, newline="") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    pos = next((i for i, l in enumerate(linhas) if "COD_CONTA" in [c.strip() for c in l]), None)
    if pos is None:
        raise ValueError(f"{caminho.name}: cabeçalho com COD_CONTA não encontrado")
    cab = [c.strip() for c in linhas[pos]]
    for campo in ("COD_CONTA", "DESCRICAO", "ACEITA_LANCTO"):
        if campo not in cab:
            raise ValueError(f"{caminho.name}: coluna {campo} ausente")
    contas: list[ContaContabil] = []
    for linha in linhas[pos + 1:]:
        if not any(c.strip() for c in linha):
            continue
        r = dict(zip(cab, (c.strip() for c in linha)))
        contas.append({"codigo": r["COD_CONTA"], "descricao": r["DESCRICAO"],
                       "aceita_lancto": r["ACEITA_LANCTO"].upper() == "S"})
    return contas
