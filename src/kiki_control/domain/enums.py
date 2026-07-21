"""Enumeraciones del dominio."""

from enum import StrEnum


class TipoFuente(StrEnum):
    """Fuentes externas reconocidas por el sistema."""

    MERCADO_LIBRE_VENTAS = "MERCADO_LIBRE_VENTAS"
    ECCOMAPP_RENTABILIDAD = "ECCOMAPP_RENTABILIDAD"
    # Alias temporal de compatibilidad: el CSV antes llamado Mercado Libre
    # corresponde al reporte de rentabilidad y costos de Eccomapp.
    MERCADO_LIBRE = "ECCOMAPP_RENTABILIDAD"
    MERCADO_PAGO = "MERCADO_PAGO"
    DESCONOCIDA = "DESCONOCIDA"


class SeveridadValidacion(StrEnum):
    """Niveles de severidad para problemas de validación."""

    ERROR = "ERROR"
    ADVERTENCIA = "ADVERTENCIA"
    INFORMACION = "INFORMACION"
