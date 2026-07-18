"""Parseo local de importes y porcentajes informados en Argentina."""

from decimal import Decimal, InvalidOperation
import re

_MONTO_RE = re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")
_PORCENTAJE_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?%$")


class ErrorNormalizacion(ValueError):
    """Error claro de normalización de valores externos."""


def parsear_importe(valor: str, *, campo: str, opcional: bool = False) -> Decimal | None:
    """Convierte importes como '7.478,66' a Decimal, sin usar float."""

    texto = valor.strip()
    if texto == "":
        if opcional:
            return None
        raise ErrorNormalizacion(f"El campo {campo} está vacío.")
    if not _MONTO_RE.fullmatch(texto):
        raise ErrorNormalizacion(f"El campo {campo} tiene un importe inválido: {valor!r}.")
    try:
        return Decimal(texto.replace(".", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ErrorNormalizacion(f"El campo {campo} tiene un importe inválido: {valor!r}.") from exc


def parsear_porcentaje(valor: str, *, campo: str, opcional: bool = False) -> Decimal | None:
    """Convierte porcentajes como '21%' a Decimal('0.21')."""

    texto = valor.strip()
    if texto == "":
        if opcional:
            return None
        raise ErrorNormalizacion(f"El campo {campo} está vacío.")
    if not _PORCENTAJE_RE.fullmatch(texto):
        raise ErrorNormalizacion(f"El campo {campo} tiene un porcentaje inválido: {valor!r}.")
    try:
        return Decimal(texto[:-1]) / Decimal("100")
    except InvalidOperation as exc:
        raise ErrorNormalizacion(f"El campo {campo} tiene un porcentaje inválido: {valor!r}.") from exc
