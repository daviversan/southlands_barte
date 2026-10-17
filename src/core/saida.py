"""Contrato comum de saída: todo número emitido carrega suas origens e a soma é conferida.

Uso:
    saida = Saida()
    id_ = saida.emitir(
        "comissoes_por_lojista",
        {"cnpj": "...", "lojista": "...", "linha_negocio": "CHECKOUT", "comissao_brl": Decimal("16.37")},
        origens=[Origem("01_orbe_relatorio_comissoes_set2026.csv", "TX88410932", Decimal("16.37"))],
    )
    saida.gravar("saida/")

Regra de arredondamento (plano, seção 3): quem emite passa o valor de cada linha de origem **já
na regra de negócio** (ex.: comissão da transação); `emitir` arredonda cada origem e o valor
reportado a 2 casas com ROUND_HALF_UP e **falha** se Σ rastro != valor reportado. Assim o rastro
leva os mesmos valores arredondados por linha e a soma bate ao centavo.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from src.core.normalize import q2

LINHAS_NEGOCIO = ("CHECKOUT", "REMESSA")
BANCOS = ("AURORA", "MERIDIANO")
METODOS = ("REGRA", "IA", "HUMANO")


class SaidaError(ValueError):
    """Violação do contrato de saída (coluna, formato, enum ou soma do rastro)."""


@dataclass(frozen=True)
class Origem:
    arquivo: str
    ref: str
    valor: Decimal


@dataclass(frozen=True)
class Esquema:
    prefixo: str
    colunas: tuple[str, ...]  # obrigatórias, na ordem do enunciado
    extras: tuple[str, ...] = ()  # colunas extras permitidas (opcionais)
    valor: str | None = None  # coluna que carrega o valor conferido contra o rastro
    pct: tuple[str, ...] = ()  # colunas em pontos percentuais
    cnpj: tuple[str, ...] = ()
    datas: tuple[str, ...] = ()
    enums: tuple[tuple[str, tuple[str, ...]], ...] = ()
    textos: tuple[str, ...] = ()  # obrigatoriamente não vazias


ESQUEMAS: dict[str, Esquema] = {
    "comissoes_por_lojista": Esquema(
        "COM", ("id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"),
        valor="comissao_brl", cnpj=("cnpj",),
        enums=(("linha_negocio", LINHAS_NEGOCIO),), textos=("lojista",),
    ),
    "divergencias_taxa": Esquema(
        "DIV",
        ("id_saida", "cnpj", "linha_negocio", "ref_origem", "taxa_contratada_pct",
         "taxa_aplicada_pct", "diferenca_brl"),
        valor="diferenca_brl", pct=("taxa_contratada_pct", "taxa_aplicada_pct"), cnpj=("cnpj",),
        enums=(("linha_negocio", LINHAS_NEGOCIO),), textos=("ref_origem",),
    ),
    "notas_a_emitir": Esquema(
        "NF", ("id_saida", "tomador_cnpj", "tomador", "linha_negocio", "valor_brl", "discriminacao"),
        valor="valor_brl", cnpj=("tomador_cnpj",),
        enums=(("linha_negocio", LINHAS_NEGOCIO),), textos=("tomador", "discriminacao"),
    ),
    "lancamentos_classificados": Esquema(
        "LAN",
        ("id_saida", "banco", "ref_origem", "data", "descricao", "valor", "conta_codigo",
         "metodo", "confianca"),
        valor="valor", pct=("confianca",), datas=("data",),
        enums=(("banco", BANCOS), ("metodo", METODOS)),
        textos=("ref_origem", "descricao", "conta_codigo"),
    ),
    "pendencias": Esquema(
        "PEN", ("id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"),
        extras=("sugestao",), valor="valor_brl", textos=("tipo", "motivo", "quem_decide"),
    ),
    # O rastro é escrito por `emitir`; não se emite linha de rastro diretamente.
    "rastro": Esquema("", ("id_saida", "arquivo_origem", "ref_origem", "valor")),
}

ARQUIVOS_EMISSIVEIS = tuple(n for n, e in ESQUEMAS.items() if e.prefixo)


def _fmt_decimal(d: Decimal, min_casas: int = 2) -> str:
    """Decimal em ponto fixo (sem notação científica), com no mínimo `min_casas` casas."""
    s = format(d.normalize(), "f")
    casas = len(s.split(".")[1]) if "." in s else 0
    return s if casas >= min_casas else format(d.quantize(Decimal(1).scaleb(-min_casas)), "f")


def _como_decimal(coluna: str, v) -> Decimal:
    if isinstance(v, bool) or v is None:
        raise SaidaError(f"{coluna}: valor numérico obrigatório, veio {v!r}")
    if isinstance(v, float):
        raise SaidaError(f"{coluna}: float não permitido, use Decimal (veio {v!r})")
    try:
        numero = Decimal(v)
    except Exception:
        raise SaidaError(f"{coluna}: número inválido {v!r}") from None
    if not numero.is_finite():
        raise SaidaError(f"{coluna}: número deve ser finito (veio {v!r})")
    return numero


class Saida:
    """Acumula linhas de saída + rastro; `gravar` escreve os 6 CSVs."""

    def __init__(self) -> None:
        self._linhas: dict[str, list[dict[str, str]]] = {n: [] for n in ESQUEMAS}
        self._contadores: dict[str, int] = {}

    def emitir(self, arquivo: str, linha: dict, origens: list[Origem | tuple]) -> str:
        """Valida a linha, gera `id_saida`, registra o rastro e devolve o id.

        `linha` não leva `id_saida` (gerado aqui). `origens`: Origem ou tupla (arquivo, ref, valor).
        """
        if arquivo not in ARQUIVOS_EMISSIVEIS:
            raise SaidaError(f"arquivo de saída desconhecido: {arquivo!r}")
        esq = ESQUEMAS[arquivo]
        if "id_saida" in linha:
            raise SaidaError("id_saida é gerado por emitir(); não informe")

        permitidas = set(esq.colunas) - {"id_saida"} | set(esq.extras)
        faltando = (set(esq.colunas) - {"id_saida"}) - set(linha)
        sobrando = set(linha) - permitidas
        if faltando:
            raise SaidaError(f"{arquivo}: faltam colunas {sorted(faltando)}")
        if sobrando:
            raise SaidaError(f"{arquivo}: colunas não previstas {sorted(sobrando)}")

        campos = {c: self._validar(arquivo, esq, c, linha[c]) for c in linha}
        valor = q2(_como_decimal(esq.valor, linha[esq.valor]))
        campos[esq.valor] = _fmt_decimal(valor)

        itens = [o if isinstance(o, Origem) else Origem(*o) for o in origens]
        rastro = [(o, q2(_como_decimal("origem.valor", o.valor))) for o in itens]
        for o, _ in rastro:
            if not o.arquivo or not o.ref:
                raise SaidaError(f"{arquivo}: origem sem arquivo/ref ({o!r})")
        if not rastro and valor != 0:
            raise SaidaError(f"{arquivo}: valor {valor} sem nenhuma origem no rastro")
        soma = sum((v for _, v in rastro), Decimal(0))
        if soma != valor:
            raise SaidaError(
                f"{arquivo}: Σ rastro ({soma}) != valor reportado ({valor}) "
                f"[{', '.join(o.ref for o, _ in rastro)}]"
            )

        self._contadores[arquivo] = self._contadores.get(arquivo, 0) + 1
        id_saida = f"{esq.prefixo}-{self._contadores[arquivo]:04d}"
        self._linhas[arquivo].append({"id_saida": id_saida, **campos})
        for o, v in rastro:
            self._linhas["rastro"].append(
                {"id_saida": id_saida, "arquivo_origem": o.arquivo, "ref_origem": o.ref,
                 "valor": _fmt_decimal(v)}
            )
        return id_saida

    @staticmethod
    def _validar(arquivo: str, esq: Esquema, col: str, v) -> str:
        if col == esq.valor:
            return ""  # preenchido por emitir() após o arredondamento
        if col in esq.pct:
            d = _como_decimal(col, v)
            if col == "confianca" and not Decimal(0) <= d <= Decimal(1):
                raise SaidaError(f"{arquivo}.{col}: deve estar entre 0 e 1 (veio {d})")
            return _fmt_decimal(d)
        s = "" if v is None else str(v)
        if col in esq.cnpj and not re.fullmatch(r"\d{14}", s):
            raise SaidaError(f"{arquivo}.{col}: CNPJ deve ter 14 dígitos (veio {s!r})")
        if col in esq.datas and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            raise SaidaError(f"{arquivo}.{col}: data deve ser AAAA-MM-DD (veio {s!r})")
        for c, validos in esq.enums:
            if col == c and s not in validos:
                raise SaidaError(f"{arquivo}.{col}: {s!r} fora de {validos}")
        if col in esq.textos and not s.strip():
            raise SaidaError(f"{arquivo}.{col}: não pode ser vazio")
        return s

    def gravar(self, destino: str | Path) -> dict[str, Path]:
        """Escreve os 6 CSVs em `destino` (`;`, UTF-8, `\\n`) e reconfere a soma do rastro."""
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        caminhos = {}
        for nome, esq in ESQUEMAS.items():
            colunas = list(esq.colunas) + [
                c for c in esq.extras if any(c in r for r in self._linhas[nome])
            ]
            caminho = destino / f"{nome}.csv"
            with caminho.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", lineterminator="\n",
                                   restval="")
                w.writeheader()
                w.writerows(self._linhas[nome])
            caminhos[nome] = caminho
        conferir_diretorio(destino)
        return caminhos


def conferir_diretorio(pasta: str | Path) -> None:
    """Relê os CSVs em disco e exige Σ rastro.valor por id_saida == valor reportado.

    Levanta SaidaError com a lista de ids que não fecham. Também falha se o rastro citar um
    id inexistente ou se um id de saída com valor != 0 não tiver rastro.
    """
    pasta = Path(pasta)

    def ler(nome: str) -> list[dict[str, str]]:
        with (pasta / f"{nome}.csv").open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter=";"))

    soma_rastro: dict[str, Decimal] = {}
    for r in ler("rastro"):
        soma_rastro[r["id_saida"]] = soma_rastro.get(r["id_saida"], Decimal(0)) + Decimal(r["valor"])

    erros, vistos = [], set()
    for nome in ARQUIVOS_EMISSIVEIS:
        col = ESQUEMAS[nome].valor
        for r in ler(nome):
            vistos.add(r["id_saida"])
            reportado, rastreado = Decimal(r[col]), soma_rastro.get(r["id_saida"], Decimal(0))
            if reportado != rastreado:
                erros.append(f"{r['id_saida']}: reportado {reportado} != rastro {rastreado}")
    erros += [f"{i}: rastro sem linha de saída" for i in sorted(set(soma_rastro) - vistos)]
    if erros:
        raise SaidaError("rastro não fecha:\n  " + "\n  ".join(erros))
