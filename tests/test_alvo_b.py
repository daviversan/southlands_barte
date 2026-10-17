"""Critérios de B e integração A/B com entradas reais e limites sintéticos."""
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
from collections import Counter
import csv
import hashlib

import openpyxl
import pytest
import yaml

from src import main
from src.core.normalize import pct
from src.core.saida import Origem, Saida, SaidaError, conferir_diretorio
from src.ingest.bancos import ler_aurora, ler_meridiano
from src.ingest.plano import ler_plano
from src.ingest.ponte import ler_ponte
from src.ingest.taxas import ler_taxas
from src.regras.classificacao import classificar_lancamentos
from src.regras.remessa import calcular_remessa

PACK = Path(__file__).resolve().parents[1] / 'context/tarvo_data_pack'
REGRAS = main.RAIZ / 'config/regras.yaml'
CADASTRO = main.RAIZ / 'config/lojistas.yaml'


@pytest.fixture
def regras():
    return yaml.safe_load(REGRAS.read_text(encoding='utf-8'))


@pytest.fixture
def relatorio():
    return ler_ponte(next(PACK.glob('03_*.eml')))


def contratos_alvo(caminho):
    """Conferência independente da coluna de spread fornecida pelo leitor de A."""
    contratos = ler_taxas(caminho)
    wb = openpyxl.load_workbook(caminho, data_only=True)
    try:
        ws = wb['Taxas vigentes']
        cab = next(r for r in ws.values if 'Spread remessa' in r)
        coluna = cab.index('Spread remessa') + 1
        for c in contratos:
            valor = ws.cell(int(c['ref_origem'].split('!L')[1]), coluna).value
            c['spread_remessa_pct'] = None if valor is None or str(valor).strip().lower() == 'padrão' else pct(valor)
    finally:
        wb.close()
    return contratos


def calcular_real(relatorio, regras):
    return calcular_remessa(relatorio, contratos_alvo(next(PACK.glob('02_*.xlsx'))),
                            yaml.safe_load(CADASTRO.read_text(encoding='utf-8'))['lojistas'], '2026-09', regras)


def test_remessa_data_pack(relatorio, regras):
    r = calcular_real(relatorio, regras)
    assert len(relatorio['operacoes']) == 233
    assert sum(o['data_liquidacao'].startswith('2026-10') for o in relatorio['operacoes']) == 6
    assert (r['resumo']['validas'], r['resumo']['bloqueadas'], r['resumo']['operacoes_distintas']) == (228, 5, 232)
    assert r['resumo']['sem_spread_contratado'] == 51
    assert sum(c['comissao_brl'] for c in r['comissoes']) == D('39543.45')
    assert len(r['comissoes']) == 14
    assert len(r['divergencias']) == 41
    assert sum(d['diferenca_brl'] for d in r['divergencias']) == D('1419.05')
    rec = r['resumo']['reconciliacao']
    assert (rec['rodape_spread_total_brl'], rec['repetidas_brl'], rec['negativos_brl'], rec['base_comissao_brl']) == (
        D('78073.59'), D('821.88'), D('-1834.05'), D('79085.76'))
    repetida = next(p for p in r['pendencias'] if p['tipo'] == 'OPERACAO_REPETIDA')
    assert repetida['ref_origem'] == 'PC-0926-0162#2'
    negativos = {p['ref_origem'] for p in r['pendencias'] if p['tipo'] == 'CONTESTACAO'}
    assert len(negativos) == 4
    assert not negativos & {d['ref_origem'] for d in r['divergencias']}
    assert not negativos & {o.ref for c in r['comissoes'] for o in c['origens']}


def test_remessa_excecoes(relatorio, regras):
    relatorio['rodape']['total_operacoes'] += 1
    r = calcular_real(relatorio, regras)
    assert next(p for p in r['pendencias'] if p['tipo'] == 'RODAPE_DIVERGENTE')['valor_brl'] == 0
    regras['remessa']['aprovado_com_ressalva_entra'] = False
    r = calcular_real(relatorio, regras)
    assert sum(p['tipo'] == 'OPERACAO_COM_RESSALVA' for p in r['pendencias']) == 16
    relatorio['operacoes'][0]['data_contratacao'] = '2026-08-31'
    with pytest.raises(ValueError, match='fora da competência'):
        calcular_real(relatorio, regras)


def test_remessa_sinaliza_sem_descartar_e_tolerancia(relatorio, regras):
    op = deepcopy(relatorio['operacoes'][0])
    op.update(num_operacao='X', ref_origem='X', cnpj='00000000000001', spread_brl=D('100.03'),
              valor_me=D('1000'), ptax=D('10'), spread_pct=D('1.0009'))
    relatorio.update(operacoes=[op, {**op, 'num_operacao': 'Y', 'ref_origem': 'Y'}],
                     rodape=dict(total_operacoes=2, spread_total_brl=D('200.06')))
    contrato = dict(cnpj=op['cnpj'], lojista='Contrato', spread_remessa_pct=D(1), vigencia_inicio=None, vigencia_fim=None)
    r = calcular_remessa(relatorio, [contrato], {}, '2026-09', regras)
    assert r['resumo']['validas'] == 2
    assert not r['divergencias']  # diferença monetária não é alarme quando taxa está na tolerância
    assert [p['tipo'] for p in r['pendencias']] == ['OPERACAO_POSSIVEL_DUPLICIDADE']
    op['spread_pct'] = D('1.0011')
    r = calcular_remessa(relatorio, [contrato], {}, '2026-09', regras)
    assert r['divergencias'][0]['diferenca_brl'] == D('0.03')
    r = calcular_remessa(relatorio, [], {}, '2026-09', regras)
    assert r['resumo']['bloqueadas'] == 2


def bancos_reais(regras):
    return ler_aurora(next(PACK.glob('05a_*')), regras) + ler_meridiano(next(PACK.glob('05b_*')))


def test_bancos_data_pack(regras):
    entradas = bancos_reais(regras)
    plano = ler_plano(next(PACK.glob('04_*')))
    r = classificar_lancamentos(entradas, plano, regras)
    assert (r['resumo']['total_aurora'], r['resumo']['total_meridiano'], r['resumo']['humano']) == (84, 100, 0)
    assert len(r['lancamentos']) == 184
    assert entradas[0]['ref_origem'] == 'L9'
    for regra in regras['bancos']['regras']:
        assert r['resumo']['por_regra'][regra['id']] == {
            'ted_orbe':21, 'pix_lojista':44, 'transf_entre_contas':4, 'tarifa_aurora':2,
            'pix_receb_lojista':64, 'ted_ponte_liquidacao':21, 'ted_mesma_titularidade':3, 'aplicacao_cdb':3,
            'resgate_cdb':3, 'tarifa_meridiano':2}.get(regra['id'], 1)
    assert {(p['tipo'], p['valor_brl']) for p in r['pendencias']} == {
        ('CREDITO_NAO_IDENTIFICADO', D('7350')), ('TRANSFERENCIA_SEM_CONTRAPARTIDA', D('-300000'))}
    assert {l['conta_codigo'] for l in r['lancamentos']} <= {c['codigo'] for c in plano if c['aceita_lancto']}
    regras['bancos']['aurora_ref_offset'] = 1
    assert ler_aurora(next(PACK.glob('05a_*')), regras)[0]['ref_origem'] == 'L10'


def test_humano_configuracao_e_despesa(regras, tmp_path):
    entradas = bancos_reais(regras)
    plano = ler_plano(next(PACK.glob('04_*')))
    regras['bancos']['folha_e_impostos_de_08'] = 'despesa'
    r = classificar_lancamentos(entradas, plano, regras)
    assert r['resumo']['humano'] == 6
    desconhecido = {**entradas[0], 'descricao': 'SEM REGRA'}
    r = classificar_lancamentos([desconhecido], plano, regras)
    l = r['lancamentos'][0]
    assert l['metodo'] == 'HUMANO' and l['conta_codigo'] == '' and l['confianca'] == 0
    s = Saida()
    s.emitir('lancamentos_classificados', {k:v for k,v in l.items() if k not in ('origens','regra_id','arquivo_origem')}, l['origens'])
    s.gravar(tmp_path)
    conferir_diretorio(tmp_path)
    regras['bancos']['regras'][0]['conta'] = '1'
    with pytest.raises(ValueError, match='não existe no plano|não aceita lançamento'):
        classificar_lancamentos([], plano, regras)


def test_contrapartida_nao_reutiliza_entrada(regras):
    entradas = bancos_reais(regras)
    saida = next(l for l in entradas if l['valor'] == D('-350000'))
    entrada = next(l for l in entradas if l['valor'] == D('350000'))
    plano = ler_plano(next(PACK.glob('04_*')))
    r = classificar_lancamentos([saida, {**saida, 'ref_origem': 'X'}, entrada], plano, regras)
    assert sum(p['tipo'] == 'TRANSFERENCIA_SEM_CONTRAPARTIDA' for p in r['pendencias']) == 1
    entrada['data'] = '2026-09-06'
    r = classificar_lancamentos([saida, entrada], plano, regras)
    assert len(r['pendencias']) == 1


def test_integracao_publicacao_deterministica(tmp_path):
    destino = tmp_path / 'alvo'
    resultado = main.run(PACK, '2026-09', destino, REGRAS, CADASTRO)
    assert resultado['remessa']['resumo']['validas'] == 228
    assert len(resultado['notas']) == 19
    conferir_diretorio(destino)
    antes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destino.iterdir()}
    main.run(PACK, '2026-09', destino, REGRAS, CADASTRO)
    assert antes == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destino.iterdir()}


@pytest.mark.parametrize('defeito', ['gravacao', 'nota', 'competencia'])
def test_alvo_falha_preserva_publicacao(tmp_path, monkeypatch, defeito):
    destino = tmp_path/'alvo'
    main.run(PACK, '2026-09', destino, REGRAS, CADASTRO)
    antes = {p.name:p.read_bytes() for p in destino.iterdir()}
    competencia = '2026-09'
    if defeito == 'gravacao':
        def falhar(self, pasta):
            (Path(pasta)/'parcial.csv').write_text('parcial')
            raise SaidaError('Falha de conferência em disco')
        monkeypatch.setattr(Saida, 'gravar', falhar)
    elif defeito == 'nota':
        gerar = main.calcular_notas
        def corromper(*args):
            notas, pendencias = gerar(*args)
            notas[0]['valor_brl'] += D(1)
            return notas, pendencias
        monkeypatch.setattr(main, 'calcular_notas', corromper)
    else:
        competencia = '2026-08'
    with pytest.raises(ValueError):
        main.run(PACK, competencia, destino, REGRAS, CADASTRO)
    assert antes == {p.name:p.read_bytes() for p in destino.iterdir()}
    assert not list(tmp_path.glob('.fechamento-*'))
