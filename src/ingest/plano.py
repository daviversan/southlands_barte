"""Plano de contas, incluindo contas sintéticas para auditoria."""
import csv
from pathlib import Path
from src.core.contratos import ContaContabil


def ler_plano(caminho: Path) -> list[ContaContabil]:
    with Path(caminho).open(encoding='iso-8859-1', newline='') as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=';')
        if not {'COD_CONTA', 'DESCRICAO', 'ACEITA_LANCTO'} <= set(leitor.fieldnames or []):
            raise ValueError('Cabeçalho do plano de contas inválido')
        contas = [dict(codigo=r['COD_CONTA'], descricao=r['DESCRICAO'],
                       aceita_lancto=r['ACEITA_LANCTO'].strip().upper() == 'S') for r in leitor]
    if len({c['codigo'] for c in contas}) != len(contas):
        raise ValueError('Código contábil duplicado')
    return contas
