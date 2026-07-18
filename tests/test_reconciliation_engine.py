from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.financial_movement import MovimientoFinanciero, TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion, MotivoConciliacion, ReporteConciliacion, ResultadoConciliacion
from kiki_control.reconciliation import reconciliar

FECHA = datetime(2026, 1, 1, tzinfo=UTC)


def op(id_orden="1", neto="100", fila=1, utilidad="25", hash_="h-op"):
    return OperacionComercial(
        fuente="ML", hash_importacion=hash_, numero_fila_origen=fila, id_orden=id_orden,
        id_carrito=None, sku="SKU", fecha_venta_original="2026-01-01", hora_venta_original="10:00",
        fecha_hora_venta=FECHA, producto="Producto", tipo_envio=None, provincia=None, cantidad=1,
        precio_unitario=Decimal("100"), monto_venta=Decimal("100"), costo_unitario_con_iva=Decimal("50"),
        costo_total_con_iva=Decimal("50"), comision_mercado_libre_informada=None, costo_envio_bruto=None,
        costo_envio_vendedor=None, costo_envio_prorrateado=None, bonificacion_envio=None,
        monto_neto_mercado_pago_informado=Decimal(neto), impuestos_y_comisiones_informados=None,
        utilidad_neta_informada=Decimal(utilidad), precio_equilibrio=None, tasa_iva=None,
        rentabilidad_precio_venta=None, rentabilidad_costo_producto=None, rentabilidad_suma_costos=None,
        tasa_comision_mercado_libre=None, tasa_costo_envio=None, parametros_calculo_original="{}",
        costo_incluye_alicuota=None, precio_incluye_alicuota=None, tasa_iibb_configurada=None,
    )


def mov(id_orden="1", monto="100", tipo=TipoOperacionFinanciera.PAGO_APROBADO, fila=10, id_mp="mp-1", hash_="h-mov", liquidado=True):
    fecha_liq = FECHA if liquidado else None
    return MovimientoFinanciero("MP", hash_, fila, "Hoja1", None, id_mp, id_orden, None, None, None, "SKU", None, tipo, tipo.value, None, None, None, None, None, Decimal("0"), None, Decimal("0"), Decimal(monto), None, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), "ARS", "ARS", "2026-01-01", FECHA, FECHA, "2026-01-01", FECHA, FECHA, "2026-01-02" if liquidado else None, fecha_liq, fecha_liq, None, (), None, None)


def único(reporte):
    assert reporte.total_resultados == 1
    return reporte.resultados[0]


def test_conciliacion_exacta_uno_a_uno_y_trazabilidad():
    r = único(reconciliar([op(hash_="hash-c", fila=7)], [mov(hash_="hash-f", fila=8)]))
    assert r.estado == EstadoConciliacion.CONCILIADA
    assert r.motivos == (MotivoConciliacion.COINCIDENCIA_NETA_EXACTA,)
    assert r.diferencia_control == Decimal("0")
    assert r.hashes_importacion_comercial == ("hash-c",)
    assert r.hashes_importacion_financiera == ("hash-f",)
    assert r.numeros_fila_comercial == (7,)
    assert r.numeros_fila_financiera == (8,)


def test_diferencias_positiva_negativa_tolerancia_y_rechazo():
    assert único(reconciliar([op(neto="100")], [mov(monto="101")])).diferencia_control == Decimal("1")
    assert único(reconciliar([op(neto="100")], [mov(monto="99")])).diferencia_control == Decimal("-1")
    menor = único(reconciliar([op(neto="100")], [mov(monto="100.01")], tolerancia=Decimal("0.01")))
    assert menor.estado == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR
    mayor = único(reconciliar([op(neto="100")], [mov(monto="100.02")], tolerancia=Decimal("0.01")))
    assert mayor.estado == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA
    assert MotivoConciliacion.DIFERENCIA_SUPERA_TOLERANCIA in mayor.motivos
    with pytest.raises(ValueError):
        reconciliar([], [], tolerancia=Decimal("-0.01"))


def test_pago_dividido_coincide_con_diferencia_y_no_es_duplicado():
    exacto = único(reconciliar([op(neto="100")], [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11)]))
    assert exacto.estado == EstadoConciliacion.CONCILIADA
    assert exacto.es_pago_dividido is True
    assert exacto.tiene_duplicados is False
    assert exacto.neto_pagos_aprobados == Decimal("100")
    dif = único(reconciliar([op(neto="100")], [mov(monto="40", id_mp="a"), mov(monto="61", id_mp="b", fila=11)]))
    assert dif.estado == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA
    assert MotivoConciliacion.PAGO_DIVIDIDO in dif.motivos


def test_operacion_sin_movimiento_y_movimiento_con_orden_sin_operacion():
    sin_mov = único(reconciliar([op()], []))
    assert sin_mov.estado == EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO
    assert sin_mov.neto_pagos_aprobados is None and sin_mov.diferencia_control is None
    sin_op = único(reconciliar([], [mov(id_orden="9")]))
    assert sin_op.estado == EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL
    assert sin_op.neto_comercial_informado is None and sin_op.diferencia_control is None


def test_movimientos_sin_orden_payout_otros_y_no_se_mezclan():
    reporte = reconciliar([], [mov(id_orden=None, tipo=TipoOperacionFinanciera.PAYOUT, fila=2), mov(id_orden=None, tipo=TipoOperacionFinanciera.CASHBACK, fila=3, id_mp="c")])
    assert [r.estado for r in reporte.resultados] == [EstadoConciliacion.MOVIMIENTO_DE_FONDOS, EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL]
    assert reporte.resultados[0].motivos == (MotivoConciliacion.PAYOUT_SIN_ORDEN,)
    assert reporte.resultados[1].motivos == (MotivoConciliacion.ORDEN_AUSENTE,)


def test_liquidacion_pendiente_envio_y_componentes_total():
    r = único(reconciliar([op(neto="100")], [mov(monto="100", liquidado=False), mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="e", fila=11)]))
    assert r.estado == EstadoConciliacion.PENDIENTE_ACREDITACION
    assert r.tiene_liquidacion_pendiente and r.tiene_pago_envio
    assert r.impacto_pagos_envio == Decimal("-10")
    assert r.neto_financiero_total == Decimal("90")
    assert r.diferencia_control == Decimal("0")


def test_devoluciones_reclamos_disputas_y_mismo_id_distinto_tipo():
    dev = mov(monto="-100", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="mp-1", fila=11)
    r = único(reconciliar([op()], [mov(id_mp="mp-1"), dev]))
    assert r.estado == EstadoConciliacion.DEVUELTA
    assert r.tiene_devolucion and not r.tiene_duplicados
    assert r.impacto_devoluciones == Decimal("-100")
    rec = único(reconciliar([op()], [mov(), mov(monto="-5", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="r", fila=12)]))
    assert rec.estado == EstadoConciliacion.EN_RECLAMO and rec.tiene_reclamo and rec.requiere_revision
    dis = único(reconciliar([op()], [mov(), mov(monto="-3", tipo=TipoOperacionFinanciera.DISPUTA_ENVIO, id_mp="d", fila=12)]))
    assert dis.estado == EstadoConciliacion.EN_RECLAMO and dis.tiene_disputa
    ambos = único(reconciliar([op()], [mov(), dev, mov(monto="-5", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="r", fila=12)]))
    assert ambos.tiene_devolucion and ambos.tiene_reclamo and ambos.estado == EstadoConciliacion.EN_RECLAMO


def test_desconocidos_y_duplicados():
    desc = único(reconciliar([op()], [mov(), mov(monto="1", tipo=TipoOperacionFinanciera.DESCONOCIDA, id_mp="x", fila=12)]))
    assert desc.estado == EstadoConciliacion.EN_REVISION and desc.tiene_movimiento_desconocido
    op_dup = único(reconciliar([op(fila=1), op(fila=2, hash_="h2")], [mov()]))
    assert op_dup.estado == EstadoConciliacion.DUPLICADA and op_dup.tiene_duplicados
    fin_dup = único(reconciliar([op()], [mov(id_mp="z"), mov(id_mp="z", fila=11)]))
    assert fin_dup.estado == EstadoConciliacion.DUPLICADA
    assert MotivoConciliacion.MOVIMIENTO_FINANCIERO_DUPLICADO in fin_dup.motivos


def test_impactos_utilidad_decimales_inmutabilidad_orden_totales_y_sin_dataframes():
    movimientos = [
        mov(id_orden="b", monto="100", id_mp="b1"),
        mov(id_orden="a", monto="40", id_mp="a1"),
        mov(id_orden="a", monto="60", id_mp="a2", fila=11),
        mov(id_orden="a", monto="-12", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env", fila=12),
        mov(id_orden="a", monto="-30", tipo=TipoOperacionFinanciera.DEVOLUCION_ENVIO, id_mp="dev", fila=13),
        mov(id_orden="a", monto="-7", tipo=TipoOperacionFinanciera.DISPUTA_ENVIO, id_mp="dis", fila=14),
        mov(id_orden="a", monto="2", tipo=TipoOperacionFinanciera.CASHBACK, id_mp="cash", fila=15),
    ]
    reporte = reconciliar([op(id_orden="b"), op(id_orden="a", utilidad="33")], movimientos)
    assert [r.id_orden for r in reporte.resultados] == ["a", "b"]
    a = reporte.resultados[0]
    assert a.neto_pagos_aprobados == Decimal("100")
    assert a.impacto_pagos_envio == Decimal("-12")
    assert a.impacto_devoluciones == Decimal("-30")
    assert a.impacto_reclamos_disputas == Decimal("-7")
    assert a.impacto_otros == Decimal("2")
    assert a.neto_financiero_total == Decimal("53")
    assert a.utilidad_neta_informada == Decimal("33")
    assert isinstance(a.motivos, tuple)
    assert not any(isinstance(v, float) for v in asdict(a).values())
    assert not any("DataFrame" in type(v).__name__ for v in asdict(reporte).values())
    assert ReporteConciliacion.total_resultados.fget is not None
    assert reporte.total_resultados == 2
    assert reporte.total_devueltas == 0
    assert reporte.total_en_reclamo == 1


def test_api_publica_no_contiene_dependencias_de_interfaz_o_archivos():
    import kiki_control.reconciliation.engine as engine

    assert "pandas" not in engine.__dict__
    assert "streamlit" not in engine.__dict__
    assert "openpyxl" not in engine.__dict__
    assert ResultadoConciliacion.__name__
