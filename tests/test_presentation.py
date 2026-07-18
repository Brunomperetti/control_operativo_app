from decimal import Decimal

from kiki_control.domain.financial_movement import TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.reconciliation_view import ETIQUETAS_ESTADO, detalle_presentacion, filas_presentacion, filtrar_filas, resultado_a_fila, resumen_kpis
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
    assert kpis["Operaciones comerciales"] == 2
    assert kpis["Movimientos de fondos"] == 1
    assert kpis["Neto comercial informado"] == "$ 150,00"
    assert kpis["Neto de pagos aprobados"] == "$ 151,00"
    assert kpis["Diferencia total de control"] == "$ 1,00"
    assert kpis["Utilidad informada por Mercado Libre"] == "$ 15,00"


def test_detalle_presentacion_completo():
    resultado = reconciliar([op(neto="100")], [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11)]).resultados[0]
    detalle = detalle_presentacion(resultado)
    assert detalle["ID de orden"] == "1"
    assert detalle["Cantidad de pagos aprobados"] == 2
    assert detalle["Pago dividido"] == "Sí"
    assert detalle["Neto financiero total"] == "$ 100,00"
