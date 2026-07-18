"""Enumeraciones del dominio."""

from enum import StrEnum


class TipoFuente(StrEnum):
    """Fuentes externas reconocidas por el sistema."""

    MERCADO_LIBRE = "MERCADO_LIBRE"
    MERCADO_PAGO = "MERCADO_PAGO"
    DESCONOCIDA = "DESCONOCIDA"


class SeveridadValidacion(StrEnum):
    """Niveles de severidad para problemas de validación."""

    ERROR = "ERROR"
    ADVERTENCIA = "ADVERTENCIA"
    INFORMACION = "INFORMACION"
