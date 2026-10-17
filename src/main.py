"""CLI do nível mínimo: leitores e cálculo de A, publicação e conservação de B."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import yaml

from src.core.contratos import ResultadoCheckout
from src.core.saida import Saida
from src.regras.pendencias import validar_pendencia

RAIZ = Path(__file__).resolve().parent.parent


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


def _componentes_checkout():
    # Importação adiada permite usar --help antes de integrar a entrega de A.
    try:
        from src.ingest.orbe import ler_orbe
        from src.ingest.taxas import ler_taxas
        from src.regras.checkout import calcular_checkout
    except ModuleNotFoundError as erro:
        if erro.name in ("src.ingest.orbe", "src.ingest.taxas", "src.regras.checkout"):
            raise ValueError(f"Integração depende da entrega do membro A: {erro.name}") from erro
        raise
    return ler_orbe, ler_taxas, calcular_checkout


def _conferir_conservacao(transacoes, resultado):
    vendas = {t["ref_origem"]: t for t in transacoes if t["tipo_lancamento"] == "VENDA"}
    if len({t["id_transacao"] for t in transacoes}) != len(transacoes):
        raise ValueError("Orbe contém id_transacao repetido")
    processadas, bloqueadas = [], []
    for comissao in resultado["comissoes"]:
        if comissao["linha_negocio"] != "CHECKOUT":
            raise ValueError("Nível mínimo permite somente CHECKOUT")
        processadas.extend(comissao["origens"])
    for pendencia in resultado["pendencias"]:
        validar_pendencia(pendencia)
        origens_venda = [o for o in pendencia["origens"] if o.ref in vendas
                         and o.arquivo == vendas[o.ref]["arquivo_origem"]]
        if origens_venda:
            if len(origens_venda) != 1 or len(pendencia["origens"]) != 1:
                raise ValueError("Venda bloqueada exige uma pendência com uma origem")
            origem = origens_venda[0]
            if origem.valor != vendas[origem.ref]["valor_bruto"]:
                raise ValueError("Pendência de venda deve rastrear o bruto assinado")
            bloqueadas.extend(origens_venda)
        elif pendencia["valor_brl"] != 0:
            raise ValueError("Pendência cadastral deve ter valor zero")
    esperadas = Counter((t["arquivo_origem"], t["ref_origem"]) for t in vendas.values())
    recebidas = Counter((o.arquivo, o.ref) for o in processadas + bloqueadas)
    if esperadas != recebidas:
        raise ValueError("Conservação: cada venda deve aparecer exatamente uma vez na saída")
    cnpjs = [c["cnpj"] for c in resultado["comissoes"]]
    if len(set(cnpjs)) != len(cnpjs):
        raise ValueError("Comissão deve ter uma linha por CNPJ")
    esperado = {
        "total_orbe": len(transacoes), "vendas_total": len(vendas),
        "vendas_processadas": len(processadas), "vendas_bloqueadas": len(bloqueadas),
        "fora_escopo_por_tipo": dict(Counter(t["tipo_lancamento"] for t in transacoes
                                             if t["tipo_lancamento"] != "VENDA")),
        "contagens_por_arquivo": dict(Counter(t["arquivo_origem"] for t in transacoes)),
    }
    if resultado["resumo"] != esperado:
        raise ValueError(f"Resumo não conserva as entradas; esperado: {esperado}")


def run(entrada: Path, competencia: str, saida: Path,
        regras_path: Path, cadastro_path: Path) -> ResultadoCheckout:
    _validar_competencia(competencia)
    entrada, saida = Path(entrada).resolve(), Path(saida).resolve()
    if not entrada.is_dir():
        raise ValueError(f"Pasta de entrada inexistente: {entrada}")
    regras = _carregar_yaml(Path(regras_path))
    cadastro = _carregar_yaml(Path(cadastro_path)).get("lojistas")
    if not isinstance(cadastro, dict):
        raise ValueError("Cadastro deve conter o mapa lojistas")
    if not isinstance(regras.get("checkout"), dict):
        raise ValueError("Regras devem conter o mapa checkout")
    arquivos_taxas = sorted(entrada.glob("02_*.xlsx"))
    if len(arquivos_taxas) != 1:
        raise ValueError("Esperado exatamente um arquivo de taxas 02_*.xlsx na entrada")
    ler_orbe, ler_taxas, calcular_checkout = _componentes_checkout()
    transacoes = ler_orbe(entrada)
    for transacao in transacoes:
        data = date.fromisoformat(transacao["data_movimento"])
        if data.isoformat()[:7] != competencia:
            raise ValueError(f"Transação {transacao['id_transacao']} fora da competência {competencia}")
    contratos = ler_taxas(arquivos_taxas[0])
    resultado = calcular_checkout(transacoes, contratos, cadastro, competencia, regras)
    _conferir_conservacao(transacoes, resultado)
    gravador = Saida()
    for comissao in sorted(resultado["comissoes"], key=lambda c: c["cnpj"]):
        gravador.emitir("comissoes_por_lojista", {k: v for k, v in comissao.items()
                       if k not in ("origens", "contratos_utilizados")}, comissao["origens"])
    for pendencia in sorted(resultado["pendencias"], key=lambda p:
                            (p["tipo"], p["origens"][0].arquivo, p["ref_origem"])):
        gravador.emitir("pendencias", {k: v for k, v in pendencia.items() if k != "origens"},
                       pendencia["origens"])
    # Só publica depois de gravar e reconferir todos os CSVs em disco.
    saida.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".fechamento-", dir=saida.parent) as temporaria:
        caminhos = gravador.gravar(temporaria)
        saida.mkdir(parents=True, exist_ok=True)
        for caminho in caminhos.values():
            caminho.replace(saida / caminho.name)
    resumo = resultado["resumo"]
    print(f"Orbe: {resumo['total_orbe']} linhas; vendas: {resumo['vendas_total']} = "
          f"{resumo['vendas_processadas']} processadas + {resumo['vendas_bloqueadas']} bloqueadas")
    for arquivo, quantidade in sorted(resumo["contagens_por_arquivo"].items()):
        print(f"  {arquivo}: {quantidade} linhas")
    for tipo, quantidade in sorted(resumo["fora_escopo_por_tipo"].items()):
        print(f"  {tipo}: {quantidade} fora do escopo deste nível")
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fechamento mínimo de checkout (somente vendas)")
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
