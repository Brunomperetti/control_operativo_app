from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from kiki_control.domain.account_statement import MovimientoEstadoCuentaMp, ResumenEstadoCuentaMp
from kiki_control.domain.temporal import (
    EstadoReconocimiento, TipoSeleccionPeriodo, filtrar_estado_cuenta,
    reconocer_cuatro_fuentes, resolver_periodo, universos_settlement,
)


@dataclass(frozen=True)
class Item:
    id_venta: str | None = None
    id_orden: str | None = None
    id_operacion_mercado_pago: str | None = None
    id_paquete: str | None = None
    reference_id: str | None = None
    fecha_venta: datetime | None = None
    fecha_hora_venta: datetime | None = None
    fecha_origen_local: datetime | None = None
    fecha_liquidacion_local: datetime | None = None


def movimiento(fila, fecha, importe, parcial, ref):
    return MovimientoEstadoCuentaMp(fila, datetime.combine(fecha, datetime.min.time()), "Pago", ref,
                                     Decimal(importe), Decimal(parcial), "hash", "sheet")


def resumen():
    ms = (movimiento(5, date(2026, 7, 20), "10", "110", "A"),
          movimiento(6, date(2026, 7, 21), "-4", "106", "B"))
    return ResumenEstadoCuentaMp(Decimal("100"), Decimal("10"), Decimal("-4"), Decimal("106"), ms,
                                 ms[0].fecha_liberacion, ms[-1].fecha_liberacion)


@pytest.mark.parametrize(("tipo", "esperado"), [
    (TipoSeleccionPeriodo.AYER, (date(2026, 7, 28), date(2026, 7, 28))),
    (TipoSeleccionPeriodo.ULTIMOS_3_DIAS, (date(2026, 7, 26), date(2026, 7, 28))),
    (TipoSeleccionPeriodo.ULTIMOS_7_DIAS, (date(2026, 7, 22), date(2026, 7, 28))),
])
def test_periodos_rapidos_respetan_fecha_local(tipo, esperado):
    periodo = resolver_periodo(tipo, "America/Argentina/Cordoba", ahora=datetime(2026, 7, 29, 15, tzinfo=UTC))
    assert (periodo.fecha_desde, periodo.fecha_hasta) == esperado


def test_todo_disponible_y_personalizado():
    disponible = (date(2026, 7, 18), date(2026, 7, 21))
    assert resolver_periodo(TipoSeleccionPeriodo.TODO_DISPONIBLE, "UTC", disponible).fecha_desde == disponible[0]
    with pytest.raises(ValueError, match="posterior"):
        resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=disponible[1], hasta=disponible[0])


def test_reconocimiento_dinamico_y_capacidades_separadas():
    ml = (Item(id_venta="1", fecha_venta=datetime(2026, 7, 18)), Item(id_venta="2", fecha_venta=datetime(2026, 7, 20)))
    ec = (Item(id_orden="1", fecha_hora_venta=datetime(2026, 7, 19)),)
    settlement = (Item(id_operacion_mercado_pago="A", fecha_origen_local=datetime(2026, 3, 30), fecha_liquidacion_local=datetime(2026, 8, 24)),)
    rec = reconocer_cuatro_fuentes(ml, ec, settlement, resumen())
    assert rec.periodo_b1_disponible == (date(2026, 7, 19), date(2026, 7, 19))
    assert rec.periodo_b2_b3_disponible == (date(2026, 7, 20), date(2026, 7, 21))
    assert rec.estado_b1 == EstadoReconocimiento.PENDIENTE_DE_VALIDACION_POR_IDS
    assert len(rec.filas_tabla()) == 5


def test_archivo_sin_fechas_e_incompatibilidad():
    rec = reconocer_cuatro_fuentes((Item(id_venta="1", fecha_venta=datetime(2026, 1, 1)),),
                                   (Item(id_orden="2", fecha_hora_venta=datetime(2026, 2, 1)),),
                                   (Item(id_operacion_mercado_pago="A"),), resumen())
    assert rec.estado_b1 == EstadoReconocimiento.PERIODOS_INCOMPATIBLES
    assert rec.coberturas[2].estado == EstadoReconocimiento.ARCHIVO_SIN_FECHAS_VALIDAS


def test_b1_solo_vinculos_y_b23_settlement_completo():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    ml = (Item(id_venta="ORDER-1", fecha_venta=datetime(2026, 7, 20)),)
    relacionados = Item(id_orden="ORDER-1", id_operacion_mercado_pago="MP-1", fecha_liquidacion_local=datetime(2026, 8, 20))
    historico = Item(id_orden="OLD", id_operacion_mercado_pago="MP-OLD", fecha_origen_local=datetime(2026, 3, 1))
    b1, b23 = universos_settlement(ml, (), (relacionados, historico), p)
    assert b1 == (relacionados,)
    assert b23 == (relacionados, historico)


def test_filtrado_statement_deriva_saldos_sin_inventarlos():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 21), hasta=date(2026, 7, 21))
    filtrado = filtrar_estado_cuenta(resumen(), p)
    assert filtrado is not None
    assert (filtrado.saldo_inicial, filtrado.saldo_final_informado, filtrado.variacion_neta) == (Decimal("110"), Decimal("106"), Decimal("-4"))
