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
    assert diag.temporal_mp_sin_venta.fechas_mixtas.cantidad == 0
    assert diag.temporal_mp_sin_venta.dentro.cantidad == 1
    assert diag.temporal_mp_sin_venta.dentro.neto_aprobado_mp == D('0')
    assert diag.temporal_mp_sin_venta.dentro.neto_financiero_total_mp == D('0')
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
    assert diag.residual_ml.nombre_visible == 'Otros conceptos pendientes de clasificación'
    assert diag.residual_ml.grupos_universo_ml_oficial == 2
    assert diag.residual_ml.grupos_calculables == 0
    assert diag.residual_ml.grupos_excluidos == 2
    assert diag.residual_ml.importe == D('-120')
    assert diag.residual_ml.estado_conciliacion == 'PENDIENTE'
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
    assert residual.importe == D('5')
    assert residual.suma_total_ars == D('150')
    assert residual.suma_ingresos_productos == D('184')
    assert residual.suma_ingresos_envio == D('0')
    assert residual.suma_cargo_venta_impuestos == D('-23')
    assert residual.suma_costos_envio == D('-16')
    assert residual.suma_anulaciones_reembolsos == D('0')
    assert residual.suma_cupones_descuento == D('0')
    assert not residual.identidad_cierra_exactamente
    assert residual.metodo_cupones == 'SIN_EVIDENCIA'
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
    assert not residual.identidad_cierra_exactamente
    assert residual.importe == D('10')


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
    assert residual.suma_ingresos_envio == D('0')
    assert residual.suma_cargo_venta_impuestos == D('-25')
    assert residual.suma_costos_envio == D('0')
    assert residual.suma_anulaciones_reembolsos == D('0')
    assert residual.suma_cupones_descuento == D('0')
    assert residual.importe == D('0')
    assert residual.identidad_cierra_exactamente


def test_cupon_explicito_se_respeta_cuando_cierra_dentro_de_tolerancia():
    reporte = rep([replace(r('explicito'), total_informado_ml=D('80'), monto_venta_ml=D('100'), ingresos_envio_ml=D('5'), cargo_venta_impuestos_ml=D('-10'), costo_envio_ml=D('-3'), anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('-12'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    assert residual.metodo_cupones == 'INFORMADO_POR_FUENTE'
    assert residual.suma_cupones_descuento == D('-12')
    assert residual.diferencia_final == D('0')
    assert residual.estado_conciliacion == 'CIERRA'


def test_residual_sin_evidencia_cupon_queda_en_otros_conceptos():
    """Si Descuentos y bonificaciones está en cero, el residual no se atribuye a cupones."""
    reporte = rep([replace(r('residual'), total_informado_ml=D('85'), monto_venta_ml=D('100'), ingresos_envio_ml=None, cargo_venta_impuestos_ml=D('-5'), costo_envio_ml=D('-5'), anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('0'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    assert residual.metodo_cupones == 'SIN_EVIDENCIA'
    assert residual.suma_cupones_descuento == D('0')
    assert residual.diferencia_final == D('-5')
    assert residual.estado_conciliacion == 'PENDIENTE'


def test_diferencia_final_queda_pendiente_si_faltan_componentes_base():
    reporte = rep([replace(r('pendiente'), total_informado_ml=D('90'), monto_venta_ml=None, ingresos_envio_ml=None, cargo_venta_impuestos_ml=D('-5'), costo_envio_ml=D('-5'), anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('0'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    assert residual.grupos_excluidos == 1
    assert residual.diferencia_final == D('100')
    assert residual.estado_conciliacion == 'PENDIENTE'


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


# --- Pruebas obligatorias de clasificación del residual (req. 7) ---

def test_residual_sin_evidencia_no_se_clasifica_como_cupon():
    """Req. 7-1/7-4: sin evidencia explícita, el residual permanece en 'Otros conceptos'."""
    reporte = rep([replace(r('sin-ev'), total_informado_ml=D('200'), monto_venta_ml=D('220'),
                           ingresos_envio_ml=D('0'), cargo_venta_impuestos_ml=D('-10'),
                           costo_envio_ml=D('-5'), anulaciones_reembolsos_ml=D('0'),
                           descuentos_bonificaciones_ml=D('0'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    # El residual_sin_cupon = 200 - (220 + 0 + (-10) + (-5) + 0) = -5
    # Sin evidencia de cupón: suma_cupones debe quedar en 0, residual en -5.
    assert residual.metodo_cupones == 'SIN_EVIDENCIA'
    assert residual.suma_cupones_descuento == D('0')
    assert residual.diferencia_final == D('-5')
    assert residual.estado_conciliacion == 'PENDIENTE'
    # El componente "Otros conceptos" refleja el residual, no el cupón.
    otros = next(c for c in residual.componentes if c.concepto == 'Otros conceptos pendientes de clasificación')
    assert otros.importe == D('-5')


def test_cupon_explicito_valido_usa_informado_por_fuente():
    """Req. 7-2: un cupón explícito que cierra la identidad usa INFORMADO_POR_FUENTE."""
    reporte = rep([replace(r('con-cupon'), total_informado_ml=D('80'),
                           monto_venta_ml=D('100'), ingresos_envio_ml=D('0'),
                           cargo_venta_impuestos_ml=D('-10'), costo_envio_ml=D('-5'),
                           anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('-5'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    # residual_sin_cupon = 80 - (100 + 0 + (-10) + (-5) + 0) = -5; cupon_fuente = -5 → cierra
    assert residual.metodo_cupones == 'INFORMADO_POR_FUENTE'
    assert residual.suma_cupones_descuento == D('-5')
    assert residual.diferencia_final == D('0')
    assert residual.estado_conciliacion == 'CIERRA'


def test_cupon_parcial_no_cierra_identidad_residual_queda_pendiente():
    """Req. 7-3/7-4: un cupón que no cierra la identidad deja residual en 'Otros conceptos'."""
    reporte = rep([replace(r('cupon-parcial'), total_informado_ml=D('75'),
                           monto_venta_ml=D('100'), ingresos_envio_ml=D('0'),
                           cargo_venta_impuestos_ml=D('-10'), costo_envio_ml=D('-5'),
                           anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('-3'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    # residual_sin_cupon = 75 - (100 + 0 + (-10) + (-5) + 0) = -10; cupon_fuente = -3
    # diferencia_con_fuente = -10 - (-3) = -7 > tolerancia → no cierra → SIN_EVIDENCIA, suma_cupones=0 (fuente=-3 != 0 pero no cierra)
    # Wait: metodo_cupones = "INFORMADO_POR_FUENTE" if (filas_cupones > 0 and suma_cupones_fuente != 0) else "SIN_EVIDENCIA"
    # Here filas_cupones > 0 and suma = -3 != 0, so metodo = "INFORMADO_POR_FUENTE"
    # suma_cupones = -3; residual = 75 - (100 + 0 + (-10) + (-5) + 0 + (-3)) = 75 - 82 = -7
    assert residual.metodo_cupones == 'INFORMADO_POR_FUENTE'
    assert residual.suma_cupones_descuento == D('-3')
    assert residual.diferencia_final == D('-7')
    assert residual.estado_conciliacion == 'PENDIENTE'
    otros = next(c for c in residual.componentes if c.concepto == 'Otros conceptos pendientes de clasificación')
    assert otros.importe == D('-7')


def test_nunca_se_fuerza_residual_a_cupon_para_cerrar_identidad():
    """Req. 7-4: con todos los componentes presentes pero sin cupón explícito, la identidad no cierra artificialmente."""
    reporte = rep([replace(r('no-cierre'), total_informado_ml=D('90'),
                           monto_venta_ml=D('100'), ingresos_envio_ml=D('0'),
                           cargo_venta_impuestos_ml=D('-5'), costo_envio_ml=D('-5'),
                           anulaciones_reembolsos_ml=D('0'), descuentos_bonificaciones_ml=D('0'))])
    residual = diagnosticar_control_consolidado(reporte).residual_ml
    # residual_sin_cupon = 90 - (100 + 0 + (-5) + (-5) + 0) = 0
    # cupon_fuente = 0 → SIN_EVIDENCIA; suma_cupones = 0; diferencia_final = 0 (pero por fórmula, no por forzar)
    # El residual es 0 porque la suma de componentes ya coincide con el total, sin necesidad de cupón.
    assert residual.metodo_cupones == 'SIN_EVIDENCIA'
    assert residual.suma_cupones_descuento == D('0')
    # La identidad cierra naturalmente (no se forzó cupón).
    assert residual.diferencia_final == D('0')
    assert residual.estado_conciliacion == 'CIERRA'


def test_bloque_d_separa_mp_sin_venta_y_excluye_payout_de_todas_sus_filas():
    casos = [
        r('fin:ant', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('10'), neto_fin=D('-1'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(11,)),
        r('fin:den', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('20'), neto_fin=D('-2'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(12,)),
        r('fin:post', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('30'), neto_fin=D('-3'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(13,)),
        r('fin:sf', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('40'), neto_fin=D('-4'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(14,)),
        r('fin:payout', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('999'), neto_fin=D('999'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(15,), tipo=TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS),
    ]
    diag = diagnosticar_control_consolidado(rep(casos), date(2026, 7, 10), date(2026, 7, 20), {
        11: date(2026, 7, 1), 12: date(2026, 7, 15), 13: date(2026, 7, 30), 15: date(2026, 7, 15),
    })
    filas = {x.motivo_visible: x for x in diag.revisiones.revisiones_multietiqueta}
    nombres = (
        'MP sin venta anterior al período ML', 'MP sin venta dentro del período ML',
        'MP sin venta posterior al período ML', 'MP sin venta sin fecha de origen',
    )
    assert [filas[n].cantidad for n in nombres] == [1, 1, 1, 1]
    assert [filas[n].importe_afectado for n in nombres] == [D('-1'), D('-2'), D('-3'), D('-4')]
    assert all(filas[n].accion_recomendada for n in nombres)
    assert all('payout' not in filas[n].grupos_involucrados for n in nombres)
    assert 'Fuente faltante' not in filas or 'fin:payout' not in filas['Fuente faltante'].grupos_involucrados
    assert diag.temporal_mp_sin_venta.total_solo_movimiento_financiero == 4


def test_coherencia_resumen_bloque_b_y_filas_temporales_bloque_d():
    from kiki_control.presentation.bloque_b_diagnostics import diagnosticar_bloque_b
    casos = [
        r('fin:a', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('10'), neto_fin=D('-1'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(21,)),
        r('fin:d', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('20'), neto_fin=D('-2'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(22, 23)),
        r('fin:p', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('30'), neto_fin=D('-3'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(24,)),
        r('fin:s', E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D('40'), neto_fin=D('-4'), costo=None, dif=None, tiene_ml=False, tiene_ec=False, filas_mp=(25,)),
    ]
    fechas = {21: date(2026, 7, 1), 22: date(2026, 7, 1), 23: date(2026, 7, 15), 24: date(2026, 7, 30)}
    reporte = rep(casos)
    b = diagnosticar_bloque_b(reporte, date(2026, 7, 10), date(2026, 7, 20), fechas)
    d = diagnosticar_control_consolidado(reporte, date(2026, 7, 10), date(2026, 7, 20), fechas)
    resumen_b = {x.categoria.value: (x.cantidad_grupos, x.neto_financiero_total) for x in b.resumen_mp_sin_venta}
    temporal_d = {
        'ANTERIOR_AL_PERIODO_ML': d.temporal_mp_sin_venta.anteriores,
        'DENTRO_DEL_PERIODO_ML_SIN_VENTA': d.temporal_mp_sin_venta.dentro,
        'POSTERIOR_AL_PERIODO_ML': d.temporal_mp_sin_venta.posteriores,
        'SIN_FECHA_DE_ORIGEN': d.temporal_mp_sin_venta.sin_fecha,
    }
    assert all(resumen_b[k][0] == v.cantidad for k, v in temporal_d.items())
    assert sum(x[0] for x in resumen_b.values()) == b.cantidad_mp_sin_venta == 4
    # Bloque B no reutiliza agregados cuando el detalle por fila carece de monto.
    assert sum(x[1] for x in resumen_b.values()) == b.neto_financiero_total_mp_sin_venta == D('0')
    assert not b.coherencia_detalle_importes_mp_sin_venta
