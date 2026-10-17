"""Leitores de CSV bancário e OFX SGML; referências da fonte preservadas."""
import csv
from datetime import datetime
from pathlib import Path
import re
from src.core.normalize import brl, data
from src.core.contratos import LancamentoBancario


def ler_aurora(caminho: Path, regras: dict) -> list[LancamentoBancario]:
    caminho = Path(caminho)
    linhas = list(csv.reader(caminho.read_text(encoding='utf-8-sig').splitlines(), delimiter=';'))
    cab = next((i for i, r in enumerate(linhas) if r[:2] == ['Data', 'Lançamento']), None)
    if cab is None:
        raise ValueError('Cabeçalho Aurora ausente')
    resultado = []
    for numero, r in enumerate(linhas[cab + 1:], cab + 2):
        if len(r) < 4 or r[1].strip().upper() in ('SALDO ANTERIOR', 'SALDO FINAL'):
            continue
        try:
            dia = data(r[0])
        except ValueError:
            continue
        if dia is None:
            continue
        valor = brl(r[3])
        if valor is None:
            raise ValueError(f'Aurora L{numero}: valor ausente')
        resultado.append(dict(banco='AURORA', ref_origem=f"L{numero + regras['bancos'].get('aurora_ref_offset', 0)}",
                              data=dia, descricao=r[1], valor=valor, arquivo_origem=caminho.name))
    return resultado


def ler_meridiano(caminho: Path) -> list[LancamentoBancario]:
    caminho = Path(caminho)
    texto = caminho.read_text(encoding='cp1252')
    resultado = []
    for bloco in re.findall(r'<STMTTRN>(.*?)</STMTTRN>', texto, re.S | re.I):
        def tag(nome):
            match = re.search(fr'<{nome}>([^<\r\n]*)', bloco, re.I)
            if not match or not match[1].strip():
                raise ValueError(f'Meridiano: campo {nome} ausente')
            return match[1].strip()
        resultado.append(dict(banco='MERIDIANO', ref_origem=tag('FITID'),
                              data=datetime.strptime(tag('DTPOSTED')[:8], '%Y%m%d').date().isoformat(),
                              descricao=tag('MEMO'), valor=brl(tag('TRNAMT')), arquivo_origem=caminho.name))
    if not resultado:
        raise ValueError('Meridiano sem lançamentos STMTTRN')
    return resultado
