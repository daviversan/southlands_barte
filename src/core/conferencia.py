"""Conferência automática da saída (nível Extra, E1): Σ por arquivo × Σ rastro × totais de origem.

Relê os CSVs **gravados em disco** e cruza com as linhas de entrada já lidas, sem usar as estruturas
em memória das regras: é uma segunda conta, independente da que gerou os números. Roda sobre a
pasta temporária antes de publicar; se uma checagem bloqueante falhar, o comando falha e a saída
anterior fica intacta.

Checagens:
- por arquivo: Σ valor reportado = Σ rastro, e todo `id_saida` tem rastro;
- forma do rastro: `DIV`, `LAN` e `PEN` 1:1 com a linha de origem (a `PEN` de nota não emitida
  carrega as origens da comissão, como a NF); `COM` e `NF` com ao menos uma origem;
- todo `(arquivo_origem, ref_origem)` do rastro existe numa entrada;
- Orbe, Ponte e bancos: cada linha de entrada aparece uma vez e os totais de origem fecham;
- notas × comissões por linha de negócio, com as mesmas origens; divergência só em linha comissionada.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from src.core.saida import ARQUIVOS_EMISSIVEIS, ESQUEMAS
from src.regras.remessa import TIPOS_BLOQUEANTES, ref_ocorrencia

ZERO = Decimal(0)
REF_RODAPE_PONTE = "Operações!rodape"  # evidência da pendência RODAPE_DIVERGENTE


class ConferenciaError(ValueError):
    """Alguma checagem bloqueante da conferência não fechou."""


@dataclass(frozen=True)
class Checagem:
    grupo: str
    descricao: str
    esperado: str
    obtido: str
    ok: bool
    bloqueia: bool = True


def _brl(valor: Decimal) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ler(pasta: Path, nome: str) -> list[dict[str, str]]:
    with (pasta / f"{nome}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _soma(valores) -> Decimal:
    return sum((Decimal(v) for v in valores), ZERO)


def conferir(pasta, transacoes, relatorio, lancamentos, contratos) -> list[Checagem]:
    pasta = Path(pasta)
    saidas = {nome: _ler(pasta, nome) for nome in ARQUIVOS_EMISSIVEIS}
    rastro = _ler(pasta, "rastro")
    por_id: dict[str, list[dict[str, str]]] = {}
    for r in rastro:
        por_id.setdefault(r["id_saida"], []).append(r)
    checagens: list[Checagem] = []

    def checar(grupo, descricao, esperado, obtido, bloqueia=True, ok=None):
        ok = esperado == obtido if ok is None else ok
        checagens.append(Checagem(grupo, descricao, str(esperado), str(obtido), ok, bloqueia))

    def particao(a: Counter, b: Counter) -> str:
        return f"{sum(a.values())} + {sum(b.values())} = {sum((a + b).values())}"

    # Índice das linhas de entrada: (arquivo, ref) -> valor de referência da linha.
    orbe = {(t["arquivo_origem"], t["ref_origem"]): t["valor_bruto"] for t in transacoes}
    ponte: dict[tuple[str, str], Decimal] = {}
    ocorrencias: Counter[str] = Counter()
    for op in relatorio["operacoes"]:
        ocorrencias[op["num_operacao"]] += 1
        ponte[(op["arquivo_origem"], ref_ocorrencia(op["num_operacao"], ocorrencias[op["num_operacao"]]))] = op["spread_brl"]
    bancos = {(l["arquivo_origem"], l["ref_origem"]): l for l in lancamentos}
    evidencias = {(c["arquivo_origem"], c["ref_origem"]) for c in contratos}
    evidencias.add((relatorio["arquivo_origem"], REF_RODAPE_PONTE))
    conhecidas = set(orbe) | set(ponte) | set(bancos) | evidencias

    def chaves(ids) -> Counter:
        return Counter((r["arquivo_origem"], r["ref_origem"]) for i in ids for r in por_id.get(i, []))

    # 1. Por arquivo: Σ valor reportado = Σ rastro; todo id com rastro.
    for nome in ARQUIVOS_EMISSIVEIS:
        col = ESQUEMAS[nome].valor
        linhas = saidas[nome]
        reportado = _soma(r[col] for r in linhas)
        rastreado = _soma(x["valor"] for r in linhas for x in por_id.get(r["id_saida"], []))
        checar(nome, f"{len(linhas)} linhas: Σ {col} × Σ rastro", _brl(reportado), _brl(rastreado))
        sem = [r["id_saida"] for r in linhas if r["id_saida"] not in por_id]
        checar(nome, "linhas sem rastro", 0, len(sem))
    ids = {r["id_saida"] for linhas in saidas.values() for r in linhas}
    checar("rastro", "linhas de rastro sem linha de saída", 0, len(set(por_id) - ids))

    # 2. Forma do rastro.
    pen_nf = {r["id_saida"] for r in saidas["pendencias"] if r["tipo"] == "NF_NAO_EMITIDA"}
    for nome, prefixo in (("divergencias_taxa", "DIV"), ("lancamentos_classificados", "LAN"), ("pendencias", "PEN")):
        fora = [r["id_saida"] for r in saidas[nome]
                if r["id_saida"] not in pen_nf and len(por_id.get(r["id_saida"], [])) != 1]
        checar("rastro", f"{prefixo} com exatamente uma linha de origem", 0, len(fora))
    for nome in ("divergencias_taxa", "lancamentos_classificados"):
        trocadas = [r["id_saida"] for r in saidas[nome]
                    if [x["ref_origem"] for x in por_id.get(r["id_saida"], [])] != [r["ref_origem"]]]
        checar("rastro", f"{ESQUEMAS[nome].prefixo}: ref_origem da linha = ref_origem do rastro", 0, len(trocadas))
    desconhecidas = {(r["arquivo_origem"], r["ref_origem"]) for r in rastro} - conhecidas
    checar("rastro", "origens do rastro que não existem nas entradas", 0, len(desconhecidas))

    # 3. Orbe: cada linha uma vez (comissão CHECKOUT ou pendência); totais de bruto fecham.
    com_ck = [r["id_saida"] for r in saidas["comissoes_por_lojista"] if r["linha_negocio"] == "CHECKOUT"]
    com_rm = [r["id_saida"] for r in saidas["comissoes_por_lojista"] if r["linha_negocio"] == "REMESSA"]
    pen = [r for r in saidas["pendencias"] if r["id_saida"] not in pen_nf]
    pen_orbe = Counter(k for k in chaves(r["id_saida"] for r in pen) if k in orbe)
    comissionadas = Counter(k for k in chaves(com_ck) if k in orbe)
    checar("Orbe", "linhas da entrada × (comissionadas + em pendência), cada uma uma vez",
           len(orbe), particao(comissionadas, pen_orbe), ok=comissionadas + pen_orbe == Counter(orbe.keys()))
    bruto_pen = sum((orbe[k] for k in pen_orbe), ZERO)
    valor_pen = _soma(x["valor"] for r in pen for x in por_id[r["id_saida"]]
                      if (x["arquivo_origem"], x["ref_origem"]) in orbe)
    checar("Orbe", "pendências: Σ valor = Σ bruto das linhas", _brl(bruto_pen), _brl(valor_pen))
    total_bruto = sum(orbe.values(), ZERO)
    bruto_com = sum((orbe[k] for k in comissionadas), ZERO)
    checar("Orbe", "Σ bruto da entrada = comissionado + em pendência", _brl(total_bruto), _brl(bruto_com + bruto_pen))

    # 4. Ponte: cada linha uma vez (comissão REMESSA ou pendência bloqueante); spread fecha com as linhas.
    pen_bloq = [r["id_saida"] for r in pen if r["tipo"] in TIPOS_BLOQUEANTES]
    validas = Counter(k for k in chaves(com_rm) if k in ponte)
    bloqueadas = Counter(k for k in chaves(pen_bloq) if k in ponte)
    checar("Ponte", "linhas do relatório × (válidas + bloqueadas), cada uma uma vez",
           len(ponte), particao(validas, bloqueadas), ok=validas + bloqueadas == Counter(ponte.keys()))
    spread_linhas = sum(ponte.values(), ZERO)
    spread_bloq = _soma(x["valor"] for i in pen_bloq for x in por_id[i] if (x["arquivo_origem"], x["ref_origem"]) in ponte)
    checar("Ponte", "Σ Spread R$ das linhas = válidas + bloqueadas", _brl(spread_linhas),
           _brl(sum((ponte[k] for k in validas), ZERO) + spread_bloq))
    rodape = relatorio["rodape"]
    checar("Ponte", "rodapé do relatório × linhas (diferença vira pendência, não bloqueia)",
           f"{rodape['total_operacoes']} / {_brl(rodape['spread_total_brl'])}",
           f"{len(ponte)} / {_brl(spread_linhas)}", bloqueia=False)

    # 5. Bancos: cada lançamento uma vez e o total por banco fecha com o extrato.
    lan = saidas["lancamentos_classificados"]
    citados = chaves(r["id_saida"] for r in lan)
    checar("Bancos", "lançamentos do extrato × LAN, cada um uma vez", len(bancos),
           sum(citados.values()), ok=citados == Counter(bancos.keys()))
    for banco in sorted({l["banco"] for l in lancamentos}):
        entrada = [l["valor"] for l in lancamentos if l["banco"] == banco]
        saida = [r for r in lan if r["banco"] == banco]
        checar("Bancos", f"{banco}: linhas e Σ valor do extrato × LAN",
               f"{len(entrada)} / {_brl(sum(entrada, ZERO))}", f"{len(saida)} / {_brl(_soma(r['valor'] for r in saida))}")

    # 6. Notas × comissões, por linha de negócio, com as mesmas origens.
    notas = saidas["notas_a_emitir"]
    for linha, ids_com, indice in (("CHECKOUT", com_ck, orbe), ("REMESSA", com_rm, ponte)):
        ids_nf = [r["id_saida"] for r in notas if r["linha_negocio"] == linha]
        ids_nf += [i for i in sorted(pen_nf) if any((x["arquivo_origem"], x["ref_origem"]) in indice for x in por_id[i])]
        total_com = _soma(r["comissao_brl"] for r in saidas["comissoes_por_lojista"] if r["id_saida"] in set(ids_com))
        total_nf = _soma(x["valor"] for i in ids_nf for x in por_id[i])
        checar("Notas", f"{linha}: Σ NF (+ não emitidas) × Σ comissões", _brl(total_com), _brl(total_nf))
        checar("Notas", f"{linha}: NF com as mesmas origens das comissões", True, chaves(ids_com) == chaves(ids_nf))

    # 7. Divergência só em linha comissionada.
    comissionadas_todas = set(chaves(com_ck + com_rm))
    soltas = [r["id_saida"] for r in saidas["divergencias_taxa"]
              if not {(x["arquivo_origem"], x["ref_origem"]) for x in por_id.get(r["id_saida"], [])} <= comissionadas_todas]
    checar("Divergências", "divergências fora de linha comissionada", 0, len(soltas))
    return checagens


def imprimir(checagens: list[Checagem]) -> None:
    print("Conferência (saída × rastro × entradas):")
    grupo = None
    for c in checagens:
        if c.grupo != grupo:
            grupo = c.grupo
            print(f"  {grupo}")
        marca = "ok" if c.ok else ("FALHA" if c.bloqueia else "aviso")
        valores = c.obtido if c.ok else f"esperado {c.esperado}, obtido {c.obtido}"
        print(f"    [{marca}] {c.descricao}: {valores}")
    falhas = sum(1 for c in checagens if not c.ok and c.bloqueia)
    print(f"  {len(checagens)} checagens, {falhas} falha(s)")


def exigir(checagens: list[Checagem]) -> None:
    falhas = [c for c in checagens if not c.ok and c.bloqueia]
    if falhas:
        raise ConferenciaError("Conferência não fechou: " + "; ".join(
            f"{c.grupo} — {c.descricao} (esperado {c.esperado}, obtido {c.obtido})" for c in falhas))
