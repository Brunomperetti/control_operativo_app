"""Motor puro de control financiero consolidado ML oficial / Eccomapp / MP."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from kiki_control.domain.commercial_link import EstadoVinculacionComercial, ReporteVinculacionComercial, ResultadoVinculacionComercial
from kiki_control.domain.control_consolidado import (
    ErrorControlConsolidado,
    EstadoControlConsolidado,
    IndicadoresFinancieros,
    ReporteControlConsolidado,
    ResultadoControlConsolidado,
    TipoMovimientoFinanciero,
    VERSION_REGLA_CONTROL_CONSOLIDADO,
)
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.domain.reconciliation import EstadoConciliacion, ReporteConciliacion, ResultadoConciliacion

_PRIORIDAD = (
    EstadoControlConsolidado.DUPLICADA_O_AMBIGUA,
    EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO,
    EstadoControlConsolidado.SIN_VENTA_OFICIAL,
    EstadoControlConsolidado.SIN_COSTO_PRODUCTO,
    EstadoControlConsolidado.SIN_MOVIMIENTO_FINANCIERO,
    EstadoControlConsolidado.EN_REVISION_FINANCIERA,
    EstadoControlConsolidado.CON_DIFERENCIA,
    EstadoControlConsolidado.COMPLETA,
)

_ZERO = Decimal("0")


def _sumar(valores):
    vals = [v for v in valores if v is not None]
    if not vals:
        return None
    return sum(vals, _ZERO)


def _ordenes(r: ResultadoVinculacionComercial) -> tuple[str, ...]:
    return tuple(sorted({oid.strip() for oid in r.ids_orden if oid and oid.strip()}))


def _ordenes_para_mercado_pago(r: ResultadoVinculacionComercial) -> tuple[str, ...]:
    ids = _ordenes(r)
    if ids:
        return ids
    if r.estado == EstadoVinculacionComercial.SOLO_MERCADO_LIBRE and r.venta_principal_ml is None and len(r.ventas_detalle_ml) == 1:
        return (str(r.ventas_detalle_ml[0].id_venta).strip(),)
    return ()


def _tiene_movimiento_mercado_pago(resultado: ResultadoConciliacion) -> bool:
    return resultado.cantidad_movimientos_financieros > 0


def _monetaria_ml(r: ResultadoVinculacionComercial) -> VentaOficialMercadoLibre | None:
    if r.estado in {EstadoVinculacionComercial.AMBIGUA, EstadoVinculacionComercial.DUPLICADA}:
        return None
    if r.venta_principal_ml is not None:
        return r.venta_principal_ml
    ventas = r.ventas_detalle_ml
    if r.estado == EstadoVinculacionComercial.SOLO_MERCADO_LIBRE and len(ventas) == 1:
        return ventas[0]
    return None


def _indicadores(financieros: tuple[ResultadoConciliacion, ...]) -> IndicadoresFinancieros:
    financieros_reales = tuple(f for f in financieros if _tiene_movimiento_mercado_pago(f))
    return IndicadoresFinancieros(
        tiene_liquidacion_pendiente=any(f.tiene_liquidacion_pendiente for f in financieros_reales),
        tiene_devolucion=any(f.tiene_devolucion for f in financieros_reales),
        tiene_reclamo=any(f.tiene_reclamo for f in financieros_reales),
        tiene_disputa=any(f.tiene_disputa for f in financieros_reales),
        tiene_pago_dividido=any(f.es_pago_dividido for f in financieros_reales),
        tiene_movimiento_desconocido=any(f.tiene_movimiento_desconocido for f in financieros_reales),
        tiene_duplicados=any(f.tiene_duplicados for f in financieros_reales),
        tiene_pago_envio=any(f.tiene_pago_envio for f in financieros_reales),
    )


def _estado(candidatos: set[EstadoControlConsolidado]) -> EstadoControlConsolidado:
    for e in _PRIORIDAD:
        if e in candidatos:
            return e
    return EstadoControlConsolidado.COMPLETA


def _fin_key(f: ResultadoConciliacion) -> str:
    filas = ",".join(str(n) for n in f.numeros_fila_financiera)
    hashes = ",".join(f.hashes_importacion_financiera)
    return f"fin:{f.id_orden or 'sin-orden'}:{hashes}:{filas}"


def _validar_hashes(reporte_comercial: ReporteVinculacionComercial, reporte_financiero: ReporteConciliacion) -> None:
    hashes_ec = set(reporte_comercial.hashes_importacion_eccomapp)
    usados = {h for f in reporte_financiero.resultados for h in f.hashes_importacion_comercial}
    if usados != hashes_ec:
        raise ErrorControlConsolidado(
            "Los hashes comerciales del reporte de conciliación deben coincidir exactamente con los hashes Eccomapp del reporte comercial; "
            "se cancela el cruce consolidado para evitar una unión silenciosa entre reportes incompatibles."
        )


def _resultado_desde(
    *,
    comercial: ResultadoVinculacionComercial | None,
    financieros: tuple[ResultadoConciliacion, ...],
    tolerancia: Decimal,
    ambiguo_financiero: bool = False,
) -> ResultadoControlConsolidado:
    venta = _monetaria_ml(comercial) if comercial else None
    ops = comercial.operaciones_eccomapp if comercial else ()
    ids_orden = _ordenes_para_mercado_pago(comercial) if comercial else tuple(sorted({f.id_orden for f in financieros if f.id_orden}))
    financieros_reales = tuple(f for f in financieros if _tiene_movimiento_mercado_pago(f))
    tiene_mp = bool(financieros_reales)
    ml_vals = {
        "monto_venta_ml": venta.ingresos_productos if venta else None,
        "cargo_venta_impuestos_ml": venta.cargo_venta_impuestos if venta else None,
        "ingresos_envio_ml": venta.ingresos_envio if venta else None,
        "costo_envio_ml": venta.costos_envio if venta else None,
        "descuentos_bonificaciones_ml": venta.descuentos_bonificaciones if venta else None,
        "anulaciones_reembolsos_ml": venta.anulaciones_reembolsos if venta else None,
        "total_informado_ml": venta.total_informado_ml if venta else None,
    }
    monto_ec = _sumar(op.monto_venta for op in ops)
    costo_prod = _sumar(op.costo_total_con_iva for op in ops)
    costo_env_ec = _sumar(op.costo_envio_vendedor for op in ops)
    neto_ec = _sumar(op.monto_neto_mercado_pago_informado for op in ops)
    utilidad_ec = _sumar(op.utilidad_neta_informada for op in ops)
    neto_mp = _sumar(f.neto_pagos_aprobados for f in financieros_reales)
    neto_fin = _sumar(f.neto_financiero_total for f in financieros_reales)
    imp_env = _sumar(f.impacto_pagos_envio for f in financieros_reales)
    imp_dev = _sumar(f.impacto_devoluciones for f in financieros_reales)
    imp_rec = _sumar(f.impacto_reclamos_disputas for f in financieros_reales)
    imp_otros = _sumar(f.impacto_otros for f in financieros_reales)
    total_ml = ml_vals["total_informado_ml"]
    dif_venta = ml_vals["monto_venta_ml"] - monto_ec if ml_vals["monto_venta_ml"] is not None and monto_ec is not None else None
    dif_neto_ec = total_ml - neto_ec if total_ml is not None and neto_ec is not None else None
    dif_ml_mp = neto_mp - total_ml if neto_mp is not None and total_ml is not None else None
    utilidad_control = total_ml - costo_prod if total_ml is not None and costo_prod is not None else None
    motivos = list(comercial.motivos if comercial else ())
    explicaciones = list(comercial.explicaciones if comercial else ())
    candidatos: set[EstadoControlConsolidado] = set()
    if comercial and comercial.estado in {EstadoVinculacionComercial.AMBIGUA, EstadoVinculacionComercial.DUPLICADA}:
        candidatos.add(EstadoControlConsolidado.DUPLICADA_O_AMBIGUA)
        motivos.append("RESULTADO_COMERCIAL_DUPLICADO_O_AMBIGUO")
    if ambiguo_financiero:
        candidatos.add(EstadoControlConsolidado.DUPLICADA_O_AMBIGUA)
        motivos.append("ID_ORDER_COMERCIAL_AMBIGUO_PARA_MP")
        explicaciones.append("El ID Order financiero aparece en más de un resultado comercial; no se asigna automáticamente a un grupo.")
    if comercial is None:
        candidatos.add(EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO)
        motivos.append("SIN_GRUPO_COMERCIAL")
    if comercial and not (comercial.venta_principal_ml or comercial.ventas_detalle_ml):
        candidatos.add(EstadoControlConsolidado.SIN_VENTA_OFICIAL)
    if comercial and costo_prod is None:
        candidatos.add(EstadoControlConsolidado.SIN_COSTO_PRODUCTO)
    if comercial and not tiene_mp:
        candidatos.add(EstadoControlConsolidado.SIN_MOVIMIENTO_FINANCIERO)
    ind = _indicadores(financieros)
    if financieros_reales and (any(f.requiere_revision for f in financieros_reales) or any((f.estado in {EstadoConciliacion.DEVUELTA, EstadoConciliacion.EN_RECLAMO, EstadoConciliacion.EN_REVISION, EstadoConciliacion.DUPLICADA, EstadoConciliacion.PENDIENTE_ACREDITACION}) for f in financieros_reales)):
        candidatos.add(EstadoControlConsolidado.EN_REVISION_FINANCIERA)
    if dif_ml_mp is not None and abs(dif_ml_mp) > tolerancia:
        candidatos.add(EstadoControlConsolidado.CON_DIFERENCIA)
        motivos.append("DIFERENCIA_ML_MP_SUPERA_TOLERANCIA")
    estado = _estado(candidatos)
    tipo = None
    if comercial is None and financieros:
        tipo = TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS if financieros_reales and all(f.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS for f in financieros_reales) else TipoMovimientoFinanciero.ORDEN_FINANCIERA
    requiere_revision = bool((comercial.requiere_revision if comercial else False) or any(f.requiere_revision for f in financieros) or estado != EstadoControlConsolidado.COMPLETA)
    return ResultadoControlConsolidado(
        clave_resultado=(comercial.clave_resultado if comercial else "+".join(_fin_key(f) for f in financieros)),
        id_grupo_canonico=comercial.id_grupo_canonico if comercial else None,
        ids_orden=ids_orden,
        tiene_mercado_libre_oficial=bool(comercial and (comercial.venta_principal_ml or comercial.ventas_detalle_ml)),
        tiene_eccomapp=bool(ops),
        tiene_mercado_pago=tiene_mp,
        tipo_movimiento_financiero=tipo,
        **ml_vals,
        monto_venta_eccomapp_informado=monto_ec,
        costo_productos_eccomapp=costo_prod,
        costo_envio_seller_eccomapp_informado=costo_env_ec,
        neto_mp_eccomapp_informado=neto_ec,
        utilidad_eccomapp_informada=utilidad_ec,
        neto_aprobado_mp=neto_mp,
        neto_financiero_total_mp=neto_fin,
        impacto_pagos_envio_mp=imp_env,
        impacto_devoluciones_mp=imp_dev,
        impacto_reclamos_disputas_mp=imp_rec,
        impacto_otros_mp=imp_otros,
        diferencia_venta_ml_eccomapp=dif_venta,
        diferencia_neto_ml_eccomapp=dif_neto_ec,
        diferencia_ml_mp=dif_ml_mp,
        utilidad_preliminar_control=utilidad_control,
        tolerancia=tolerancia,
        estado=estado,
        requiere_revision=requiere_revision,
        motivos=tuple(dict.fromkeys(motivos)),
        explicaciones=tuple(dict.fromkeys(explicaciones)),
        indicadores_financieros=ind,
        version_regla=VERSION_REGLA_CONTROL_CONSOLIDADO,
        hashes_importacion_ml=tuple(sorted(comercial.hashes_importacion_ml if comercial else ())),
        hashes_importacion_eccomapp=tuple(sorted(comercial.hashes_importacion_eccomapp if comercial else ())),
        hashes_importacion_mp=tuple(sorted({h for f in financieros_reales for h in f.hashes_importacion_financiera})),
        filas_origen_ml=tuple(sorted(comercial.filas_origen_ml if comercial else ())),
        filas_origen_eccomapp=tuple(sorted(comercial.filas_origen_eccomapp if comercial else ())),
        filas_origen_mp=tuple(sorted({n for f in financieros_reales for n in f.numeros_fila_financiera})),
        claves_resultados_comerciales=tuple([comercial.clave_resultado] if comercial else ()),
        claves_resultados_financieros=tuple(_fin_key(f) for f in financieros),
    )


def _validar_particion(comerciales, financieros, resultados):
    c = Counter(r.clave_resultado for r in comerciales)
    cs = Counter(k for r in resultados for k in r.claves_resultados_comerciales)
    f = Counter(_fin_key(r) for r in financieros)
    fs = Counter(k for r in resultados for k in r.claves_resultados_financieros)
    if c != cs or f != fs:
        raise AssertionError("El reporte consolidado no conserva una partición exacta de resultados comerciales y financieros.")


def consolidar_control_financiero(reporte_comercial: ReporteVinculacionComercial, reporte_financiero: ReporteConciliacion) -> ReporteControlConsolidado:
    """Consolida reportes comerciales y financieros solo por ID Order, sin I/O ni dependencias de UI."""
    _validar_hashes(reporte_comercial, reporte_financiero)
    comerciales = tuple(sorted(reporte_comercial.resultados, key=lambda r: r.clave_resultado))
    financieros = tuple(sorted(reporte_financiero.resultados, key=_fin_key))
    comerciales_por_orden: dict[str, list[ResultadoVinculacionComercial]] = defaultdict(list)
    ordenes_comerciales_ambiguas: set[str] = set()
    for r in comerciales:
        for oid in _ordenes_para_mercado_pago(r):
            comerciales_por_orden[oid].append(r)
        if r.estado in {EstadoVinculacionComercial.AMBIGUA, EstadoVinculacionComercial.DUPLICADA}:
            for v in ((r.venta_principal_ml,) if r.venta_principal_ml else ()) + r.ventas_detalle_ml:
                ordenes_comerciales_ambiguas.add(str(v.id_venta).strip())
    financieros_por_comercial: dict[str, list[ResultadoConciliacion]] = defaultdict(list)
    financieros_sueltos: list[tuple[ResultadoConciliacion, bool]] = []
    for f in financieros:
        if not f.id_orden:
            financieros_sueltos.append((f, False)); continue
        candidatos = comerciales_por_orden.get(f.id_orden, [])
        if f.id_orden in ordenes_comerciales_ambiguas:
            financieros_sueltos.append((f, True))
        elif len(candidatos) == 1:
            financieros_por_comercial[candidatos[0].clave_resultado].append(f)
        else:
            financieros_sueltos.append((f, len(candidatos) > 1))
    resultados = [_resultado_desde(comercial=c, financieros=tuple(sorted(financieros_por_comercial.get(c.clave_resultado, ()), key=_fin_key)), tolerancia=reporte_financiero.tolerancia) for c in comerciales]
    resultados.extend(_resultado_desde(comercial=None, financieros=(f,), tolerancia=reporte_financiero.tolerancia, ambiguo_financiero=amb) for f, amb in financieros_sueltos)
    resultados_t = tuple(sorted(resultados, key=lambda r: r.clave_resultado))
    _validar_particion(comerciales, financieros, resultados_t)
    cuenta = lambda e: sum(1 for r in resultados_t if r.estado == e)
    return ReporteControlConsolidado(
        resultados=resultados_t,
        version_regla=VERSION_REGLA_CONTROL_CONSOLIDADO,
        tolerancia=reporte_financiero.tolerancia,
        total_resultados_comerciales_recibidos=len(comerciales),
        total_resultados_financieros_recibidos=len(financieros),
        total_resultados=len(resultados_t),
        total_requieren_revision=sum(1 for r in resultados_t if r.requiere_revision),
        total_completa=cuenta(EstadoControlConsolidado.COMPLETA),
        total_con_diferencia=cuenta(EstadoControlConsolidado.CON_DIFERENCIA),
        total_sin_movimiento_financiero=cuenta(EstadoControlConsolidado.SIN_MOVIMIENTO_FINANCIERO),
        total_solo_movimiento_financiero=cuenta(EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO),
        total_sin_venta_oficial=cuenta(EstadoControlConsolidado.SIN_VENTA_OFICIAL),
        total_sin_costo_producto=cuenta(EstadoControlConsolidado.SIN_COSTO_PRODUCTO),
        total_en_revision_financiera=cuenta(EstadoControlConsolidado.EN_REVISION_FINANCIERA),
        total_duplicada_o_ambigua=cuenta(EstadoControlConsolidado.DUPLICADA_O_AMBIGUA),
        suma_total_informado_ml=sum((r.total_informado_ml or _ZERO for r in resultados_t), _ZERO),
        suma_neto_aprobado_mp=sum((r.neto_aprobado_mp or _ZERO for r in resultados_t), _ZERO),
        suma_costo_productos_eccomapp=sum((r.costo_productos_eccomapp or _ZERO for r in resultados_t), _ZERO),
    )
