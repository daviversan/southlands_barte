from decimal import Decimal

import pytest

from src.core.normalize import brl, cnpj, data, pct, q2


class TestCnpj:
    def test_pontuado_e_so_digitos_dao_o_mesmo(self):
        assert cnpj("75.374.179/0001-46") == cnpj("75374179000146") == "75374179000146"

    def test_13_digitos_ganha_zero_a_esquerda(self):
        assert cnpj("5374179000146") == "05374179000146"

    def test_numero_do_excel_perde_zero(self):
        assert cnpj(5374179000146) == "05374179000146"
        assert cnpj(5374179000146.0) == "05374179000146"

    def test_vazio(self):
        assert cnpj(None) is None and cnpj("") is None and cnpj(float("nan")) is None

    def test_invalido(self):
        with pytest.raises(ValueError):
            cnpj("123456789012345")
        with pytest.raises(ValueError):
            cnpj("abc")


class TestBrl:
    @pytest.mark.parametrize("entrada,esperado", [
        ("1.234,56", "1234.56"), ("608,88", "608.88"), ("-2193,16", "-2193.16"),
        ("612.334,81", "612334.81"), ("78073.59", "78073.59"), ("R$ 10,00", "10.00"),
        (7350, "7350"), (0.1, "0.1"),
    ])
    def test_formatos(self, entrada, esperado):
        assert brl(entrada) == Decimal(esperado)

    def test_vazio(self):
        assert brl("") is None and brl(None) is None

    def test_invalido(self):
        with pytest.raises(ValueError):
            brl("abc")


class TestPct:
    def test_texto_e_fracao_dao_o_mesmo(self):
        assert pct("2,59%") == pct(0.0259) == pct("0.0259") == Decimal("2.59")

    def test_orbe_ja_vem_em_pontos(self):
        assert pct("2,69", fracao=False) == Decimal("2.69")

    def test_fracao_sem_ruido_de_float(self):
        assert pct(0.0149) == Decimal("1.49")
        assert pct(0.015) == Decimal("1.5")

    def test_vazio(self):
        assert pct(None) is None and pct("") is None


class TestData:
    def test_ptbr(self):
        assert data("01/09/2026") == "2026-09-01"

    def test_serial_excel(self):
        assert data(46266) == "2026-09-01"
        assert data(46266.0) == "2026-09-01"
        assert data("46266") == "2026-09-01"

    def test_iso_e_date(self):
        from datetime import date, datetime
        assert data("2026-09-01") == "2026-09-01"
        assert data(date(2026, 9, 1)) == data(datetime(2026, 9, 1, 10)) == "2026-09-01"

    def test_vazio_e_invalido(self):
        assert data("") is None
        with pytest.raises(ValueError):
            data("32/13/2026")
        with pytest.raises(ValueError):
            data("setembro")


class TestArredondamento:
    def test_meio_arredonda_para_cima_nao_para_o_par(self):
        # round(0.125, 2) == 0.12 (par); a Tarvo arredonda normalmente
        assert q2(Decimal("0.125")) == Decimal("0.13")
        assert q2(Decimal("0.135")) == Decimal("0.14")
        assert q2(Decimal("2.675")) == Decimal("2.68")

    def test_nao_trunca(self):
        assert q2(Decimal("16.3789")) == Decimal("16.38")  # a Orbe trunca (16,37); a Tarvo não

    def test_negativo_afasta_do_zero(self):
        assert q2(Decimal("-0.125")) == Decimal("-0.13")
