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


def test_neto_aprobado_y_financiero_total_pago_dividido_y_sin_pago_aprobado():
    movimientos = [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11), mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env", fila=12)]
    resultado = reconciliar([op(neto="100")], movimientos).resultados[0]
    assert resultado.neto_pagos_aprobados == Decimal("100")
    assert resultado.neto_financiero_total == Decimal("90")
    pasos = explicar_operacion(resultado, [op(neto="100")], movimientos, Decimal("0.01"))
    assert "fila 10: $ 40,00" in next(p for p in pasos if p.resultado == "Neto aprobado MP").regla_o_formula
    assert "fila 11: $ 60,00" in next(p for p in pasos if p.resultado == "Neto aprobado MP").regla_o_formula
    solo_envio = reconciliar([op(neto="100")], [mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env")]).resultados[0]
    assert solo_envio.neto_pagos_aprobados is None and solo_envio.neto_financiero_total == Decimal("-10")
    assert "No hay movimientos PAGO_APROBADO" in next(p for p in explicar_operacion(solo_envio, [op(neto="100")], [mov(monto="-10", tipo=TipoOperacionFinanciera.PAGO_ENVIO, id_mp="env")], Decimal("0.01")) if p.resultado == "Neto aprobado MP").regla_o_formula


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
