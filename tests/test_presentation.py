from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from kiki_control.domain.financial_movement import TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.reconciliation_view import ETIQUETAS_ESTADO, cobertura_archivos, detalle_presentacion, filas_presentacion, filtrar_filas, resultado_a_fila, resumen_kpis
from kiki_control.reconciliation import reconciliar
from tests.test_reconciliation_engine import mov, op


def test_formato_monetario_argentino():
    assert formato_pesos_argentino(Decimal("13026524.25")) == "$ 13.026.524,25"
    assert formato_pesos_argentino(Decimal("-3199.9")) == "-$ 3.199,90"
    assert formato_pesos_argentino(Decimal("0")) == "$ 0,00"
    assert formato_pesos_argentino(None) == "—"


def test_etiquetas_de_todos_los_estados():
    assert set(ETIQUETAS_ESTADO) == set(EstadoConciliacion)
    assert ETIQUETAS_ESTADO[EstadoConciliacion.CONCILIADA] == "Conciliada"
    assert ETIQUETAS_ESTADO[EstadoConciliacion.MOVIMIENTO_DE_FONDOS] == "Movimiento de fondos"


def test_conversion_a_fila_sin_campos_personales_y_diferencia_con_signo():
    resultado = reconciliar([op(neto="100")], [mov(monto="90")]).resultados[0]
    fila = resultado_a_fila(resultado)
    assert fila.id_orden == "1"
    assert fila.estado == "Con diferencia"
    assert fila.diferencia == "-$ 10,00"
    assert fila.diferencia_valor == Decimal("-10")
    campos = set(fila.__dict__)
    assert "nombre_pagador" not in campos
    assert "numero_identificacion" not in campos
    assert "tarjeta" not in campos
    assert "json_original" not in campos


def test_filtros_estado_busqueda_revision_y_pago_dividido():
    reporte = reconciliar(
        [op(id_orden="A", neto="100"), op(id_orden="B", neto="50"), op(id_orden="C", neto="20")],
        [mov(id_orden="A", monto="100"), mov(id_orden="B", monto="10", id_mp="b1"), mov(id_orden="B", monto="40", id_mp="b2"), mov(id_orden="X", monto="1", id_mp="x")],
    )
    filas = filas_presentacion(reporte.resultados)
    assert [f.id_orden for f in filtrar_filas(filas, {EstadoConciliacion.CONCILIADA.value})] == ["A", "B"]
    assert [f.id_orden for f in filtrar_filas(filas, busqueda_id="c")] == ["C"]
    assert [f.id_orden for f in filtrar_filas(filas, solo_revision=True)] == ["C", "X"]
    assert [f.id_orden for f in filtrar_filas(filas, solo_pago_dividido=True)] == ["B"]


def test_resumen_kpis_orden_determinista_sin_id_y_totales_decimal():
    reporte = reconciliar(
        [op(id_orden="B", neto="50", utilidad="5"), op(id_orden="A", neto="100", utilidad="10")],
        [mov(id_orden="A", monto="101"), mov(id_orden="B", monto="50", id_mp="b"), mov(id_orden=None, tipo=TipoOperacionFinanciera.PAYOUT, monto="-20", id_mp="p", fila=7)],
    )
    filas = filas_presentacion(reporte.resultados)
    assert [f.id_orden for f in filas] == ["A", "B", "movimiento_de_fondos-fila-7"]
    assert filas[-1].estado == "Movimiento de fondos"
    kpis = resumen_kpis(reporte)
    assert kpis["Operaciones comparables"] == 2
    assert kpis["Movimientos de fondos"] == 1
    assert kpis["Neto comercial de operaciones comparables"] == "$ 150,00"
    assert kpis["Neto aprobado de Mercado Pago de operaciones comparables"] == "$ 151,00"
    assert kpis["Diferencia de control — operaciones comparables"] == "$ 1,00"
    assert "Neto de pagos aprobados" not in kpis
    assert "Diferencia total de control" not in kpis
    assert "Sin contraparte" not in kpis
    assert kpis["Utilidad informada por Mercado Libre"] == "$ 15,00"


def test_detalle_presentacion_completo():
    resultado = reconciliar([op(neto="100")], [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11)]).resultados[0]
    detalle = detalle_presentacion(resultado)
    assert detalle["ID de orden"] == "1"
    assert detalle["Cantidad de pagos aprobados"] == 2
    assert detalle["Pago dividido"] == "Sí"
    assert detalle["Neto financiero total"] == "$ 100,00"
    assert "Neto de pagos aprobados" not in detalle


def test_resumen_separa_alcances_y_no_mezcla_exclusivos_mp_con_comparables():
    reporte = reconciliar(
        [op(id_orden="EXACTA", neto="100", utilidad="10"), op(id_orden="DIF", neto="50", utilidad="5"), op(id_orden="SINMOV", neto="30", utilidad="3")],
        [
            mov(id_orden="EXACTA", monto="100", id_mp="mp-exacta"),
            mov(id_orden="DIF", monto="60", id_mp="mp-dif"),
            mov(id_orden="SOLOMP", monto="70", id_mp="mp-solo"),
            mov(id_orden="DEV", monto="-25", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="mp-dev"),
            mov(id_orden="REC", monto="-15", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="mp-rec"),
            mov(id_orden=None, monto="-200", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="mp-payout", fila=20),
        ],
    )
    kpis = resumen_kpis(reporte)
    assert kpis["Operaciones comparables"] == 2
    assert kpis["Conciliadas exactas"] == 1
    assert kpis["Operaciones comparables con diferencia"] == 1
    assert kpis["Grupos financieros sin operación en el archivo comercial"] == 3
    assert kpis["Operaciones comerciales sin movimiento financiero"] == 1
    assert kpis["Movimientos de fondos"] == 1
    assert kpis["Neto comercial de operaciones comparables"] == "$ 150,00"
    assert kpis["Neto aprobado de Mercado Pago de operaciones comparables"] == "$ 160,00"
    assert kpis["Diferencia de control — operaciones comparables"] == "$ 10,00"
    assert kpis["Neto aprobado de Mercado Pago sin operación comercial asociada"] == "$ 70,00"
    sin_operacion = [r for r in reporte.resultados if r.cantidad_operaciones_comerciales == 0 and r.estado != EstadoConciliacion.MOVIMIENTO_DE_FONDOS]
    assert {r.estado for r in sin_operacion} == {EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL, EstadoConciliacion.DEVUELTA, EstadoConciliacion.EN_RECLAMO}
    assert all(isinstance(v, Decimal) for r in reporte.resultados for v in (r.neto_financiero_total, r.impacto_devoluciones, r.impacto_reclamos_disputas, r.impacto_otros))
    assert not any(isinstance(v, float) for r in reporte.resultados for v in asdict(r).values())
    texto_presentacion = str(kpis) + str([f.__dict__ for f in filas_presentacion(reporte.resultados)])
    for pii in ("Persona", "DNI", "tarjeta", "email", "12345678"):
        assert pii not in texto_presentacion


def test_cobertura_archivos_periodos_iguales_diferentes_y_liquidaciones():
    operaciones = [op(id_orden="A", fila=1), op(id_orden="B", fila=2)]
    movimientos = [mov(id_orden="A", id_mp="a", liquidado=True), mov(id_orden="B", id_mp="b", liquidado=False)]
    cobertura = cobertura_archivos(operaciones, movimientos)
    assert cobertura.periodo_ventas_ml.texto == "01/01/2026"
    assert cobertura.periodo_origen_mp.texto == "01/01/2026"
    assert cobertura.periodo_liquidacion_mp.texto == "01/01/2026"
    assert cobertura.movimientos_sin_fecha_liquidacion == 1
    assert cobertura.origenes_coinciden is True
    assert cobertura.advertencia_origenes is None

    otra_fecha = datetime(2026, 1, 3, tzinfo=UTC)
    diferentes = cobertura_archivos([op(id_orden="C", fila=3)], [mov(id_orden="C", id_mp="c", hash_="h3")])
    assert diferentes.origenes_coinciden is True
    movimiento_fuera = mov(id_orden="Z", id_mp="z")
    movimiento_fuera = movimiento_fuera.__class__(**{**asdict(movimiento_fuera), "fecha_origen_utc": otra_fecha, "fecha_origen_local": otra_fecha})
    diferentes = cobertura_archivos([op(id_orden="C", fila=3)], [movimiento_fuera])
    assert diferentes.periodo_origen_mp.texto == "03/01/2026"
    assert diferentes.origenes_coinciden is False
    assert diferentes.advertencia_origenes is not None
    assert "no coinciden" in diferentes.advertencia_origenes
    assert "recortar" in diferentes.advertencia_origenes
