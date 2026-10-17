"""Classificação ordenada e conciliação de transferências, sem IA."""
from collections import Counter
from datetime import date
from decimal import Decimal
import re
import unicodedata
from src.core.saida import Origem
from src.core.contratos import LancamentoBancario, ContaContabil, ResultadoBancos
from src.regras.remessa import _pendencia


def _normalizar(texto):
    return ' '.join(unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode().upper().split())


def classificar_lancamentos(lancamentos: list[LancamentoBancario], plano: list[ContaContabil], regras: dict) -> ResultadoBancos:
    cfg = regras['bancos']
    modo = cfg['folha_e_impostos_de_08']
    if modo not in ('baixa_provisao', 'despesa'):
        raise ValueError('Modo de folha/impostos inválido')
    janela = cfg.get('janela_contrapartida_dias', 3)
    if not isinstance(janela, int) or janela < 0:
        raise ValueError('Janela de contrapartida inválida')
    permitidas = {c['codigo'] for c in plano if c['aceita_lancto']}
    compiladas, ids = [], set()
    for r in cfg['regras']:
        if r['id'] in ids or r['banco'] not in ('*', 'AURORA', 'MERIDIANO'):
            raise ValueError('Regra bancária duplicada ou banco inválido')
        ids.add(r['id'])
        conta = r.get('contas_por_modo', {}).get(modo, r.get('conta'))
        if conta is not None and conta not in permitidas:
            raise ValueError(f"Conta de regra fora do plano analítico: {conta}")
        try:
            compiladas.append((r, re.compile(r['padrao']), conta))
        except re.error as erro:
            raise ValueError(f"Regex inválida em {r['id']}: {erro}") from erro
    resultado, pendencias, por_regra, vistos, papeis = [], [], Counter(), set(), {}
    for l in lancamentos:
        chave = (l['arquivo_origem'], l['ref_origem'])
        if chave in vistos:
            raise ValueError('Referência bancária duplicada')
        vistos.add(chave)
        regra, conta = None, None
        for r, padrao, codigo in compiladas:
            if r['banco'] in ('*', l['banco']) and padrao.search(_normalizar(l['descricao'])):
                regra, conta = r, codigo
                break
        origem = Origem(*chave, l['valor'])
        classificado = {k: l[k] for k in ('banco', 'ref_origem', 'data', 'descricao', 'valor')}
        classificado.update(conta_codigo=conta or '', metodo='REGRA' if conta else 'HUMANO',
                            confianca=Decimal(1 if conta else 0), regra_id=regra['id'] if conta else None,
                            origens=[origem])
        resultado.append(classificado)
        por_regra[classificado['regra_id'] or 'HUMANO'] += 1
        if not conta:
            pendencias.append(_pendencia('LANCAMENTO_NAO_CLASSIFICADO', *chave, l['valor'],
                                         'Nenhuma regra com conta analítica disponível; requer classificação humana.'))
        elif regra.get('pendencia'):
            pendencias.append(_pendencia(regra['pendencia'], *chave, l['valor'], 'Lançamento classificado que requer análise financeira.'))
        if regra and regra.get('contrapartida'):
            papeis[chave] = regra['contrapartida']
    usados = set()
    ordenados = sorted(resultado, key=lambda l: (l['data'], l['banco'], l['ref_origem']))
    for l in ordenados:
        chave = (l['origens'][0].arquivo, l['ref_origem'])
        if papeis.get(chave) != 'saida':
            continue
        par = next((p for p in ordenados if (p['origens'][0].arquivo, p['ref_origem']) not in usados
                    and papeis.get((p['origens'][0].arquivo, p['ref_origem'])) == 'entrada'
                    and p['valor'] == -l['valor'] and l['valor'] < 0
                    and 0 <= (date.fromisoformat(p['data']) - date.fromisoformat(l['data'])).days <= janela), None)
        if par:
            usados.add((par['origens'][0].arquivo, par['ref_origem']))
        else:
            pendencias.append(_pendencia('TRANSFERENCIA_SEM_CONTRAPARTIDA', *chave, l['valor'],
                                         f'Saída sem entrada de mesmo valor na janela de {janela} dias.'))
    return dict(lancamentos=resultado, pendencias=pendencias,
                resumo=dict(total_aurora=sum(l['banco'] == 'AURORA' for l in lancamentos),
                            total_meridiano=sum(l['banco'] == 'MERIDIANO' for l in lancamentos),
                            por_regra=dict(por_regra), humano=por_regra['HUMANO']))
