"""Comissão de câmbio por operação e exceções rastreáveis."""
from collections import Counter
from decimal import Decimal
from src.core.normalize import q2
from src.core.saida import Origem
from src.core.contratos import RelatorioPonte, ContratoTaxa, ResultadoRemessa


def _pendencia(tipo, arquivo, ref, valor, motivo):
    return dict(tipo=tipo, ref_origem=ref, valor_brl=valor, motivo=motivo,
                quem_decide='Financeiro', origens=[Origem(arquivo, ref, valor)])


def calcular_remessa(relatorio: RelatorioPonte, contratos: list[ContratoTaxa], cadastro: dict[str, dict[str, str]],
                     competencia: str, regras: dict) -> ResultadoRemessa:
    cfg = regras['remessa']
    participacao = Decimal(str(cfg['participacao_tarvo']))
    tolerancia = Decimal(str(cfg['precisao_spread_pct'])) * 100
    if not 0 <= participacao <= 1 or tolerancia < 0:
        raise ValueError('Parâmetros da remessa inválidos')
    if relatorio['competencia'] not in (None, competencia):
        raise ValueError('Relatório Ponte fora da competência')
    por_cnpj = {}
    for c in contratos:
        por_cnpj.setdefault(c['cnpj'], []).append(c)
    nomes = {c['cnpj']: c['lojista'] for c in cadastro.values()}
    vistos, chaves = Counter(), set()
    comissoes, divergencias, pendencias = {}, [], []
    parcelas = Counter()
    validas = bloqueadas = sem_spread = 0
    for op in relatorio['operacoes']:
        if not op['data_contratacao'].startswith(competencia + '-'):
            raise ValueError(f"Operação {op['num_operacao']} fora da competência")
        ref, arquivo, spread = op['num_operacao'], op['arquivo_origem'], op['spread_brl']
        vistos[ref] += 1
        tipo = motivo = None
        if vistos[ref] > 1:
            ref = f'{ref}#{vistos[ref]}'
            tipo, motivo = 'OPERACAO_REPETIDA', 'Ocorrência excedente; solicitar correção do relatório à Ponte.'
        elif op['cnpj'] not in por_cnpj:
            tipo, motivo = 'CADASTRO_NAO_RESOLVIDO', 'CNPJ ausente da planilha de taxas.'
        elif spread < 0:
            tipo, motivo = 'CONTESTACAO', 'Trava de 2 horas excedida; contestar dentro do prazo de 5 dias úteis do e-mail.'
        elif op['status_compliance'] == 'APROVADO C/ RESSALVA' and not cfg['aprovado_com_ressalva_entra']:
            tipo, motivo = 'OPERACAO_COM_RESSALVA', 'Operação com ressalva bloqueada por configuração.'
        if tipo:
            pendencias.append(_pendencia(tipo, arquivo, ref, spread, motivo + ' Base: Spread R$ assinado.'))
            parcelas[tipo] += spread
            bloqueadas += 1
            continue
        chave = (op['cnpj'], op['valor_me'], op['moeda'], op['data_contratacao'])
        if chave in chaves:
            pendencias.append(_pendencia('OPERACAO_POSSIVEL_DUPLICIDADE', arquivo, ref, spread,
                                         'Mesmos CNPJ, valor, moeda e data; sinalização sem excluir comissão.'))
        chaves.add(chave)
        candidatos = por_cnpj[op['cnpj']]
        if any('spread_remessa_pct' not in c for c in candidatos):
            raise ValueError('Integração de A pendente: ler_taxas deve fornecer spread_remessa_pct')
        vigentes = [c for c in candidatos if (not c['vigencia_inicio'] or c['vigencia_inicio'] <= op['data_contratacao'])
                    and (not c['vigencia_fim'] or c['vigencia_fim'] >= op['data_contratacao'])]
        spreads = {c['spread_remessa_pct'] for c in vigentes or candidatos}
        if len(spreads) != 1:
            raise ValueError(f"Spread contratado ambíguo: {op['cnpj']}")
        contratada = next(iter(spreads))
        com = comissoes.setdefault(op['cnpj'], dict(cnpj=op['cnpj'], lojista=nomes.get(op['cnpj'], candidatos[0]['lojista']),
                    linha_negocio='REMESSA', comissao_brl=Decimal(0), origens=[], contratos_utilizados=[]))
        valor = q2(spread * participacao)
        com['comissao_brl'] += valor
        com['origens'].append(Origem(arquivo, ref, valor))
        validas += 1
        if contratada is None:
            sem_spread += 1
        elif abs(op['spread_pct'] - contratada) > tolerancia:
            diferenca = q2(spread - op['valor_me'] * op['ptax'] * contratada / 100)
            divergencias.append(dict(cnpj=op['cnpj'], linha_negocio='REMESSA', ref_origem=ref,
                    taxa_contratada_pct=contratada, taxa_aplicada_pct=op['spread_pct'], diferenca_brl=diferenca,
                    origens=[Origem(arquivo, ref, diferenca)]))
    total = sum((o['spread_brl'] for o in relatorio['operacoes']), Decimal(0))
    rodape = relatorio['rodape']
    if rodape['total_operacoes'] != len(relatorio['operacoes']) or rodape['spread_total_brl'] != total:
        pendencias.append(_pendencia('RODAPE_DIVERGENTE', relatorio['arquivo_origem'], 'Operações!rodape',
                         total - rodape['spread_total_brl'], 'Contagem ou soma das linhas difere do rodapé.'))
    for c in comissoes.values():
        c['origens'].sort(key=lambda o: o.ref)
    reconciliacao = dict(rodape_spread_total_brl=rodape['spread_total_brl'], linhas_spread_total_brl=total,
                        repetida_brl=parcelas['OPERACAO_REPETIDA'], negativos_brl=parcelas['CONTESTACAO'],
                        outros_bloqueados_brl=sum((v for k, v in parcelas.items() if k not in ('OPERACAO_REPETIDA', 'CONTESTACAO')), Decimal(0)),
                        base_comissao_brl=total - sum(parcelas.values(), Decimal(0)))
    return dict(comissoes=sorted(comissoes.values(), key=lambda c: c['cnpj']), divergencias=divergencias,
                pendencias=pendencias, resumo=dict(linhas_relatorio=len(relatorio['operacoes']), operacoes_distintas=len(vistos),
                validas=validas, bloqueadas=bloqueadas, sem_spread_contratado=sem_spread, reconciliacao=reconciliacao))
