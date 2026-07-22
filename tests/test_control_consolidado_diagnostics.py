from datetime import date
from decimal import Decimal
from dataclasses import FrozenInstanceError, replace

import pytest

from kiki_control.domain.control_consolidado import EstadoControlConsolidado as E, IndicadoresFinancieros, ReporteControlConsolidado, ResultadoControlConsolidado, TipoMovimientoFinanciero
from kiki_control.presentation.control_consolidado_diagnostics import diagnosticar_control_consolidado
from kiki_control.presentation.control_consolidado_view import etiqueta_selector_detalle, filas_tabla_consolidada, estado_visible

IND = IndicadoresFinancieros(False, False, False, False, False, False, False, False)
D = Decimal

def r(clave, estado=E.COMPLETA, ml=D('100'), mp=D('100'), costo=D('40'), dif=D('0'), venta_ml=D('120'), venta_ec=D('120'), neto_ec=D('100'), tiene_ml=True, tiene_ec=True, tiene_mp=True, filas_mp=(1,), revision=False, neto_fin='DEFAULT', ind=IND, tipo=None):
    neto_fin_valor = mp if neto_fin == 'DEFAULT' else neto_fin
    return ResultadoControlConsolidado(clave, clave if not clave.startswith('fin:') else None, (clave,) if not clave.startswith('fin:') else (), tiene_ml, tiene_ec, tiene_mp, tipo, venta_ml if tiene_ml else None, None, None, None, None, None, ml, venta_ec if tiene_ec else None, costo if tiene_ec else None, None, neto_ec if tiene_ec else None, None, mp if tiene_mp else None, neto_fin_valor if tiene_mp else None, None, None, None, None, (venta_ml-venta_ec) if venta_ml is not None and venta_ec is not None else None, (ml-neto_ec) if ml is not None and neto_ec is not None else None, dif, (ml-costo) if ml is not None and costo is not None else None, D('0.01'), estado, revision or state_needs_review(estado), (), (), ind, 'v', (), (), (), (), (), filas_mp, (), (clave,))

def state_needs_review(e):
    return e != E.COMPLETA

def rep(resultados):
    return ReporteControlConsolidado(tuple(resultados), 'v', D('0.01'), 0, 0, len(resultados), sum(x.requiere_revision for x in resultados), sum(x.estado==E.COMPLETA for x in resultados), sum(x.estado==E.CON_DIFERENCIA for x in resultados), sum(x.estado==E.SIN_MOVIMIENTO_FINANCIERO for x in resultados), sum(x.estado==E.SOLO_MOVIMIENTO_FINANCIERO for x in resultados), sum(x.estado==E.SIN_VENTA_OFICIAL for x in resultados), sum(x.estado==E.SIN_COSTO_PRODUCTO for x in resultados), sum(x.estado==E.EN_REVISION_FINANCIERA for x in resultados), sum(x.estado==E.DUPLICADA_O_AMBIGUA for x in resultados), D('0'), D('0'), D('0'), sum(x.estado==E.TOTAL_ML_AUSENTE for x in resultados))

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


def test_temporal_conserva_decimal_cero_y_distingue_none():
    reporte = rep([
        r('fin:cero:hash:fila:1', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('99'), neto_fin=D('0'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(1,)),
        r('fin:none:hash:fila:2', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('3'), neto_fin=None, costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(2,)),
    ])
    temporal = diagnosticar_control_consolidado(reporte, date(2026, 7, 1), date(2026, 7, 31), {1: date(2026,7,10), 2: date(2026,7,10)}).temporal_mp_sin_venta
    assert temporal.dentro.cantidad == 2
    assert temporal.dentro.neto_aprobado_mp == D('102')
    assert temporal.dentro.neto_financiero_total_mp == D('0')
    assert temporal.particion_cierra_exactamente


def test_mp_no_comparable_legitimo_no_es_dato_critico_y_venta_sin_neto_si_lo_es():
    devolucion = IndicadoresFinancieros(False, True, False, False, False, False, False, False)
    reclamo = IndicadoresFinancieros(False, False, True, True, False, False, False, False)
    casos = [
        r('dev', mp=None, neto_fin=D('-10'), ind=devolucion, revision=True),
        r('rec', mp=None, neto_fin=D('-20'), ind=reclamo, revision=True),
        r('payout', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=None, neto_fin=D('0'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, tipo=TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS),
        r('venta-sin-neto', mp=None, neto_fin=None, revision=True),
    ]
    filas = filas_tabla_consolidada(casos)
    assert not filas[0].tiene_datos_faltantes
    assert not filas[1].tiene_datos_faltantes
    assert filas[2].motivo_principal == 'Fuente faltante'
    assert filas[3].motivo_principal == 'Sin neto aprobado MP comparable'


def test_revisiones_multietiqueta_solo_requiere_revision_y_temporal_mixta_cierra():
    reporte = rep([
        r('diff-no-revision', E.COMPLETA, mp=D('120'), dif=D('20'), revision=False),
        r('diff-revision', E.CON_DIFERENCIA, mp=D('130'), dif=D('30'), revision=True),
        r('fin:mix:hash:fila:8', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('0'), neto_fin=D('0'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(8,9)),
        r('fin:sinfecha:hash:fila:10', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=None, neto_fin=None, costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(10,)),
    ])
    diag = diagnosticar_control_consolidado(reporte, date(2026,7,10), date(2026,7,20), {8: date(2026,7,1), 9: date(2026,7,30)})
    dif_rev = [x for x in diag.revisiones.revisiones_multietiqueta if x.motivo_visible == 'Diferencia pendiente de clasificación contable'][0]
    assert dif_rev.cantidad == 1
    assert diag.temporal_mp_sin_venta.fechas_mixtas.cantidad == 1
    assert diag.temporal_mp_sin_venta.fechas_mixtas.neto_aprobado_mp == D('0')
    assert diag.temporal_mp_sin_venta.fechas_mixtas.neto_financiero_total_mp == D('0')
    assert diag.temporal_mp_sin_venta.sin_fecha.cantidad == 1
    assert diag.temporal_mp_sin_venta.particion_cierra_exactamente


def test_modulo_puro_sin_streamlit_dataframe_float_ni_pii():
    source = open('src/kiki_control/presentation/control_consolidado_diagnostics.py', encoding='utf-8').read().lower()
    assert 'streamlit' not in source
    assert 'dataframe' not in source
    assert 'float(' not in source
    assert 'comprador' not in source and 'documento' not in source and 'email' not in source

def test_selector_usa_ids_orden_reales_y_no_compara_claves():
    con_orden = r('fin:hash:fila:99', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('10'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(99,))
    # simula un resultado cuya clave técnica parece financiera pero el texto visible trae ID de orden real
    fila = filas_tabla_consolidada([con_orden])[0]
    fila = fila.__class__(fila.clave, fila.grupo_orden, fila.estado, fila.estado_codigo, fila.fuentes_disponibles, fila.venta_ml_oficial, fila.cargos_impuestos_ml, fila.costo_envio_ml, fila.neto_esperado_ml, fila.costo_productos, fila.neto_aprobado_mp, fila.neto_financiero_total_mp, fila.diferencia_ml_mp, fila.utilidad_preliminar, fila.requiere_revision, fila.tiene_diferencia, fila.tiene_datos_faltantes, fila.motivo_principal, fila.que_revisar, ('123456789',), fila.filas_origen_mp)
    assert etiqueta_selector_detalle(fila) == 'Orden 123456789 — Solo movimiento de Mercado Pago'
    sin_orden = filas_tabla_consolidada([r('fin:x:hash:fila:7', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('1'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(7,))])[0]
    assert etiqueta_selector_detalle(sin_orden) == 'Movimiento MP sin orden — fila 7'


def test_cobertura_residual_puente_excluidos_y_neto_mp_doble():
    reporte = rep([
        r('triple', ml=D('100'), mp=D('100'), costo=D('40'), dif=D('0'), neto_ec=D('100'), venta_ml=D('150'), venta_ec=D('150')),
        r('fuera-triple', ml=D('50'), mp=D('70'), costo=D('20'), dif=D('20'), neto_ec=None),
        r('solo-ec', E.SIN_VENTA_OFICIAL, ml=None, mp=None, costo=D('18560'), dif=None, tiene_ml=False, tiene_mp=False),
        r('fin:solo:hash:fila:21', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('5'), neto_fin=D('-15'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(21,)),
    ])
    diag = diagnosticar_control_consolidado(reporte, date(2026,7,1), date(2026,7,31), {21: date(2026,7,10)})
    assert {c.universo for c in diag.cobertura_monetaria} >= {'universo completo ML oficial', 'universo completo Eccomapp', 'universo ML–Eccomapp', 'universo ML–MP', 'universo ML–Eccomapp–MP', 'universo calculable de utilidad'}
    assert diag.utilidad.costo_eccomapp_fuera_universo_calculable == D('18560')
    assert diag.residual_ml.nombre_visible == 'Otros conceptos y ajustes ML no desagregados en este resumen'
    assert diag.residual_ml.grupos_universo_ml_oficial == 2
    assert diag.residual_ml.grupos_calculables == 0
    assert diag.residual_ml.grupos_excluidos == 2
    assert diag.residual_ml.importe == D('0')
    assert len(diag.puente.grupos_excluidos_universo_triple) == 3
    assert diag.puente.aporte_excluidos_a_diferencia_ml_mp == D('20')
    assert diag.temporal_mp_sin_venta.dentro.neto_aprobado_mp == D('5')
    assert diag.temporal_mp_sin_venta.dentro.neto_financiero_total_mp == D('-15')


def con_componentes_ml(resultado, total, ingresos, cargos, envio):
    return replace(
        resultado,
        total_informado_ml=total,
        monto_venta_ml=ingresos,
        cargo_venta_impuestos_ml=cargos,
        costo_envio_ml=envio,
    )


def test_temporal_mp_separa_aprobado_financiero_none_y_cero_sin_fallback():
    reporte = rep([
        r('fin:distinto:hash:fila:1', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('100'), neto_fin=D('-20'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(1,)),
        r('fin:solo-fin:hash:fila:2', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=None, neto_fin=D('-30'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(2,)),
        r('fin:solo-aprobado:hash:fila:3', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('40'), neto_fin=None, costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(3,)),
        r('fin:cero-vs-none:hash:fila:4', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('0'), neto_fin=None, costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(4,)),
    ])
    temporal = diagnosticar_control_consolidado(
        reporte,
        date(2026, 7, 1),
        date(2026, 7, 31),
        {1: date(2026, 7, 10), 2: date(2026, 7, 10), 3: date(2026, 7, 10), 4: date(2026, 7, 10)},
    ).temporal_mp_sin_venta
    assert temporal.dentro.cantidad == 4
    assert temporal.dentro.neto_aprobado_mp == D('140')
    assert temporal.dentro.neto_financiero_total_mp == D('-50')
    assert temporal.particion_cierra_exactamente


def test_residual_ml_solo_calcula_grupos_con_cuatro_importes_e_identidad():
    completo = con_componentes_ml(r('completo'), D('120'), D('150'), D('-20'), D('-10'))
    ceros_validos = con_componentes_ml(r('ceros'), D('0'), D('0'), D('0'), D('0'))
    sin_total = con_componentes_ml(r('sin-total'), None, D('10'), D('-1'), D('-2'))
    sin_ingresos = con_componentes_ml(r('sin-ingresos'), D('10'), None, D('-1'), D('-2'))
    sin_cargo = con_componentes_ml(r('sin-cargo'), D('10'), D('12'), None, D('-2'))
    sin_envio = con_componentes_ml(r('sin-envio'), D('10'), D('12'), D('-1'), None)
    residual = diagnosticar_control_consolidado(rep([completo, ceros_validos, sin_total, sin_ingresos, sin_cargo, sin_envio])).residual_ml
    assert residual.grupos_universo_ml_oficial == 6
    assert residual.grupos_calculables == 2
    assert residual.grupos_excluidos == 4
    assert residual.importe == D('0')
    assert residual.suma_total_ars == D('120')
    assert residual.suma_ingresos_productos == D('150')
    assert residual.suma_cargo_venta_impuestos == D('-20')
    assert residual.suma_costos_envio == D('-10')
    assert residual.identidad_cierra_exactamente
    assert residual.motivos_exclusion['falta Total (ARS)'] == 1
    assert residual.motivos_exclusion['falta Ingresos por productos (ARS)'] == 1
    assert residual.motivos_exclusion['falta Cargo por venta e impuestos (ARS)'] == 1
    assert residual.motivos_exclusion['falta Costos de envío (ARS)'] == 1
    source = open('src/kiki_control/presentation/control_consolidado_diagnostics.py', encoding='utf-8').read()
    assert ' or _ZERO' not in source and 'float(' not in source


def test_residual_ml_excluye_solo_mp_y_solo_eccomapp_del_universo():
    completo = con_componentes_ml(r('ml-completo'), D('120'), D('150'), D('-20'), D('-10'))
    faltante_ml = con_componentes_ml(r('ml-faltante'), D('10'), None, D('0'), D('0'))
    solo_mp = r('fin:solo-mp:hash:fila:1', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('50'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(1,))
    solo_ec = r('solo-ec', E.SIN_VENTA_OFICIAL, ml=None, mp=None, costo=D('70'), dif=None, tiene_ml=False, tiene_mp=False)
    residual = diagnosticar_control_consolidado(rep([completo, faltante_ml, solo_mp, solo_ec])).residual_ml
    assert residual.grupos_universo_ml_oficial == 2
    assert residual.grupos_calculables == 1
    assert residual.grupos_excluidos == 1
    assert residual.grupos_calculables + residual.grupos_excluidos == residual.grupos_universo_ml_oficial
    assert residual.motivos_exclusion['falta Ingresos por productos (ARS)'] == 1
    assert residual.identidad_cierra_exactamente


def test_residual_ml_incluye_envio_vacio_ya_normalizado_como_cero():
    envio_vacio_normalizado = con_componentes_ml(r('envio-vacio-normalizado'), D('80'), D('100'), D('-20'), D('0'))
    otro_calculable = con_componentes_ml(r('otro'), D('45'), D('50'), D('-5'), D('0'))

    residual = diagnosticar_control_consolidado(rep([envio_vacio_normalizado, otro_calculable])).residual_ml

    assert residual.grupos_universo_ml_oficial == 2
    assert residual.grupos_calculables == 2
    assert residual.grupos_excluidos == 0
    assert residual.motivos_exclusion['falta Costos de envío (ARS)'] == 0
    assert residual.suma_total_ars == D('125')
    assert residual.suma_ingresos_productos == D('150')
    assert residual.suma_cargo_venta_impuestos == D('-25')
    assert residual.suma_costos_envio == D('0')
    assert residual.importe == D('0')
    assert residual.identidad_cierra_exactamente


def test_conclusion_con_diferencias_usa_diagnostico_no_estado_principal():
    from kiki_control.presentation.control_consolidado_view import conclusion_ejecutiva_consolidada

    reporte = rep([
        r('diff-a', E.COMPLETA, ml=D('100'), mp=D('110'), dif=D('10')),
        r('diff-b', E.COMPLETA, ml=D('200'), mp=D('214.34'), dif=D('14.34')),
        r('ok', E.COMPLETA, ml=D('50'), mp=D('50'), dif=D('0')),
    ])
    diagnostico = diagnosticar_control_consolidado(reporte)
    texto = conclusion_ejecutiva_consolidada(reporte, diagnostico)

    assert reporte.total_con_diferencia == 0
    assert diagnostico.diferencias.con_diferencia_ml_mp == 2
    assert diagnostico.diferencias.suma_diferencia_ml_mp == diagnostico.diferencias.suma_neto_mp_comparable - diagnostico.diferencias.suma_neto_ml_comparable
    assert "1 de 3 grupos comparables coinciden dentro de la tolerancia" in texto
    assert "2 presentan diferencias" in texto
    assert "$ 24,34" in texto
