"""Relatório XLSX anexado ao e-mail, sem arquivos intermediários."""
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
import re

import openpyxl
from src.core.normalize import brl, cnpj, data, pct
from src.core.contratos import RelatorioPonte


def ler_ponte(caminho: Path) -> RelatorioPonte:
    caminho = Path(caminho)
    mensagem = BytesParser(policy=policy.default).parsebytes(caminho.read_bytes())
    anexos = [p for p in mensagem.walk() if (p.get_filename() or '').lower().endswith('.xlsx')]
    if len(anexos) != 1:
        raise ValueError('Esperado exatamente um anexo XLSX da Ponte')
    wb = openpyxl.load_workbook(BytesIO(anexos[0].get_payload(decode=True)), data_only=True)
    try:
        if 'Operações' not in wb.sheetnames:
            raise ValueError('Aba Operações ausente')
        linhas = list(wb['Operações'].values)
    finally:
        wb.close()
    cab = next((i for i, r in enumerate(linhas) if 'Nº Operação' in r), None)
    if cab is None:
        raise ValueError('Cabeçalho Ponte ausente')
    col = {v: i for i, v in enumerate(linhas[cab]) if v}
    operacoes, rodape, competencia = [], {}, None
    for numero, r in enumerate(linhas, 1):
        texto = str(r[0] or '')
        match = re.search(r'Competência:\s*(\d{2})/(\d{4})', texto)
        if match:
            competencia = f'{match[2]}-{match[1]}'
        if texto == 'Total de operações:':
            rodape['total_operacoes'] = int(r[1])
        elif texto == 'Spread total R$:':
            rodape['spread_total_brl'] = brl(r[1])
        elif numero > cab + 1 and texto and texto not in ('Total de operações:', 'Spread total R$:'):
            def v(nome):
                return r[col[nome]]
            op = dict(num_operacao=str(v('Nº Operação')), linha=numero,
                      data_contratacao=data(v('Data Contratação')), data_liquidacao=data(v('Data Liquidação')),
                      cnpj=cnpj(v('CNPJ Cliente')), cliente_origem=str(v('Cliente')),
                      moeda=str(v('Moeda')), status_compliance=str(v('Status Compliance')),
                      observacao=v('Observação'), arquivo_origem=caminho.name, ref_origem=str(v('Nº Operação')))
            for campo, coluna in {'valor_me': 'Valor ME', 'taxa_cliente': 'Taxa Cliente', 'ptax': 'PTAX Ref.',
                                  'valor_brl': 'Valor R$', 'spread_brl': 'Spread R$',
                                  'spread_estimado_d1_brl': 'Spread Estimado R$ (D-1)', 'iof_brl': 'IOF R$'}.items():
                op[campo] = brl(v(coluna))
            op['spread_pct'] = pct(v('Spread %'))
            if any(op[k] is None for k in ('cnpj', 'data_contratacao', 'data_liquidacao', 'spread_brl', 'valor_me', 'ptax', 'spread_pct')):
                raise ValueError(f'Operação incompleta na linha {numero}')
            operacoes.append(op)
    if set(rodape) != {'total_operacoes', 'spread_total_brl'}:
        raise ValueError('Rodapé Ponte ausente ou incompleto')
    return dict(operacoes=operacoes, rodape=rodape, competencia=competencia, arquivo_origem=caminho.name)
