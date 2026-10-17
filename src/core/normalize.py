"""Normalização de tipos vindos das fontes (CNPJ, dinheiro, percentual, data).

Convenções de saída:
- dinheiro e percentual são `Decimal` (nunca float);
- percentual é sempre em **pontos percentuais** (2,59 = 2,59%): a Orbe já vem assim,
  a planilha de taxas vem em fração e é convertida aqui antes de qualquer comparação;
- data é `AAAA-MM-DD` (str).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")
# Excel (sistema 1900): serial 1 = 1900-01-01, com o bug do 29/02/1900 -> época efetiva 1899-12-30.
_EPOCA_EXCEL = date(1899, 12, 30)


def _vazio(x) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and x != x:  # NaN
        return True
    return isinstance(x, str) and not x.strip()


def q2(valor: Decimal) -> Decimal:
    """Arredonda a 2 casas com ROUND_HALF_UP (o `round()` do Python arredonda para o par)."""
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def cnpj(x) -> str | None:
    """Só dígitos, 14 posições. Aceita pontuado, texto, int e float (Excel perde o zero à esquerda).

    Devolve None para vazio. Levanta ValueError se sobrar mais de 14 dígitos ou nenhum.
    """
    if _vazio(x):
        return None
    if isinstance(x, float):
        if x != int(x):
            raise ValueError(f"CNPJ inválido: {x!r}")
        x = int(x)
    digitos = re.sub(r"\D", "", str(x))
    if not digitos or len(digitos) > 14:
        raise ValueError(f"CNPJ inválido: {x!r}")
    return digitos.zfill(14)


def _decimal_ptbr(texto: str) -> Decimal:
    t = texto.strip().replace("R$", "").replace(" ", "")
    if "," in t:  # pt-BR: ponto é milhar, vírgula é decimal
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        raise ValueError(f"número inválido: {texto!r}") from None


def brl(x) -> Decimal | None:
    """Dinheiro: `"1.234,56"` -> Decimal('1234.56'); aceita negativo, int, float e Decimal.

    Texto sem vírgula é lido como decimal com ponto (`"1234.56"`). Vazio -> None.
    """
    if _vazio(x):
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, float)):
        return Decimal(str(x))
    return _decimal_ptbr(str(x))


def pct(x, fracao: bool = True) -> Decimal | None:
    """Percentual em **pontos percentuais**.

    - texto com `%` (`'2,59%'`) -> sempre pontos: 2.59;
    - número/texto sem `%`: se `fracao=True` (planilha: 0.0259) multiplica por 100;
      se `fracao=False` (Orbe: `'2,69'`) já está em pontos.
    """
    if _vazio(x):
        return None
    if isinstance(x, str) and "%" in x:
        return _decimal_ptbr(x.replace("%", ""))
    valor = brl(x)
    return valor * 100 if fracao else valor


def data(x) -> str | None:
    """Data -> `AAAA-MM-DD`. Aceita `dd/mm/aaaa`, ISO, date/datetime e serial Excel (int/float/texto)."""
    if _vazio(x):
        return None
    if isinstance(x, datetime):
        return x.date().isoformat()
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, (int, float)):
        return (_EPOCA_EXCEL + timedelta(days=int(x))).isoformat()
    t = str(x).strip()
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return (_EPOCA_EXCEL + timedelta(days=int(float(t)))).isoformat()
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", t):
        return datetime.strptime(t, "%d/%m/%Y").date().isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return datetime.strptime(t, "%Y-%m-%d").date().isoformat()
    raise ValueError(f"data inválida: {x!r}")
