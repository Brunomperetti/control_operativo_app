"""Reglas puras y priorización de estados de conciliación."""

from decimal import Decimal

from kiki_control.domain.reconciliation import EstadoConciliacion

PRIORIDAD_ESTADOS: tuple[EstadoConciliacion, ...] = (
    EstadoConciliacion.DUPLICADA,
    EstadoConciliacion.EN_REVISION,
    EstadoConciliacion.EN_RECLAMO,
    EstadoConciliacion.DEVUELTA,
    EstadoConciliacion.MOVIMIENTO_DE_FONDOS,
    EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL,
    EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO,
    EstadoConciliacion.PENDIENTE_ACREDITACION,
    EstadoConciliacion.CONCILIADA_CON_DIFERENCIA,
    EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR,
    EstadoConciliacion.CONCILIADA,
)


def validar_tolerancia(tolerancia: Decimal) -> None:
    """Rechaza tolerancias negativas sin convertir importes a float."""

    if tolerancia < Decimal("0"):
        raise ValueError("La tolerancia de conciliación no puede ser negativa.")


def clasificar_diferencia(diferencia: Decimal, tolerancia: Decimal) -> EstadoConciliacion:
    """Clasifica la diferencia principal sin redondeos silenciosos."""

    if diferencia == Decimal("0"):
        return EstadoConciliacion.CONCILIADA
    if abs(diferencia) <= tolerancia:
        return EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR
    return EstadoConciliacion.CONCILIADA_CON_DIFERENCIA


def elegir_estado_por_prioridad(candidatos: set[EstadoConciliacion]) -> EstadoConciliacion:
    """Elige el estado más prioritario entre candidatos explícitos."""

    for estado in PRIORIDAD_ESTADOS:
        if estado in candidatos:
            return estado
    return EstadoConciliacion.EN_REVISION
