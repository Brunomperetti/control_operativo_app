from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from kiki_control.domain.financial_movement import TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.presentation.explanations import (
    COLUMNAS_TABLA,
    ESTADOS,
    METRICAS_COBERTURA,
    METRICAS_RESUMEN,
    MP_ID_ORDER,
    MP_NETO,
    MP_TIPO,
    SENSITIVE_COLUMNS,
    cobertura_desigual_no_bloqueante,
    explicar_operacion,
    guia_general,
)
from kiki_control.presentation.reconciliation_view import ENCABEZADOS_TABLA_CLIENTE, cobertura_archivos, detalle_cliente, es_excepcion_o_caso_especial, resumen_kpis_tipado
from kiki_control.reconciliation import reconciliar
from tests.test_reconciliation_engine import mov, op


def _textos(obj):
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for k, v in obj.items() for t in _textos(k) + _textos(v)]
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [t for v in obj for t in _textos(v)]
    if hasattr(obj, "__dataclass_fields__"):
        return _textos(asdict(obj))
    return []


def test_todas_las_metricas_visibles_tienen_definicion():
    assert set(METRICAS_RESUMEN) == {
        "Comparables", "Coincidencias exactas", "Con diferencia", "Sin venta en ML", "Sin movimiento en MP", "Requieren revisión", "Movimientos de fondos", "Utilidad informada ML", "Neto ML comparable", "Neto MP comparable", "Diferencia comparable", "Neto MP fuera del archivo ML",
    }
    assert set(METRICAS_COBERTURA) == {"Ventas ML", "Origen movimientos MP", "Liquidaciones MP", "Sin fecha de liquidación"}
    assert all(d.ayuda for d in (*METRICAS_RESUMEN.values(), *METRICAS_COBERTURA.values()))


def test_todas_las_columnas_visibles_tienen_ayuda_y_columnas_externas_exactas():
    assert set(COLUMNAS_TABLA) == set(ENCABEZADOS_TABLA_CLIENTE.values())
    assert all(d.ayuda for d in COLUMNAS_TABLA.values())
    textos = "\n".join(_textos(COLUMNAS_TABLA) + _textos(METRICAS_RESUMEN) + _textos(METRICAS_COBERTURA) + _textos(guia_general()))
    for columna in ["ID Order", "ID DE LA ORDEN", "Sku", "CÓDIGO DE PRODUCTO SKU", "Monto neto (en MP) ($)", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO", "TIPO DE OPERACIÓN"]:
        assert columna in textos


def test_formula_diferencia_orden_mp_menos_ml_y_signo_correcto():
    resultado = reconciliar([op(neto="100")], [mov(monto="90")]).resultados[0]
    pasos = explicar_operacion(resultado, [op(neto="100")], [mov(monto="90")], Decimal("0.01"))
    diferencia = next(p for p in pasos if p.resultado == "Diferencia")
    assert "-$ 10,00" in diferencia.valor_calculado
    assert "$ 90,00 - $ 100,00 = -$ 10,00" in diferencia.regla_o_formula
    assert "MP informa menos neto que ML" in diferencia.regla_o_formula
    positivo = reconciliar([op(neto="100")], [mov(monto="110")]).resultados[0]
    texto = next(p for p in explicar_operacion(positivo, [op(neto="100")], [mov(monto="110")], Decimal("0.01")) if p.resultado == "Diferencia").regla_o_formula
    assert "MP informa más neto que ML" in texto


def test_neto_aprobado_con_id_muestra_filas_suma_final_y_agrupacion():
    movimientos = [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11), mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env", fila=12)]
    resultado = reconciliar([op(neto="100")], movimientos).resultados[0]
    assert resultado.neto_pagos_aprobados == Decimal("100")
    assert resultado.neto_financiero_total == Decimal("90")
    paso = next(p for p in explicar_operacion(resultado, [op(neto="100")], movimientos, Decimal("0.01")) if p.resultado == "Neto aprobado MP")
    assert paso.valor_calculado == "$ 100,00"
    assert "Movimientos PAGO_APROBADO utilizados" in paso.regla_o_formula
    assert "fila 10: $ 40,00" in paso.regla_o_formula
    assert "fila 11: $ 60,00" in paso.regla_o_formula
    assert "Suma final: $ 100,00" in paso.regla_o_formula
    assert "agrupados por ID DE LA ORDEN" in paso.regla_o_formula


def test_pago_aprobado_sin_id_orden_no_se_presenta_como_usado_y_conserva_estado_motor():
    movimiento = mov(id_orden=None, monto="123.45", fila=55)
    resultado = reconciliar([], [movimiento]).resultados[0]
    estado_original = resultado.estado
    assert resultado.id_orden is None
    assert resultado.neto_pagos_aprobados is None
    assert resultado.neto_financiero_total == Decimal("123.45")

    pasos = explicar_operacion(resultado, [], [movimiento], Decimal("0.01"))
    paso_neto = next(p for p in pasos if p.resultado == "Neto aprobado MP")
    paso_total = next(p for p in pasos if p.resultado == "Neto financiero total")

    assert paso_neto.valor_calculado == "—"
    assert "fila 55" in paso_neto.regla_o_formula
    assert "$ 123,45" in paso_neto.regla_o_formula
    assert "utilizado" not in paso_neto.regla_o_formula
    assert "Suma final" not in paso_neto.regla_o_formula
    assert "ID DE LA ORDEN" in paso_neto.regla_o_formula
    assert "no se utiliza para calcular el neto aprobado comparable" in paso_neto.regla_o_formula
    assert "no puede agruparse ni compararse por orden" in paso_neto.regla_o_formula.lower()
    assert "Neto financiero total" in paso_neto.regla_o_formula
    assert paso_total.valor_calculado == "$ 123,45"
    assert resultado.estado == estado_original == EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL


def test_neto_aprobado_sin_pagos_aprobados_conserva_explicacion():
    solo_envio = reconciliar([op(neto="100")], [mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env")]).resultados[0]
    assert solo_envio.neto_pagos_aprobados is None and solo_envio.neto_financiero_total == Decimal("-10")
    paso = next(p for p in explicar_operacion(solo_envio, [op(neto="100")], [mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env")], Decimal("0.01")) if p.resultado == "Neto aprobado MP")
    assert paso.regla_o_formula == "No hay movimientos normalizados como pago aprobado; por eso el Neto aprobado MP queda vacío."


def test_cobertura_desigual_no_bloqueante_excepciones_revision_y_payout_separado():
    assert "continúa" in cobertura_desigual_no_bloqueante()
    cobertura = cobertura_archivos([op(id_orden="A")], [mov(id_orden="A", liquidado=False)])
    assert cobertura.movimientos_sin_fecha_liquidacion == 1
    reporte = reconciliar([], [mov(id_orden=None, tipo=TipoOperacionFinanciera.PAYOUT, monto="-10", fila=42)])
    r = reporte.resultados[0]
    assert r.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS
    assert es_excepcion_o_caso_especial(r) is True
    assert r.requiere_revision is False
    assert resumen_kpis_tipado(reporte)["Movimientos de fondos"] == 1


def test_referencia_interna_sin_orden_no_se_presenta_como_id_real_y_muestra_filas():
    movimiento = mov(id_orden=None, tipo=TipoOperacionFinanciera.PAYOUT, monto="-10", fila=77)
    resultado = reconciliar([], [movimiento]).resultados[0]
    assert detalle_cliente(resultado)["ID de orden"] == "Movimiento MP sin ID de orden — referencia interna fila 77"
    pasos = explicar_operacion(resultado, [], [movimiento], Decimal("0.01"))
    assert "referencia interna fila 77" in pasos[0].valor_calculado
    assert any("77" in p.filas_origen for p in pasos)


def test_textos_no_contienen_columnas_sensibles_ni_pii():
    textos = "\n".join(_textos(COLUMNAS_TABLA) + _textos(METRICAS_RESUMEN) + _textos(METRICAS_COBERTURA) + _textos(guia_general()))
    for sensible in SENSITIVE_COLUMNS:
        assert sensible not in textos
    for pii in ["DNI", "tarjeta", "email", "DATOS EXTRA"]:
        assert pii not in textos


def test_no_floats_sin_archivos_reales_inmutabilidad_y_modulo_puro():
    operacion = op(id_orden="SYN-A", neto="100")
    movimiento = mov(id_orden="SYN-A", monto="100")
    antes = asdict(operacion), asdict(movimiento)
    reporte = reconciliar([operacion], [movimiento])
    pasos = explicar_operacion(reporte.resultados[0], [operacion], [movimiento], Decimal("0.01"))
    assert (asdict(operacion), asdict(movimiento)) == antes
    assert not any(isinstance(v, float) for paso in pasos for v in asdict(paso).values())
    source = Path("src/kiki_control/presentation/explanations.py").read_text()
    assert "import streamlit" not in source
    assert "import pandas" not in source
    assert "import openpyxl" not in source


def test_diccionario_cubre_todos_los_estados_y_motor_no_cambia():
    assert {e.estado for e in ESTADOS} == set(EstadoConciliacion)
    base = reconciliar([op(id_orden="A", neto="100")], [mov(id_orden="A", monto="95")]).resultados[0]
    _ = guia_general()
    _ = explicar_operacion(base, [op(id_orden="A", neto="100")], [mov(id_orden="A", monto="95")], Decimal("0.01"))
    assert base.estado == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA
    assert base.diferencia_control == Decimal("-5")
    assert MP_ID_ORDER == "ID DE LA ORDEN" and MP_TIPO == "TIPO DE OPERACIÓN" and MP_NETO == "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO"


def _paso(resultado, nombre, operaciones, movimientos):
    return next(p for p in explicar_operacion(resultado, operaciones, movimientos, Decimal("0.01")) if p.resultado == nombre)


def test_indicadores_visibles_explican_si_y_no_con_columnas_exactas():
    op_base = op(id_orden="IND", neto="100")
    movimientos_si = [
        mov(id_orden="IND", monto="40", id_mp="p1", liquidado=False),
        mov(id_orden="IND", monto="60", id_mp="p2", fila=11),
        mov(id_orden="IND", monto="-10", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="dev", fila=12),
        mov(id_orden="IND", monto="-5", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="rec", fila=13),
    ]
    resultado_si = reconciliar([op_base], movimientos_si).resultados[0]
    assert _paso(resultado_si, "Pago dividido", [op_base], movimientos_si).valor_calculado == "Sí"
    assert "Cantidad encontrada: 2" in _paso(resultado_si, "Pago dividido", [op_base], movimientos_si).regla_o_formula
    assert _paso(resultado_si, "Pago dividido", [op_base], movimientos_si).columnas_utilizadas == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO")
    assert _paso(resultado_si, "Devolución", [op_base], movimientos_si).valor_calculado == "Sí"
    assert _paso(resultado_si, "Devolución", [op_base], movimientos_si).columnas_utilizadas == ("TIPO DE OPERACIÓN",)
    assert _paso(resultado_si, "Reclamo o disputa", [op_base], movimientos_si).valor_calculado == "Sí"
    assert _paso(resultado_si, "Reclamo o disputa", [op_base], movimientos_si).columnas_utilizadas == ("TIPO DE OPERACIÓN",)
    assert _paso(resultado_si, "Pendiente de acreditación", [op_base], movimientos_si).valor_calculado == "Sí"
    assert _paso(resultado_si, "Pendiente de acreditación", [op_base], movimientos_si).columnas_utilizadas == ("TIPO DE OPERACIÓN", "FECHA DE LIQUIDACIÓN DEL DINERO")
    assert _paso(resultado_si, "Requiere revisión", [op_base], movimientos_si).valor_calculado == "Sí"
    assert "no equivale necesariamente" in _paso(resultado_si, "Requiere revisión", [op_base], movimientos_si).regla_o_formula

    movimientos_no = [mov(id_orden="IND", monto="100", id_mp="ok")]
    resultado_no = reconciliar([op_base], movimientos_no).resultados[0]
    assert _paso(resultado_no, "Pago dividido", [op_base], movimientos_no).valor_calculado == "No"
    assert "cero o un único pago aprobado" in _paso(resultado_no, "Pago dividido", [op_base], movimientos_no).regla_o_formula
    assert _paso(resultado_no, "Devolución", [op_base], movimientos_no).valor_calculado == "No"
    assert "No se detectaron" in _paso(resultado_no, "Devolución", [op_base], movimientos_no).regla_o_formula
    assert _paso(resultado_no, "Reclamo o disputa", [op_base], movimientos_no).valor_calculado == "No"
    assert "No se detectaron" in _paso(resultado_no, "Reclamo o disputa", [op_base], movimientos_no).regla_o_formula
    assert _paso(resultado_no, "Pendiente de acreditación", [op_base], movimientos_no).valor_calculado == "No"
    assert "No se encontró" in _paso(resultado_no, "Pendiente de acreditación", [op_base], movimientos_no).regla_o_formula
    assert _paso(resultado_no, "Requiere revisión", [op_base], movimientos_no).valor_calculado == "No"


def test_estado_final_explica_ganador_en_lenguaje_cliente_y_columnas_intervinientes():
    op_base = op(id_orden="EST", neto="100")
    movimientos = [mov(id_orden="EST", monto="95", liquidado=False)]
    resultado = reconciliar([op_base], movimientos).resultados[0]
    estado = _paso(resultado, "Estado final", [op_base], movimientos)
    assert estado.valor_calculado == "Pendiente de acreditación"
    assert "El estado ganador" in estado.regla_o_formula
    assert "prioridad oficial" in estado.regla_o_formula
    assert estado.columnas_utilizadas == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN", "FECHA DE LIQUIDACIÓN DEL DINERO")


def _columnas_estado_final(resultado, operaciones, movimientos):
    return _paso(resultado, "Estado final", operaciones, movimientos).columnas_utilizadas


def test_columnas_estado_exactas_para_estados_comparables_y_pendiente():
    columnas_comparables = ("ID Order", "Monto neto (en MP) ($)", "ID DE LA ORDEN", "TIPO DE OPERACIÓN", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO")
    operacion = op(id_orden="OK", neto="100")
    movimiento = mov(id_orden="OK", monto="100")
    conciliada = reconciliar([operacion], [movimiento]).resultados[0]
    assert conciliada.estado == EstadoConciliacion.CONCILIADA
    assert _columnas_estado_final(conciliada, [operacion], [movimiento]) == columnas_comparables

    operacion_dif = op(id_orden="DIF", neto="100")
    movimiento_dif = mov(id_orden="DIF", monto="101")
    diferencia = reconciliar([operacion_dif], [movimiento_dif]).resultados[0]
    assert diferencia.estado == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA
    assert _columnas_estado_final(diferencia, [operacion_dif], [movimiento_dif]) == columnas_comparables

    operacion_pend = op(id_orden="PEND", neto="100")
    movimiento_pend = mov(id_orden="PEND", monto="100", liquidado=False)
    pendiente = reconciliar([operacion_pend], [movimiento_pend]).resultados[0]
    assert pendiente.estado == EstadoConciliacion.PENDIENTE_ACREDITACION
    assert _columnas_estado_final(pendiente, [operacion_pend], [movimiento_pend]) == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN", "FECHA DE LIQUIDACIÓN DEL DINERO")


def test_columnas_estado_exactas_para_sin_contraparte_devolucion_reclamo_revision_y_fondos():
    operacion = op(id_orden="SINMP", neto="100")
    sin_mp = reconciliar([operacion], []).resultados[0]
    assert sin_mp.estado == EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO
    assert _columnas_estado_final(sin_mp, [operacion], []) == ("ID Order",)

    movimiento_sin_ml = mov(id_orden="SINML", monto="100")
    sin_ml = reconciliar([], [movimiento_sin_ml]).resultados[0]
    assert sin_ml.estado == EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL
    assert _columnas_estado_final(sin_ml, [], [movimiento_sin_ml]) == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN")

    devolucion_mov = mov(id_orden="DEV", monto="-10", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="dev")
    devuelta = reconciliar([], [devolucion_mov]).resultados[0]
    assert devuelta.estado == EstadoConciliacion.DEVUELTA
    columnas_dev = _columnas_estado_final(devuelta, [], [devolucion_mov])
    assert columnas_dev == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN")
    assert "Monto neto (en MP) ($)" not in columnas_dev
    assert "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO" not in columnas_dev

    reclamo_mov = mov(id_orden="REC", monto="-5", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="rec")
    reclamo = reconciliar([], [reclamo_mov]).resultados[0]
    assert reclamo.estado == EstadoConciliacion.EN_RECLAMO
    columnas_rec = _columnas_estado_final(reclamo, [], [reclamo_mov])
    assert columnas_rec == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN")
    assert "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO" not in columnas_rec

    desconocido_mov = mov(id_orden="UNK", monto="1", tipo=TipoOperacionFinanciera.DESCONOCIDA, id_mp="unk")
    revision = reconciliar([], [desconocido_mov]).resultados[0]
    assert revision.estado == EstadoConciliacion.EN_REVISION
    assert _columnas_estado_final(revision, [], [desconocido_mov]) == ("ID DE LA ORDEN", "TIPO DE OPERACIÓN")

    payout = mov(id_orden=None, monto="-20", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="payout", fila=55)
    fondos = reconciliar([], [payout]).resultados[0]
    assert fondos.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS
    estado_fondos = _paso(fondos, "Estado final", [], [payout])
    assert estado_fondos.columnas_utilizadas == ("TIPO DE OPERACIÓN", "ID DE LA ORDEN")
    assert "PAYOUT" in estado_fondos.regla_o_formula


def test_columnas_estado_exactas_para_duplicadas_comercial_y_financiera_sin_cambiar_motor():
    op_1 = op(id_orden="DUPC", fila=1, hash_="hc1")
    op_2 = op(id_orden="DUPC", fila=2, hash_="hc2")
    mov_c = mov(id_orden="DUPC", id_mp="mp-dupc")
    duplicada_comercial = reconciliar([op_1, op_2], [mov_c]).resultados[0]
    assert duplicada_comercial.estado == EstadoConciliacion.DUPLICADA
    assert _columnas_estado_final(duplicada_comercial, [op_1, op_2], [mov_c]) == ("ID Order",)

    op_f = op(id_orden="DUPF")
    mov_f1 = mov(id_orden="DUPF", id_mp="mp-repetido", fila=20)
    mov_f2 = mov(id_orden="DUPF", id_mp="mp-repetido", fila=21)
    duplicada_financiera = reconciliar([op_f], [mov_f1, mov_f2]).resultados[0]
    assert duplicada_financiera.estado == EstadoConciliacion.DUPLICADA
    columnas_fin = _columnas_estado_final(duplicada_financiera, [op_f], [mov_f1, mov_f2])
    assert columnas_fin == ("ID DE OPERACIÓN EN MERCADO PAGO", "TIPO DE OPERACIÓN")
    assert "ID DE OPERACIÓN EN MERCADO PAGO" in columnas_fin
    assert duplicada_financiera.neto_financiero_total == mov_f1.monto_neto_impactado + mov_f2.monto_neto_impactado
    assert not any("REAL" in str(valor) for valor in columnas_fin)
