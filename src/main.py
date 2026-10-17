"""CLI do fechamento (nível Alvo): leitores, regras de A e B, conservação e publicação.

Só este módulo fala com `Saida`. Os módulos de regras devolvem registros com origens; aqui eles são
conferidos (cada linha de entrada uma vez, Σ rastro = valor), ordenados, emitidos e publicados.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from src.core.contratos import ResultadoFechamento
from src.core.saida import ESQUEMAS, Saida
from src.ingest.bancos import ler_aurora, ler_meridiano
from src.ingest.orbe import ler_orbe
from src.ingest.plano import ler_plano
from src.ingest.ponte import ler_ponte
from src.ingest.taxas import ler_taxas
from src.regras.checkout import calcular_checkout
from src.regras.classificacao import classificar_lancamentos
from src.regras.notas import calcular_notas
from src.regras.pendencias import validar_pendencia
from src.regras.remessa import TIPOS_BLOQUEANTES, calcular_remessa, ref_ocorrencia

RAIZ = Path(__file__).resolve().parent.parent

# padrão de nome -> papel. A Orbe é descoberta pelo próprio leitor (01_ obrigatório, 06_ opcional).
ARQUIVOS = {
    "taxas": "02_*.xlsx",
    "ponte": "03_*.eml",
    "plano": "04_*.csv",
    "aurora": "05a_*.csv",
    "meridiano": "05b_*.ofx",
}


def _carregar_yaml(caminho: Path) -> dict:
    with caminho.open(encoding="utf-8") as arquivo:
        conteudo = yaml.safe_load(arquivo)
    if not isinstance(conteudo, dict):
        raise ValueError(f"{caminho}: esperado mapa YAML")
    return conteudo


def _validar_competencia(competencia: str) -> None:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", competencia):
        raise ValueError("competência deve ter formato AAAA-MM")
    date.fromisoformat(f"{competencia}-01")


def _descobrir(entrada: Path) -> dict[str, Path]:
    achados = {}
    for papel, padrao in ARQUIVOS.items():
        candidatos = sorted(entrada.glob(padrao))
        if len(candidatos) != 1:
            raise ValueError(f"Esperado exatamente um arquivo {padrao} na entrada (encontrados {len(candidatos)})")
        achados[papel] = candidatos[0]
    return achados


def _fora_competencia(nome: str, datas: list[tuple[str, str]], competencia: str) -> None:
    fora = [ref for ref, d in datas if d[:7] != competencia]
    if fora:
        raise ValueError(f"{nome}: {len(fora)} linha(s) fora da competência {competencia}, ex.: {', '.join(fora[:3])}")


def _chaves(origens) -> Counter:
    return Counter((o.arquivo, o.ref) for o in origens)


def _conferir_conservacao(transacoes, relatorio, lancamentos, analiticas, r: ResultadoFechamento) -> None:
    """Cada linha de entrada aparece uma vez; valores e contagens fecham. Falha = nada é publicado."""
    checkout, remessa, bancos = r["checkout"], r["remessa"], r["bancos"]
    for p in r["pendencias"]:
        validar_pendencia(p)

    # Orbe: cada linha em exatamente uma origem de comissão CHECKOUT ou pendência bloqueante.
    if len({t["id_transacao"] for t in transacoes}) != len(transacoes):
        raise ValueError("Orbe contém id_transacao repetido")
    orbe = {(t["arquivo_origem"], t["ref_origem"]): t for t in transacoes}
    processadas = [o for c in checkout["comissoes"] for o in c["origens"]]
    bloqueadas = []
    for p in checkout["pendencias"]:
        das_linhas = [o for o in p["origens"] if (o.arquivo, o.ref) in orbe]
        if das_linhas:
            if len(das_linhas) != 1 or len(p["origens"]) != 1:
                raise ValueError("Linha da Orbe bloqueada exige uma pendência com uma origem")
            if das_linhas[0].valor != orbe[(das_linhas[0].arquivo, das_linhas[0].ref)]["valor_bruto"]:
                raise ValueError("Pendência de linha da Orbe deve rastrear o bruto assinado")
            bloqueadas.extend(das_linhas)
        elif p["valor_brl"] != 0:
            raise ValueError("Pendência cadastral deve ter valor zero")
    if _chaves(processadas + bloqueadas) != Counter(orbe.keys()):
        raise ValueError("Conservação: cada linha da Orbe deve aparecer exatamente uma vez na saída")
    tipo_de = {k: t["tipo_lancamento"] for k, t in orbe.items()}
    por_tipo: dict[str, dict[str, int]] = {}
    for chave, t in orbe.items():
        por_tipo.setdefault(t["tipo_lancamento"], {"total": 0, "processadas": 0, "bloqueadas": 0})["total"] += 1
    for o in processadas:
        por_tipo[tipo_de[(o.arquivo, o.ref)]]["processadas"] += 1
    for o in bloqueadas:
        por_tipo[tipo_de[(o.arquivo, o.ref)]]["bloqueadas"] += 1
    vendas = por_tipo.get("VENDA", {"total": 0, "processadas": 0, "bloqueadas": 0})
    esperado = {
        "total_orbe": len(transacoes), "por_tipo": dict(sorted(por_tipo.items())),
        "linhas_processadas": len(processadas), "linhas_bloqueadas": len(bloqueadas),
        "vendas_total": vendas["total"], "vendas_processadas": vendas["processadas"],
        "vendas_bloqueadas": vendas["bloqueadas"], "fora_escopo_por_tipo": {},
        "contagens_por_arquivo": dict(sorted(Counter(t["arquivo_origem"] for t in transacoes).items())),
    }
    if checkout["resumo"] != esperado:
        raise ValueError(f"Resumo do checkout não conserva as entradas; esperado: {esperado}")
    processadas_chaves = set(_chaves(processadas))
    for d in checkout["divergencias"]:
        if len(d["origens"]) != 1 or (d["origens"][0].arquivo, d["origens"][0].ref) not in processadas_chaves:
            raise ValueError(f"Divergência {d['ref_origem']} deve apontar para uma linha processada")

    # Ponte: cada linha (k-ésima ocorrência = `<Nº>#k`) em comissão REMESSA ou pendência bloqueante.
    ocorrencia: Counter[str] = Counter()
    ponte = {}
    for op in relatorio["operacoes"]:
        ocorrencia[op["num_operacao"]] += 1
        ponte[(op["arquivo_origem"], ref_ocorrencia(op["num_operacao"], ocorrencia[op["num_operacao"]]))] = op
    validas = [o for c in remessa["comissoes"] for o in c["origens"]]
    contestadas = []
    for p in remessa["pendencias"]:
        if p["tipo"] in TIPOS_BLOQUEANTES:
            o = p["origens"][0]
            if len(p["origens"]) != 1 or (o.arquivo, o.ref) not in ponte or o.valor != ponte[(o.arquivo, o.ref)]["spread_brl"]:
                raise ValueError(f"Pendência {p['tipo']} {p['ref_origem']} deve rastrear o Spread R$ da linha")
            contestadas.append(o)
        elif p["tipo"] == "OPERACAO_POSSIVEL_DUPLICIDADE" and p["valor_brl"] != 0:
            raise ValueError("Sinalização de possível duplicidade deve ter valor zero")
    if _chaves(validas + contestadas) != Counter(ponte.keys()):
        raise ValueError("Conservação: cada linha da Ponte deve aparecer exatamente uma vez na saída")
    res = remessa["resumo"]
    if (res["linhas_relatorio"], res["validas"], res["bloqueadas"]) != (len(ponte), len(validas), len(contestadas)):
        raise ValueError("Resumo da remessa não conserva as linhas do relatório")
    validas_chaves = set(_chaves(validas))
    for d in remessa["divergencias"]:
        if len(d["origens"]) != 1 or (d["origens"][0].arquivo, d["origens"][0].ref) not in validas_chaves:
            raise ValueError(f"Divergência {d['ref_origem']} deve apontar para uma operação válida")

    # Bancos: cada lançamento uma vez; conta analítica (ou vazia só para HUMANO); pendências sobre lançamentos.
    banco = {(l["arquivo_origem"], l["ref_origem"]): l for l in lancamentos}
    if len(banco) != len(lancamentos):
        raise ValueError("Lançamento bancário com referência repetida")
    if _chaves(o for l in bancos["lancamentos"] for o in l["origens"]) != Counter(banco.keys()):
        raise ValueError("Conservação: cada lançamento bancário deve aparecer exatamente uma vez")
    for l in bancos["lancamentos"]:
        if l["metodo"] == "HUMANO" and l["conta_codigo"] == "":
            continue
        if l["conta_codigo"] not in analiticas:
            raise ValueError(f"Lançamento {l['ref_origem']}: conta {l['conta_codigo']!r} não aceita lançamento")
    for p in bancos["pendencias"]:
        o = p["origens"][0]
        if len(p["origens"]) != 1 or (o.arquivo, o.ref) not in banco or o.valor != banco[(o.arquivo, o.ref)]["valor"]:
            raise ValueError(f"Pendência {p['tipo']} {p['ref_origem']} deve rastrear o lançamento")
    humanos = sum(1 for l in bancos["lancamentos"] if l["metodo"] == "HUMANO")
    if humanos != sum(1 for p in bancos["pendencias"] if p["tipo"] == "LANCAMENTO_NAO_CLASSIFICADO"):
        raise ValueError("Todo lançamento HUMANO precisa de uma pendência LANCAMENTO_NAO_CLASSIFICADO")

    # Comissões e notas.
    chaves = [(c["cnpj"], c["linha_negocio"]) for c in checkout["comissoes"] + remessa["comissoes"]]
    if len(set(chaves)) != len(chaves):
        raise ValueError("Comissão deve ter uma linha por (CNPJ, linha de negócio)")
    # Notas: Σ NF + Σ não emitidas = Σ comissões, por linha de negócio, com as mesmas origens.
    nao_emitidas = [p for p in r["pendencias"] if p["tipo"] == "NF_NAO_EMITIDA"]
    notas_ck = {n["tomador_cnpj"]: n for n in r["notas"] if n["linha_negocio"] == "CHECKOUT"}
    sem_nota_ck = {p["ref_origem"]: p for p in nao_emitidas}
    for c in checkout["comissoes"]:
        destino = notas_ck.pop(c["cnpj"], None) if c["comissao_brl"] > 0 else sem_nota_ck.get(c["cnpj"])
        valor = None if destino is None else destino["valor_brl"]
        if destino is None or valor != c["comissao_brl"] or _chaves(destino["origens"]) != _chaves(c["origens"]):
            raise ValueError(f"Comissão CHECKOUT de {c['cnpj']} sem NF (ou NF_NAO_EMITIDA) com o mesmo valor e origens")
    if notas_ck:
        raise ValueError(f"NF CHECKOUT sem comissão correspondente: {sorted(notas_ck)}")
    notas_rm = [n for n in r["notas"] if n["linha_negocio"] == "REMESSA"]
    if remessa["comissoes"]:
        origens = _chaves(o for c in remessa["comissoes"] for o in c["origens"])
        total = sum((c["comissao_brl"] for c in remessa["comissoes"]), Decimal(0))
        destinos = notas_rm + [p for p in nao_emitidas if _chaves(p["origens"]) == origens]
        if len(destinos) != 1 or destinos[0]["valor_brl"] != total or _chaves(destinos[0]["origens"]) != origens:
            raise ValueError("Remessa deve ter exatamente uma NF (ou NF_NAO_EMITIDA) com o total e as origens das comissões")
    elif notas_rm:
        raise ValueError("NF REMESSA sem comissão de remessa")


def _natural(ref: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", ref))


def _emitir_todos(r: ResultadoFechamento) -> Saida:
    gravador = Saida()

    def emitir(nome, registro):
        colunas = [c for c in ESQUEMAS[nome].colunas if c != "id_saida"]
        gravador.emitir(nome, {c: registro[c] for c in colunas}, registro["origens"])

    ordem_linha = {"CHECKOUT": 0, "REMESSA": 1}
    for c in sorted(r["checkout"]["comissoes"] + r["remessa"]["comissoes"],
                    key=lambda c: (ordem_linha[c["linha_negocio"]], c["cnpj"])):
        emitir("comissoes_por_lojista", c)
    for d in sorted(r["checkout"]["divergencias"] + r["remessa"]["divergencias"],
                    key=lambda d: (d["linha_negocio"], d["ref_origem"])):
        emitir("divergencias_taxa", d)
    for n in sorted(r["notas"], key=lambda n: (n["linha_negocio"], n["tomador_cnpj"])):
        emitir("notas_a_emitir", n)
    for l in sorted(r["bancos"]["lancamentos"], key=lambda l: (l["banco"], l["data"], _natural(l["ref_origem"]))):
        emitir("lancamentos_classificados", l)
    for p in sorted(r["pendencias"], key=lambda p: (p["tipo"], p["origens"][0].arquivo, p["ref_origem"])):
        emitir("pendencias", p)
    return gravador


def _brl(valor: Decimal) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _imprimir_resumo(r: ResultadoFechamento) -> None:
    ck = r["checkout"]["resumo"]
    print(f"Orbe: {ck['total_orbe']} linhas = {ck['linhas_processadas']} processadas + "
          f"{ck['linhas_bloqueadas']} bloqueadas")
    for tipo, c in ck["por_tipo"].items():
        print(f"  {tipo}: {c['total']} = {c['processadas']} processadas + {c['bloqueadas']} bloqueadas")
    for arquivo, quantidade in ck["contagens_por_arquivo"].items():
        print(f"  {arquivo}: {quantidade} linhas")
    rm = r["remessa"]["resumo"]
    rec, ops = rm["reconciliacao"], rm["reconciliacao_operacoes"]
    print(f"Ponte: {rm['linhas_relatorio']} linhas ({rm['operacoes_distintas']} operações distintas) = "
          f"{rm['validas']} válidas + {rm['bloqueadas']} bloqueadas; {rm['sem_spread_contratado']} sem spread "
          "contratado (divergência não calculada)")
    print(f"  rodapé R$ {_brl(rec['rodape_spread_total_brl'])} (linhas somam R$ {_brl(rec['soma_linhas_brl'])})")
    for nome in ("repetidas", "negativos", "cadastro", "ressalva"):
        if ops[nome]:
            print(f"  (−) {nome}: R$ {_brl(rec[nome + '_brl'])} [{', '.join(ops[nome])}]")
    print(f"  = base da comissão R$ {_brl(rec['base_comissao_brl'])}; comissão R$ {_brl(rec['comissao_brl'])}")
    bc = r["bancos"]["resumo"]
    print(f"Bancos: {bc['total_aurora']} Aurora + {bc['total_meridiano']} Meridiano = "
          f"{bc['total_aurora'] + bc['total_meridiano']}; HUMANO: {bc['humano']}")
    for regra, quantidade in bc["por_regra"].items():
        print(f"  {regra}: {quantidade}")
    notas = r["notas"]
    print(f"Notas: {len(notas)} ({sum(1 for n in notas if n['linha_negocio'] == 'CHECKOUT')} CHECKOUT, "
          f"{sum(1 for n in notas if n['linha_negocio'] == 'REMESSA')} REMESSA)")
    print(f"Pendências: {len(r['pendencias'])}")
    for tipo, quantidade in sorted(Counter(p["tipo"] for p in r["pendencias"]).items()):
        print(f"  {tipo}: {quantidade}")
    for quem, quantidade in sorted(Counter(p["quem_decide"] for p in r["pendencias"]).items()):
        print(f"  quem decide {quem}: {quantidade}")


def run(entrada: Path, competencia: str, saida: Path,
        regras_path: Path, cadastro_path: Path) -> ResultadoFechamento:
    _validar_competencia(competencia)
    entrada, saida = Path(entrada).resolve(), Path(saida).resolve()
    if not entrada.is_dir():
        raise ValueError(f"Pasta de entrada inexistente: {entrada}")
    regras = _carregar_yaml(Path(regras_path))
    cadastro = _carregar_yaml(Path(cadastro_path)).get("lojistas")
    if not isinstance(cadastro, dict):
        raise ValueError("Cadastro deve conter o mapa lojistas")
    for secao in ("checkout", "remessa", "bancos", "notas"):
        if not isinstance(regras.get(secao), dict):
            raise ValueError(f"Regras devem conter o mapa {secao}")
    arquivos = _descobrir(entrada)

    transacoes = ler_orbe(entrada)
    contratos = ler_taxas(arquivos["taxas"])
    relatorio = ler_ponte(arquivos["ponte"])
    plano = ler_plano(arquivos["plano"])
    lancamentos = ler_aurora(arquivos["aurora"], regras) + ler_meridiano(arquivos["meridiano"])
    _fora_competencia("Orbe", [(t["id_transacao"], t["data_movimento"]) for t in transacoes], competencia)
    _fora_competencia("Ponte (Data Contratação)",
                      [(o["num_operacao"], o["data_contratacao"]) for o in relatorio["operacoes"]], competencia)
    _fora_competencia("Bancos", [(l["ref_origem"], l["data"]) for l in lancamentos], competencia)

    checkout = calcular_checkout(transacoes, contratos, cadastro, competencia, regras)
    remessa = calcular_remessa(relatorio, contratos, cadastro, competencia, regras)
    bancos = classificar_lancamentos(lancamentos, plano, regras)
    notas, pendencias_notas = calcular_notas(checkout["comissoes"] + remessa["comissoes"], competencia, regras)
    resultado: ResultadoFechamento = {
        "checkout": checkout, "remessa": remessa, "bancos": bancos, "notas": notas,
        "pendencias": checkout["pendencias"] + pendencias_notas + remessa["pendencias"] + bancos["pendencias"],
    }
    analiticas = {c["codigo"] for c in plano if c["aceita_lancto"]}
    _conferir_conservacao(transacoes, relatorio, lancamentos, analiticas, resultado)
    gravador = _emitir_todos(resultado)

    # Só publica depois de gravar e reconferir todos os CSVs em disco.
    saida.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".fechamento-", dir=saida.parent) as temporaria:
        caminhos = gravador.gravar(temporaria)
        saida.mkdir(parents=True, exist_ok=True)
        for caminho in caminhos.values():
            caminho.replace(saida / caminho.name)
    _imprimir_resumo(resultado)
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fechamento mensal Tarvo: checkout, remessa, notas e bancos")
    parser.add_argument("--entrada", type=Path, required=True)
    parser.add_argument("--competencia", required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--regras", type=Path, default=RAIZ / "config/regras.yaml")
    parser.add_argument("--cadastro", type=Path, default=RAIZ / "config/lojistas.yaml")
    args = parser.parse_args(argv)
    try:
        run(args.entrada, args.competencia, args.saida, args.regras, args.cadastro)
    except (OSError, ValueError, yaml.YAMLError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
