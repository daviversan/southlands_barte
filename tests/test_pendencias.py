from decimal import Decimal

import pytest

from src.core.saida import Origem, SaidaError
from src.regras.pendencias import validar_pendencia


def pendencia():
    return dict(tipo="CONTRATO_AUSENTE", ref_origem="TX2", valor_brl=Decimal("-100"),
                motivo="Bruto assinado; comissão desconhecida", quem_decide="Comercial",
                origens=[Origem("01_orbe.csv", "TX2", Decimal("-100"))])


def test_valida_bruto_assinado_e_evidencia_cadastral():
    validar_pendencia(pendencia())
    validar_pendencia({**pendencia(), "valor_brl": Decimal(0),
                      "origens": [Origem("02_taxas.xlsx", "Taxas vigentes!L6", Decimal(0))]})


@pytest.mark.parametrize("campo,valor", [
    ("tipo", " "), ("ref_origem", ""), ("motivo", None), ("quem_decide", "Outro"),
    ("valor_brl", 100.0), ("valor_brl", Decimal("NaN")), ("origens", []),
    ("origens", [Origem("C:/entrada.csv", "TX2", Decimal(-100))]),
    ("origens", [Origem("../entrada.csv", "TX2", Decimal(-100))]),
    ("origens", [Origem("01_orbe.csv", "TX2", Decimal(-99))]),
])
def test_rejeita_pendencia_invalida(campo, valor):
    with pytest.raises(SaidaError):
        validar_pendencia({**pendencia(), campo: valor})
