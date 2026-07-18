from decimal import Decimal

from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.reconciliation.rules import clasificar_diferencia, elegir_estado_por_prioridad


def test_prioridad_centralizada_y_clasificacion():
    assert clasificar_diferencia(Decimal("0"), Decimal("0.01")) == EstadoConciliacion.CONCILIADA
    assert clasificar_diferencia(Decimal("0.01"), Decimal("0.01")) == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR
    assert elegir_estado_por_prioridad({EstadoConciliacion.CONCILIADA, EstadoConciliacion.DEVUELTA, EstadoConciliacion.EN_RECLAMO}) == EstadoConciliacion.EN_RECLAMO
