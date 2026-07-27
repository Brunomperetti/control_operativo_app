"""Normalización segura de valores externos."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

class ErrorNormalizacion(ValueError):
    """Error claro de normalización de valores externos."""


def es_vacio(valor: object) -> bool:
    return valor is None or (isinstance(valor, str) and valor.strip() == "")


def normalizar_identificador(valor: object, *, campo: str, opcional: bool = False) -> str | None:
    if es_vacio(valor):
        if opcional:
            return None
        raise ErrorNormalizacion(f"El campo {campo} está vacío.")
    if isinstance(valor, bool):
        raise ErrorNormalizacion(f"El campo {campo} tiene un identificador inválido.")
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, Decimal):
        if valor == valor.to_integral_value():
            return format(valor.quantize(Decimal(1)), "f")
        raise ErrorNormalizacion(f"El campo {campo} no admite identificadores fraccionarios.")
    if isinstance(valor, float):
        dec = Decimal(str(valor))
        if dec == dec.to_integral_value():
            return format(dec.quantize(Decimal(1)), "f")
        raise ErrorNormalizacion(f"El campo {campo} no admite identificadores fraccionarios.")
    texto = str(valor).strip()
    try:
        dec = Decimal(texto)
    except InvalidOperation:
        return texto
    if "." in texto and dec == dec.to_integral_value():
        return format(dec.quantize(Decimal(1)), "f")
    if dec == dec.to_integral_value() and ("E" in texto.upper()):
        return format(dec.quantize(Decimal(1)), "f")
    if dec != dec.to_integral_value():
        raise ErrorNormalizacion(f"El campo {campo} no admite identificadores fraccionarios.")
    return texto


def normalizar_decimal(valor: object, *, campo: str, opcional: bool = False) -> Decimal | None:
    if es_vacio(valor):
        if opcional:
            return None
        raise ErrorNormalizacion(f"El campo {campo} está vacío.")
    try:
        if isinstance(valor, Decimal):
            return valor
        if isinstance(valor, int) and not isinstance(valor, bool):
            return Decimal(valor)
        if isinstance(valor, float):
            return Decimal(str(valor))
        texto = str(valor).strip()
        return Decimal(texto)
    except (InvalidOperation, ValueError) as exc:
        raise ErrorNormalizacion(f"El campo {campo} tiene un importe inválido: {valor!r}.") from exc


def normalizar_timestamp(valor: object, *, campo: str, zona: ZoneInfo, opcional: bool = False) -> tuple[str | None, datetime | None, datetime | None]:
    if es_vacio(valor):
        if opcional:
            return None, None, None
        raise ErrorNormalizacion(f"El campo {campo} está vacío.")
    original = valor.isoformat() if isinstance(valor, datetime) else str(valor).strip()
    try:
        dt = datetime.fromisoformat(original.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ErrorNormalizacion(f"El campo {campo} tiene un timestamp inválido.") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ErrorNormalizacion(f"El campo {campo} debe incluir offset de zona horaria.")
    utc = dt.astimezone(UTC)
    return original, utc, utc.astimezone(zona)
