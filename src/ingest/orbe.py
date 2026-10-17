"""Leitor da Orbe (adquirente): `01_orbe_*.csv` + ajustes `06_orbe_ajustes_*.csv`.

CSV `;`, decimal vírgula, datas pt-BR. Encoding explícito: ASCII na origem (subconjunto do UTF-8).
Entrega **todas** as linhas, de qualquer tipo; filtrar o que é escopo é com a regra.
"""
from __future__ import annotations

import csv
from pathlib import Path

from src.core import normalize
from src.core.contratos import TransacaoOrbe

ENCODING = "utf-8"
PADRAO_PRINCIPAL = "01_orbe_*.csv"
PADRAO_AJUSTES = "06_orbe_ajustes_*.csv"

_OBRIGATORIAS = (
    "id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento",
    "tipo_lancamento", "modalidade", "qtd_parcelas", "valor_bruto", "taxa_aplicada_pct",
)


def descobrir_arquivos(entrada: Path) -> list[Path]:
    """Principal (obrigatório) + ajustes (opcionais), ordenados por nome."""
    entrada = Path(entrada)
    principais = sorted(entrada.glob(PADRAO_PRINCIPAL))
    if not principais:
        raise FileNotFoundError(f"nenhum arquivo {PADRAO_PRINCIPAL} em {entrada}")
    return sorted({*principais, *entrada.glob(PADRAO_AJUSTES)}, key=lambda p: p.name)


def _texto(valor: str | None) -> str | None:
    return None if normalize._vazio(valor) else valor.strip()


def _ler_arquivo(caminho: Path, rotulo: str) -> list[TransacaoOrbe]:
    with caminho.open(encoding=ENCODING, newline="") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    # cabeçalho localizado pelo conteúdo, não pelo número da linha
    pos = next((i for i, l in enumerate(linhas) if "id_transacao" in [c.strip() for c in l]), None)
    if pos is None:
        raise ValueError(f"{rotulo}: cabeçalho com `id_transacao` não encontrado")
    cab = [c.strip() for c in linhas[pos]]
    faltam = [c for c in _OBRIGATORIAS if c not in cab]
    if faltam:
        raise ValueError(f"{rotulo}: colunas ausentes {faltam}")

    saida: list[TransacaoOrbe] = []
    for numero, linha in enumerate(linhas[pos + 1:], start=pos + 2):
        if not any(c.strip() for c in linha):
            continue
        r = dict(zip(cab, linha))
        try:
            parcelas = _texto(r.get("qtd_parcelas"))
            id_ = r["id_transacao"].strip()
            if not id_:
                raise ValueError("id_transacao vazio")
            saida.append({
                "id_transacao": id_,
                "data_movimento": normalize.data(r["data_movimento"]),
                "ec": r["cod_estabelecimento"].strip(),
                "nome_origem": (_texto(r["nome_estabelecimento"]) or ""),
                "tipo_lancamento": r["tipo_lancamento"].strip(),
                "modalidade": _texto(r["modalidade"]),
                "qtd_parcelas": int(parcelas) if parcelas is not None else None,
                "valor_bruto": normalize.brl(r["valor_bruto"]),
                "taxa_aplicada_pct": normalize.pct(r["taxa_aplicada_pct"], fracao=False),
                "arquivo_origem": rotulo,
                "ref_origem": id_,
                "bandeira": _texto(r.get("bandeira")),
                "valor_taxa": normalize.brl(r.get("valor_taxa")),
                "valor_liquido": normalize.brl(r.get("valor_liquido")),
                "id_referencia": _texto(r.get("id_referencia")),
                "data_venda_original": normalize.data(r.get("data_venda_original")),
            })
        except ValueError as e:
            raise ValueError(f"{rotulo}, linha {numero}: {e}") from e
    return saida


def ler_orbe(entrada: Path) -> list[TransacaoOrbe]:
    """Lê todos os arquivos Orbe da pasta. `arquivo_origem` = caminho relativo (com `/`).

    `id_transacao` repetido, dentro de um arquivo ou entre arquivos, é erro explícito.
    """
    entrada = Path(entrada)
    transacoes: list[TransacaoOrbe] = []
    vistos: dict[str, str] = {}
    for caminho in descobrir_arquivos(entrada):
        rotulo = caminho.relative_to(entrada).as_posix()
        for t in _ler_arquivo(caminho, rotulo):
            if t["id_transacao"] in vistos:
                raise ValueError(
                    f"id_transacao {t['id_transacao']} repetido: {vistos[t['id_transacao']]} e {rotulo}"
                )
            vistos[t["id_transacao"]] = rotulo
            transacoes.append(t)
    return transacoes
