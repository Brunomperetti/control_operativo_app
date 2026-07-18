from datetime import UTC
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from kiki_control.normalization.values import ErrorNormalizacion, normalizar_decimal, normalizar_identificador, normalizar_timestamp


def test_normaliza_importes_xlsx_seguros():
    assert normalizar_decimal(47239, campo="monto") == Decimal("47239")
    assert normalizar_decimal(7478.66, campo="monto") == Decimal("7478.66")
    assert normalizar_decimal("7478.66", campo="monto") == Decimal("7478.66")
    assert normalizar_decimal(0, campo="monto") == Decimal("0")
    assert normalizar_decimal(-3199.90, campo="monto") == Decimal("-3199.9")
    assert normalizar_decimal("", campo="monto", opcional=True) is None


def test_no_convierte_importe_invalido_en_cero():
    with pytest.raises(ErrorNormalizacion):
        normalizar_decimal("importe inválido", campo="monto")


def test_normaliza_identificadores_sin_notacion_cientifica():
    assert normalizar_identificador("1234567890123456", campo="id") == "1234567890123456"
    assert normalizar_identificador(1234567890123456, campo="id") == "1234567890123456"
    assert normalizar_identificador("123.0", campo="id") == "123"
    assert normalizar_identificador("", campo="id", opcional=True) is None
    with pytest.raises(ErrorNormalizacion):
        normalizar_identificador("123.45", campo="id")


def test_timestamp_preserva_original_y_convierte_zonas():
    original, utc, local = normalizar_timestamp("2026-07-14T23:55:13.000-04:00", campo="fecha", zona=ZoneInfo("America/Argentina/Cordoba"))
    assert original == "2026-07-14T23:55:13.000-04:00"
    assert utc is not None and utc.isoformat() == "2026-07-15T03:55:13+00:00"
    assert utc.tzinfo == UTC
    assert local is not None and local.isoformat() == "2026-07-15T00:55:13-03:00"
    with pytest.raises(ErrorNormalizacion):
        normalizar_timestamp("2026-07-14T23:55:13", campo="fecha", zona=ZoneInfo("UTC"))
