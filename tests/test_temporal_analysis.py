from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from kiki_control.domain.account_statement import MovimientoEstadoCuentaMp, ResumenEstadoCuentaMp
from kiki_control.domain.temporal import (
    EstadoBloqueB1, EstadoBloqueB2B3, EstadoReconocimiento, TipoSeleccionPeriodo,
    calcular_disponibilidad_bloques, filtrar_estado_cuenta,
    construir_universos_settlement, reconocer_cuatro_fuentes, resolver_periodo, universos_settlement,
)
from kiki_control.ui.session_cycle import construir_firma_procesamiento_cuatro_fuentes


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


def test_comparable_y_diagnostico_excluyen_historico_ajeno():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    ml = (Item(id_venta="ORDER-1", fecha_venta=datetime(2026, 7, 20)),)
    relacionados = Item(id_orden="ORDER-1", id_operacion_mercado_pago="MP-1", fecha_liquidacion_local=datetime(2026, 8, 20))
    historico = Item(id_orden="OLD", id_operacion_mercado_pago="MP-OLD", fecha_origen_local=datetime(2026, 3, 1))
    ec = (Item(id_orden="ORDER-1", fecha_hora_venta=datetime(2026, 7, 20)),)
    b1, b23 = universos_settlement(ml, ec, (relacionados, historico), p)
    assert b1 == (relacionados,)
    assert b23 == (relacionados,)


def test_diagnostico_expande_relaciones_y_no_equivale_al_settlement_ampliado():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    dentro = Item(id_orden="ORD-D", id_operacion_mercado_pago="MP-D", fecha_origen_local=datetime(2026, 7, 20), fecha_liquidacion_local=datetime(2026, 8, 20))
    posterior = Item(id_orden=None, id_operacion_mercado_pago="MP-D", fecha_origen_local=datetime(2026, 8, 1), fecha_liquidacion_local=datetime(2026, 9, 1))
    anterior = Item(id_orden="ORD-D", id_operacion_mercado_pago="MP-ANT", fecha_origen_local=datetime(2026, 7, 1))
    ajeno = Item(id_orden="OLD", id_operacion_mercado_pago="MP-OLD", fecha_origen_local=datetime(2026, 3, 1))
    universos = construir_universos_settlement((), (), (dentro, posterior, anterior, ajeno), p)
    assert universos.settlement_comparable_b1 == ()
    assert universos.settlement_diagnostico_periodo == (dentro, posterior, anterior)
    assert universos.settlement_diagnostico_periodo != (dentro, posterior, anterior, ajeno)
    assert dict(universos.metadatos)["Filas settlement_diagnostico_periodo"] == "3"


def test_b1_usa_grupo_canonico_y_expande_toda_la_operacion():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    venta = Item(id_venta="VENTA-DISTINTA-DE-MP", fecha_venta=datetime(2026, 7, 20))
    op = Item(id_orden="ORD-1", fecha_hora_venta=datetime(2026, 7, 19))
    resultado = SimpleNamespace(venta_principal_ml=venta, ventas_detalle_ml=(), id_grupo_canonico="PACK-1",
                                ids_orden=("ORD-1",), operaciones_eccomapp=(op,))
    reporte = SimpleNamespace(resultados=(resultado,))
    pago = Item(id_orden="ORD-1", id_operacion_mercado_pago="MP-99", fecha_liquidacion_local=datetime(2026, 8, 20))
    devolucion = Item(id_orden=None, id_operacion_mercado_pago="MP-99", fecha_liquidacion_local=datetime(2026, 9, 1))
    ajeno = Item(id_orden="OLD", id_operacion_mercado_pago="MP-OLD", fecha_origen_local=datetime(2026, 3, 1))
    b1, _ = universos_settlement((venta,), (op,), (pago, devolucion, ajeno), p, reporte)
    assert b1 == (pago, devolucion)


def test_filtrado_statement_deriva_saldos_sin_inventarlos():
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 21), hasta=date(2026, 7, 21))
    filtrado = filtrar_estado_cuenta(resumen(), p)
    assert filtrado is not None
    assert (filtrado.saldo_inicial, filtrado.saldo_final_informado, filtrado.variacion_neta) == (Decimal("110"), Decimal("106"), Decimal("-4"))


def test_recorte_parcial_sin_partial_balance_deja_saldo_desconocido():
    ms = (movimiento(5, date(2026, 7, 20), "10", "110", "A"),
          MovimientoEstadoCuentaMp(6, datetime(2026, 7, 21), "Pago", "B", Decimal("-4"), None, "hash", "sheet"))
    original = ResumenEstadoCuentaMp(Decimal("100"), Decimal("10"), Decimal("-4"), Decimal("106"), ms,
                                     ms[0].fecha_liberacion, ms[-1].fecha_liberacion)
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 21), hasta=date(2026, 7, 21))
    filtrado = filtrar_estado_cuenta(original, p)
    assert filtrado is not None
    assert filtrado.saldo_inicial is None
    assert filtrado.saldo_final_calculado is None
    assert filtrado.diferencia_control is None
    assert not filtrado.control_contable_verificable
    assert "composición de movimientos puede analizarse" in filtrado.motivo_control_no_disponible


def test_rango_completo_sin_partial_usa_saldo_inicial_informado():
    m = MovimientoEstadoCuentaMp(5, datetime(2026, 7, 20), "Pago", "A", Decimal("10"), None, "hash", "sheet")
    original = ResumenEstadoCuentaMp(Decimal("100"), Decimal("10"), Decimal("0"), Decimal("110"), (m,), m.fecha_liberacion, m.fecha_liberacion)
    p = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    filtrado = filtrar_estado_cuenta(original, p)
    assert filtrado is not None and filtrado.control_contable_verificable
    assert filtrado.saldo_inicial == Decimal("100") and filtrado.diferencia_control == Decimal("0")


def test_periodos_efectivos_independientes_y_fechas_sin_cobertura():
    solicitado = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 18), hasta=date(2026, 7, 20))
    disponibilidad = calcular_disponibilidad_bloques(
        solicitado, (date(2026, 7, 18), date(2026, 7, 20)), (date(2026, 7, 20), date(2026, 7, 20)))
    assert (disponibilidad.periodo_efectivo_b1.fecha_desde, disponibilidad.periodo_efectivo_b1.fecha_hasta) == (date(2026, 7, 18), date(2026, 7, 20))
    assert disponibilidad.periodo_efectivo_b2_b3.fecha_desde == date(2026, 7, 20)
    assert disponibilidad.fechas_sin_cobertura_b2_b3 == (date(2026, 7, 18), date(2026, 7, 19))


def test_firma_de_cuatro_fuentes_cambia_con_periodo_y_tipo():
    p1 = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 18), hasta=date(2026, 7, 20))
    p2 = resolver_periodo(TipoSeleccionPeriodo.PERSONALIZADO, "UTC", desde=date(2026, 7, 20), hasta=date(2026, 7, 20))
    f1 = construir_firma_procesamiento_cuatro_fuentes("1", "2", "3", "4", "UTC", Decimal("0.01"), p1)
    f2 = construir_firma_procesamiento_cuatro_fuentes("1", "2", "3", "4", "UTC", Decimal("0.01"), p2)
    assert f1 != f2
    assert set(EstadoBloqueB1) and set(EstadoBloqueB2B3)
