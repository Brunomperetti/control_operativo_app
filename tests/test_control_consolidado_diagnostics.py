from datetime import date
from decimal import Decimal
from dataclasses import FrozenInstanceError

import pytest

from kiki_control.domain.control_consolidado import EstadoControlConsolidado as E, IndicadoresFinancieros, ReporteControlConsolidado, ResultadoControlConsolidado
from kiki_control.presentation.control_consolidado_diagnostics import diagnosticar_control_consolidado
from kiki_control.presentation.control_consolidado_view import etiqueta_selector_detalle, filas_tabla_consolidada, estado_visible

IND = IndicadoresFinancieros(False, False, False, False, False, False, False, False)
D = Decimal

def r(clave, estado=E.COMPLETA, ml=D('100'), mp=D('100'), costo=D('40'), dif=D('0'), venta_ml=D('120'), venta_ec=D('120'), neto_ec=D('100'), tiene_ml=True, tiene_ec=True, tiene_mp=True, filas_mp=(1,), revision=False):
    return ResultadoControlConsolidado(clave, clave if not clave.startswith('fin:') else None, (clave,) if not clave.startswith('fin:') else (), tiene_ml, tiene_ec, tiene_mp, None, venta_ml if tiene_ml else None, None, None, None, None, None, ml, venta_ec if tiene_ec else None, costo if tiene_ec else None, None, neto_ec if tiene_ec else None, None, mp if tiene_mp else None, mp if tiene_mp else None, None, None, None, None, (venta_ml-venta_ec) if venta_ml is not None and venta_ec is not None else None, (ml-neto_ec) if ml is not None and neto_ec is not None else None, dif, (ml-costo) if ml is not None and costo is not None else None, D('0.01'), estado, revision or state_needs_review(estado), (), (), IND, 'v', (), (), (), (), (), filas_mp, (), (clave,))

def state_needs_review(e):
    return e != E.COMPLETA

def rep(resultados):
    return ReporteControlConsolidado(tuple(resultados), 'v', D('0.01'), 0, 0, len(resultados), sum(x.requiere_revision for x in resultados), sum(x.estado==E.COMPLETA for x in resultados), sum(x.estado==E.CON_DIFERENCIA for x in resultados), sum(x.estado==E.SIN_MOVIMIENTO_FINANCIERO for x in resultados), sum(x.estado==E.SOLO_MOVIMIENTO_FINANCIERO for x in resultados), sum(x.estado==E.SIN_VENTA_OFICIAL for x in resultados), sum(x.estado==E.SIN_COSTO_PRODUCTO for x in resultados), sum(x.estado==E.EN_REVISION_FINANCIERA for x in resultados), sum(x.estado==E.DUPLICADA_O_AMBIGUA for x in resultados), D('0'), D('0'), D('0'))

def test_diferencia_real_no_depende_del_estado_principal_y_signos_tolerancia():
    reporte = rep([r('sin-costo', E.SIN_COSTO_PRODUCTO, mp=D('110'), costo=None, dif=D('10')), r('neg', E.CON_DIFERENCIA, mp=D('80'), dif=D('-20')), r('tol', E.COMPLETA, mp=D('100.005'), dif=D('0.005'))])
    diag = diagnosticar_control_consolidado(reporte)
    assert diag.diferencias.con_diferencia_ml_mp == 2
    assert diag.diferencias.diferencias_positivas == 1
    assert diag.diferencias.diferencias_negativas == 1
    assert diag.diferencias.coincidencias_dentro_tolerancia == 1
    assert diag.diferencias.identidad_cierra_exactamente

def test_puente_identidad_y_universos_separados():
    reporte = rep([r('a', ml=D('90'), mp=D('95'), neto_ec=D('92'), dif=D('5'), venta_ml=D('150'), venta_ec=D('140')), r('sin-neto-ec', neto_ec=None, venta_ml=D('20'), venta_ec=D('10'))])
    puente = diagnosticar_control_consolidado(reporte).puente
    assert puente.universo_venta_comercial == 2
    assert puente.universo_neto_esperado == 1
    assert puente.mp_menos_ml == puente.mp_menos_eccomapp + puente.eccomapp_menos_ml
    assert puente.clasificacion_pendiente == 'Diferencia pendiente de clasificación contable'

def test_utilidad_calculable_costo_excluido_y_motivos_mutuamente_excluyentes():
    reporte = rep([r('ok'), r('sin-total', ml=None, mp=D('1'), costo=D('7'), dif=None, tiene_ml=True), r('sin-ec', costo=None, tiene_ec=False), r('sin-costo', costo=None), r('solo-mp', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, costo=None, dif=None, tiene_ml=False, tiene_ec=False)])
    utilidad = diagnosticar_control_consolidado(reporte).utilidad
    assert utilidad.grupos_calculables == 1
    assert utilidad.costo_eccomapp_fuera_universo_calculable == D('7')
    assert utilidad.motivos_cierran_exactamente
    assert utilidad.motivos_exclusion['con venta oficial pero sin Total (ARS)'] == 1
    assert utilidad.motivos_exclusion['faltan ambas entradas'] == 1
    assert utilidad.identidad_cierra_exactamente

def test_particion_revisiones_multietiqueta_temporal_y_presentacion_sin_hashes():
    reporte = rep([r('ok'), r('diff', E.CON_DIFERENCIA, mp=D('110'), dif=D('10'), revision=True), r('fin:abc:hash:fila:1', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('5'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(1,)), r('fin:def:hash:fila:2', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('6'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(2,)), r('fin:ghi:hash:fila:3', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('7'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(3,))])
    diag = diagnosticar_control_consolidado(reporte, date(2026, 7, 10), date(2026, 7, 20), {1: date(2026,7,1), 2: date(2026,7,15), 3: date(2026,7,30)})
    assert diag.particion.cierra_exactamente
    assert diag.revisiones.total_primario_requiere_revision == reporte.total_requieren_revision
    assert sum(x.cantidad for x in diag.revisiones.revisiones_multietiqueta) >= diag.revisiones.total_primario_requiere_revision
    assert (diag.temporal_mp_sin_venta.anteriores.cantidad, diag.temporal_mp_sin_venta.dentro.cantidad, diag.temporal_mp_sin_venta.posteriores.cantidad) == (1,1,1)
    fila = filas_tabla_consolidada([reporte.resultados[2]])[0]
    assert 'hash' not in etiqueta_selector_detalle(fila) and etiqueta_selector_detalle(fila).startswith('Movimiento MP sin orden')
    assert estado_visible(E.SOLO_MOVIMIENTO_FINANCIERO) == 'Solo movimiento de Mercado Pago'

def test_decimal_sin_float_pii_y_modelo_inmutable():
    source = open('src/kiki_control/presentation/control_consolidado_diagnostics.py', encoding='utf-8').read()
    assert 'float(' not in source and 'comprador' not in source.lower() and 'documento' not in source.lower()
    item = r('immutable')
    with pytest.raises(FrozenInstanceError):
        item.diferencia_ml_mp = D('1')
