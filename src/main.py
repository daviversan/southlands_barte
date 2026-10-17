"""CLI de fechamento: regras em memória, conservação e publicação dos seis CSVs."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from datetime import date
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import yaml

from src.core.contratos import ResultadoCheckout, ResultadoFechamento
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


def run_minimo(entrada: Path, competencia: str, saida: Path,
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


def _componentes_notas():
    try:
        from src.regras.notas import gerar_notas
    except ModuleNotFoundError as erro:
        if erro.name == 'src.regras.notas':
            raise ValueError('Integração do Alvo depende da entrega de A: src/regras/notas.py') from erro
        raise
    return gerar_notas


def _conferir_destinos(entradas, processadas, bloqueadas):
    esperadas = Counter((a, r) for a, r, _ in entradas)
    if any(n != 1 for n in esperadas.values()):
        raise ValueError('Referência de entrada duplicada')
    recebidas = Counter((o.arquivo, o.ref) for o in processadas + bloqueadas)
    if esperadas != recebidas:
        raise ValueError('Conservação: cada linha deve aparecer exatamente uma vez')
    valores = {(a, r): v for a, r, v in entradas}
    for o in bloqueadas:
        if o.valor != valores[(o.arquivo, o.ref)]:
            raise ValueError('Pendência bloqueante deve preservar o valor assinado da fonte')


def _conferir_alvo(transacoes, relatorio, lancamentos, resultado):
    checkout, remessa, bancos = (resultado[k] for k in ('checkout', 'remessa', 'bancos'))
    if checkout['resumo'].get('fora_escopo_por_tipo') or 'por_tipo' not in checkout['resumo']:
        raise ValueError('Integração de A pendente: checkout deve processar todos os tipos do Alvo')
    comissoes = checkout['comissoes'] + remessa['comissoes']
    chaves = [(c['linha_negocio'], c['cnpj']) for c in comissoes]
    if len(chaves) != len(set(chaves)):
        raise ValueError('Comissão duplicada por CNPJ/linha de negócio')
    origens_checkout = [o for c in checkout['comissoes'] for o in c['origens']]
    refs_orbe = {(t['arquivo_origem'], t['ref_origem']) for t in transacoes}
    bloqueadas = [o for p in checkout['pendencias'] for o in p['origens'] if (o.arquivo, o.ref) in refs_orbe]
    _conferir_destinos([(t['arquivo_origem'], t['ref_origem'], t['valor_bruto']) for t in transacoes], origens_checkout, bloqueadas)
    por_tipo = {}
    processadas = Counter((o.arquivo, o.ref) for o in origens_checkout)
    for t in transacoes:
        item = por_tipo.setdefault(t['tipo_lancamento'], dict(total=0, processadas=0, bloqueadas=0))
        item['total'] += 1
        item['processadas' if processadas[(t['arquivo_origem'], t['ref_origem'])] else 'bloqueadas'] += 1
    resumo = checkout['resumo']
    esperado = dict(total_orbe=len(transacoes), por_tipo=por_tipo, linhas_processadas=len(origens_checkout),
                    linhas_bloqueadas=len(bloqueadas), contagens_por_arquivo=dict(Counter(t['arquivo_origem'] for t in transacoes)))
    for k, v in esperado.items():
        if resumo.get(k) != v:
            raise ValueError(f'Resumo de checkout inconsistente: {k}')
    ocorrencias, entradas_ponte = Counter(), []
    for op in relatorio['operacoes']:
        ref = op['num_operacao']
        ocorrencias[ref] += 1
        if ocorrencias[ref] > 1:
            ref += f'#{ocorrencias[ref]}'
        entradas_ponte.append((op['arquivo_origem'], ref, op['spread_brl']))
    tipos_bloqueantes = {'OPERACAO_REPETIDA', 'CONTESTACAO', 'CADASTRO_NAO_RESOLVIDO', 'OPERACAO_COM_RESSALVA'}
    origens_remessa = [o for c in remessa['comissoes'] for o in c['origens']]
    bloqueadas = [o for p in remessa['pendencias'] if p['tipo'] in tipos_bloqueantes for o in p['origens']]
    _conferir_destinos(entradas_ponte, origens_remessa, bloqueadas)
    r = remessa['resumo']
    if (r['linhas_relatorio'], r['validas'], r['bloqueadas'], r['operacoes_distintas']) != (
            len(entradas_ponte), len(origens_remessa), len(bloqueadas), len(ocorrencias)):
        raise ValueError('Resumo da remessa inconsistente')
    _conferir_destinos([(l['arquivo_origem'], l['ref_origem'], l['valor']) for l in lancamentos],
                      [o for l in bancos['lancamentos'] for o in l['origens']], [])
    for l in bancos['lancamentos']:
        if len(l['origens']) != 1 or l['origens'][0].valor != l['valor']:
            raise ValueError('Lançamento bancário não preserva valor da fonte')
    rb = bancos['resumo']
    if (rb['total_aurora'], rb['total_meridiano']) != (sum(l['banco'] == 'AURORA' for l in lancamentos), sum(l['banco'] == 'MERIDIANO' for l in lancamentos)):
        raise ValueError('Resumo bancário inconsistente')
    if rb['por_regra'] != dict(Counter(l['regra_id'] or 'HUMANO' for l in bancos['lancamentos'])) or rb['humano'] != sum(l['metodo'] == 'HUMANO' for l in bancos['lancamentos']):
        raise ValueError('Contagem por regra bancária inconsistente')
    grupos = [(comissoes, 'comissao_brl'), (checkout['divergencias'] + remessa['divergencias'], 'diferenca_brl'),
              (resultado['notas'], 'valor_brl'), (bancos['lancamentos'], 'valor'), (resultado['pendencias'], 'valor_brl')]
    for registros, campo in grupos:
        for registro in registros:
            if not registro['origens'] or sum((o.valor for o in registro['origens']), Decimal(0)) != registro[campo]:
                raise ValueError(f'Conservação de valor inválida: {campo}')
    for negocio in ('CHECKOUT', 'REMESSA'):
        elegiveis = [c for c in comissoes if c['linha_negocio'] == negocio and (negocio == 'REMESSA' or c['comissao_brl'] > 0)]
        notas = [n for n in resultado['notas'] if n['linha_negocio'] == negocio and n['valor_brl'] > 0]
        total = sum((c['comissao_brl'] for c in elegiveis), Decimal(0))
        if sum((n['valor_brl'] for n in notas), Decimal(0)) != max(total, Decimal(0)):
            raise ValueError('Soma das notas difere das comissões faturáveis')
        if negocio == 'CHECKOUT':
            if Counter(n['tomador_cnpj'] for n in notas) != Counter(c['cnpj'] for c in elegiveis):
                raise ValueError('Esperada uma nota CHECKOUT por lojista faturável')
        elif len(notas) != (1 if total > 0 else 0):
            raise ValueError('Esperada uma única nota REMESSA')
        if Counter((o.arquivo, o.ref, o.valor) for c in elegiveis for o in c['origens']) != Counter(
                (o.arquivo, o.ref, o.valor) for n in notas for o in n['origens']):
            raise ValueError('Notas devem preservar as mesmas origens das comissões')


def run(entrada: Path, competencia: str, saida: Path, regras_path: Path, cadastro_path: Path) -> ResultadoFechamento:
    from src.ingest.ponte import ler_ponte
    from src.ingest.bancos import ler_aurora, ler_meridiano
    from src.ingest.plano import ler_plano
    from src.regras.remessa import calcular_remessa
    from src.regras.classificacao import classificar_lancamentos
    _validar_competencia(competencia)
    entrada, saida = Path(entrada).resolve(), Path(saida).resolve()
    if not entrada.is_dir():
        raise ValueError(f'Pasta de entrada inexistente: {entrada}')
    regras = _carregar_yaml(Path(regras_path))
    cadastro = _carregar_yaml(Path(cadastro_path)).get('lojistas')
    if not isinstance(cadastro, dict):
        raise ValueError('Cadastro deve conter o mapa lojistas')
    arquivos = {}
    for nome, padrao in dict(taxas='02_*.xlsx', ponte='03_*.eml', plano='04_*.csv', aurora='05a_*.csv', meridiano='05b_*.ofx').items():
        encontrados = sorted(entrada.glob(padrao))
        if len(encontrados) != 1:
            raise ValueError(f'Esperado exatamente um arquivo {padrao}')
        arquivos[nome] = encontrados[0]
    ler_orbe, ler_taxas, calcular_checkout = _componentes_checkout()
    gerar_notas = _componentes_notas()
    transacoes, contratos = ler_orbe(entrada), ler_taxas(arquivos['taxas'])
    relatorio = ler_ponte(arquivos['ponte'])
    lancamentos = ler_aurora(arquivos['aurora'], regras) + ler_meridiano(arquivos['meridiano'])
    for registro in transacoes + lancamentos:
        dia = registro.get('data_movimento', registro.get('data'))
        if date.fromisoformat(dia).isoformat()[:7] != competencia:
            raise ValueError(f"Transação {registro['ref_origem']} fora da competência {competencia}")
    checkout = calcular_checkout(transacoes, contratos, cadastro, competencia, regras)
    remessa = calcular_remessa(relatorio, contratos, cadastro, competencia, regras)
    bancos = classificar_lancamentos(lancamentos, ler_plano(arquivos['plano']), regras)
    notas = gerar_notas(checkout['comissoes'] + remessa['comissoes'], competencia, regras)
    for nota in notas:
        if nota['linha_negocio'] == 'REMESSA' and nota['tomador_cnpj'] != regras['remessa']['nf_tomador']['cnpj']:
            raise ValueError('Tomador REMESSA difere da configuração')
    pendencias = checkout['pendencias'] + remessa['pendencias'] + bancos['pendencias'] + [p for n in notas for p in n['pendencias']]
    for p in pendencias:
        validar_pendencia(p)
    resultado = dict(checkout=checkout, remessa=remessa, bancos=bancos, notas=notas, pendencias=pendencias)
    _conferir_alvo(transacoes, relatorio, lancamentos, resultado)
    gravador = Saida()
    grupos = [
        ('comissoes_por_lojista', checkout['comissoes'] + remessa['comissoes'], lambda c: (c['linha_negocio'], c['cnpj'])),
        ('divergencias_taxa', checkout['divergencias'] + remessa['divergencias'], lambda d: (d['linha_negocio'], d['ref_origem'])),
        ('notas_a_emitir', [n for n in notas if n['valor_brl'] > 0], lambda n: (n['linha_negocio'], n['tomador_cnpj'])),
        ('lancamentos_classificados', bancos['lancamentos'], lambda l: (l['banco'], l['data'], l['ref_origem'])),
        ('pendencias', pendencias, lambda p: (p['tipo'], p['origens'][0].arquivo, p['ref_origem'])),
    ]
    for arquivo, registros, ordem in grupos:
        for registro in sorted(registros, key=ordem):
            linha = {k: v for k, v in registro.items() if k not in ('origens', 'contratos_utilizados', 'regra_id', 'pendencias')}
            gravador.emitir(arquivo, linha, registro['origens'])
    saida.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.fechamento-', dir=saida.parent) as temporaria:
        caminhos = gravador.gravar(temporaria)
        saida.mkdir(parents=True, exist_ok=True)
        for caminho in caminhos.values():
            caminho.replace(saida / caminho.name)
    print('Orbe:', checkout['resumo'])
    print('Remessa:', remessa['resumo'])
    for p in remessa['pendencias']:
        if p['tipo'] in ('OPERACAO_REPETIDA', 'CONTESTACAO'):
            print('  Reconciliação:', p['tipo'], p['ref_origem'], p['valor_brl'])
    print('Bancos:', bancos['resumo'])
    print('Pendências por tipo:', dict(Counter(p['tipo'] for p in pendencias)))
    print('Pendências por responsável:', dict(Counter(p['quem_decide'] for p in pendencias)))
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fechamento Tarvo")
    parser.add_argument('--nivel', choices=('minimo', 'alvo'), default='alvo')
    parser.add_argument("--entrada", type=Path, required=True)
    parser.add_argument("--competencia", required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--regras", type=Path, default=RAIZ / "config/regras.yaml")
    parser.add_argument("--cadastro", type=Path, default=RAIZ / "config/lojistas.yaml")
    args = parser.parse_args(argv)
    try:
        executar = run_minimo if args.nivel == 'minimo' else run
        executar(args.entrada, args.competencia, args.saida, args.regras, args.cadastro)
    except (OSError, ValueError, yaml.YAMLError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
