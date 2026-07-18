from decimal import Decimal

import pytest

from kiki_control.normalization.locale_ar import ErrorNormalizacion, parsear_importe, parsear_porcentaje


def test_normaliza_importes_locales():
    assert parsear_importe("47.239", campo="monto") == Decimal("47239")
    assert parsear_importe("7.478,66", campo="monto") == Decimal("7478.66")
    assert parsear_importe(" 0,00 ", campo="monto") == Decimal("0.00")
    assert parsear_importe("193.971", campo="monto") == Decimal("193971")
    assert parsear_importe("", campo="opcional", opcional=True) is None


def test_rechaza_importe_invalido():
    with pytest.raises(ErrorNormalizacion):
        parsear_importe("12,34,56", campo="monto")


def test_normaliza_porcentajes_con_punto_decimal():
    assert parsear_porcentaje("21%", campo="iva") == Decimal("0.21")
    assert parsear_porcentaje("22.7%", campo="comision") == Decimal("0.227")
    assert parsear_porcentaje("0.00%", campo="cero") == Decimal("0.00")
    assert parsear_porcentaje("", campo="opcional", opcional=True) is None
