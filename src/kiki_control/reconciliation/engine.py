"""Motor puro de conciliación Mercado Libre / Mercado Pago por ID Order."""

from collections import Counter
from datetime import datetime, UTC
from decimal import Decimal
from typing import Sequence

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.financial_movement import MovimientoFinanciero, TipoOperacionFinanciera
from kiki_control.domain.reconciliation import (
    EstadoConciliacion,
    MotivoConciliacion,
    ReporteConciliacion,
    ResultadoConciliacion,
    VERSION_REGLA_CONCILIACION,
)
from kiki_control.reconciliation.grouping import agrupar_por_id_orden
from kiki_control.reconciliation.rules import clasificar_diferencia, elegir_estado_por_prioridad, validar_tolerancia

ZERO = Decimal("0")
DEVOLUCIONES = {TipoOperacionFinanciera.DEVOLUCION_DINERO, TipoOperacionFinanciera.DEVOLUCION_ENVIO}
RECLAMOS_DISPUTAS = {TipoOperacionFinanciera.RECLAMO, TipoOperacionFinanciera.DISPUTA_ENVIO}
CONTROL_PRINCIPAL = {TipoOperacionFinanciera.PAGO_APROBADO, TipoOperacionFinanciera.PAGO_ENVIO, *DEVOLUCIONES, *RECLAMOS_DISPUTAS}


def reconciliar(
    operaciones_comerciales: Sequence[OperacionComercial],
    movimientos_financieros: Sequence[MovimientoFinanciero],
    tolerancia: Decimal = Decimal("0.01"),
) -> ReporteConciliacion:
    """Concilia modelos normalizados sin leer archivos ni depender de interfaz."""

    validar_tolerancia(tolerancia)
    operaciones = tuple(operaciones_comerciales)
    movimientos = tuple(movimientos_financieros)
    fecha = datetime.now(UTC)
    grupos = agrupar_por_id_orden(operaciones, movimientos)
    resultados = [
        _resultado_para_orden(
            id_orden,
            grupos.operaciones_por_orden.get(id_orden, ()),
            grupos.movimientos_por_orden.get(id_orden, ()),
            tolerancia,
            fecha,
        )
        for id_orden in grupos.ids_orden
    ]
    resultados.extend(_resultado_para_movimiento_sin_orden(m, tolerancia, fecha) for m in grupos.movimientos_sin_orden)
    return ReporteConciliacion(
        resultados=tuple(resultados),
        fecha_procesamiento_utc=fecha,
        version_regla=VERSION_REGLA_CONCILIACION,
        tolerancia=tolerancia,
        cantidad_operaciones_comerciales=len(operaciones),
        cantidad_movimientos_financieros=len(movimientos),
    )


def _resultado_para_orden(id_orden: str, operaciones: tuple[OperacionComercial, ...], movimientos: tuple[MovimientoFinanciero, ...], tolerancia: Decimal, fecha: datetime) -> ResultadoConciliacion:
    pagos = tuple(m for m in movimientos if m.tipo_operacion == TipoOperacionFinanciera.PAGO_APROBADO)
    neto_comercial = operaciones[0].monto_neto_mercado_pago_informado if len(operaciones) == 1 else None
    utilidad = operaciones[0].utilidad_neta_informada if len(operaciones) == 1 else None
    neto_pagos = _sumar(pagos) if pagos else None
    diferencia = (neto_pagos - neto_comercial) if neto_pagos is not None and neto_comercial is not None else None

    motivos: list[MotivoConciliacion] = []
    explicaciones: list[str] = []
    candidatos: set[EstadoConciliacion] = set()

    if len(operaciones) > 1:
        motivos.append(MotivoConciliacion.OPERACION_COMERCIAL_DUPLICADA)
        candidatos.add(EstadoConciliacion.DUPLICADA)
        explicaciones.append("Se detectó más de una operación comercial para el mismo ID Order; no se suman automáticamente.")
    if _tiene_duplicados_financieros(movimientos):
        motivos.append(MotivoConciliacion.MOVIMIENTO_FINANCIERO_DUPLICADO)
        candidatos.add(EstadoConciliacion.DUPLICADA)
        explicaciones.append("Se repite la clave técnica financiera (id_operacion_mercado_pago, tipo_operacion).")
    if len(pagos) > 1:
        motivos.append(MotivoConciliacion.PAGO_DIVIDIDO)
        explicaciones.append("La orden tiene más de un pago aprobado; se suma su neto para el control principal.")

    _agregar_componentes(movimientos, motivos, explicaciones, candidatos)

    if not operaciones:
        motivos.append(MotivoConciliacion.SIN_OPERACION_COMERCIAL)
        candidatos.add(EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL)
        explicaciones.append("Existe movimiento financiero con ID Order sin operación comercial normalizada asociada.")
    elif not movimientos:
        motivos.append(MotivoConciliacion.SIN_MOVIMIENTO_FINANCIERO)
        candidatos.add(EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO)
        explicaciones.append("Existe operación comercial normalizada sin movimientos financieros asociados.")
    elif diferencia is not None:
        estado_diferencia = clasificar_diferencia(diferencia, tolerancia)
        candidatos.add(estado_diferencia)
        if estado_diferencia == EstadoConciliacion.CONCILIADA:
            motivos.append(MotivoConciliacion.COINCIDENCIA_NETA_EXACTA)
            explicaciones.append("El neto de pagos aprobados coincide exactamente con el neto comercial informado.")
        elif estado_diferencia == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR:
            motivos.append(MotivoConciliacion.DIFERENCIA_DENTRO_TOLERANCIA)
            explicaciones.append("La diferencia de control es distinta de cero pero está dentro de la tolerancia configurada.")
        else:
            motivos.append(MotivoConciliacion.DIFERENCIA_SUPERA_TOLERANCIA)
            explicaciones.append("La diferencia de control supera la tolerancia configurada.")

    estado = elegir_estado_por_prioridad(candidatos)
    requiere_revision = estado in {EstadoConciliacion.DUPLICADA, EstadoConciliacion.EN_REVISION, EstadoConciliacion.EN_RECLAMO, EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL, EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO}
    return _crear_resultado(id_orden, operaciones, movimientos, fecha, tolerancia, estado, tuple(dict.fromkeys(motivos)), tuple(explicaciones), requiere_revision, len(pagos) > 1, neto_comercial, neto_pagos, diferencia, utilidad)


def _agregar_componentes(movimientos: tuple[MovimientoFinanciero, ...], motivos: list[MotivoConciliacion], explicaciones: list[str], candidatos: set[EstadoConciliacion]) -> None:
    if any(m.tipo_operacion in DEVOLUCIONES for m in movimientos):
        motivos.append(MotivoConciliacion.DEVOLUCION_DETECTADA); candidatos.add(EstadoConciliacion.DEVUELTA); explicaciones.append("Se detectó devolución; se conserva su impacto separado sin recalcular utilidad.")
    if any(m.tipo_operacion == TipoOperacionFinanciera.RECLAMO for m in movimientos):
        motivos.append(MotivoConciliacion.RECLAMO_DETECTADO); candidatos.add(EstadoConciliacion.EN_RECLAMO); explicaciones.append("Se detectó reclamo; requiere revisión manual.")
    if any(m.tipo_operacion == TipoOperacionFinanciera.DISPUTA_ENVIO for m in movimientos):
        motivos.append(MotivoConciliacion.DISPUTA_DETECTADA); candidatos.add(EstadoConciliacion.EN_RECLAMO); explicaciones.append("Se detectó disputa de envío; requiere revisión manual.")
    if any(m.tipo_operacion == TipoOperacionFinanciera.DESCONOCIDA for m in movimientos):
        motivos.append(MotivoConciliacion.MOVIMIENTO_DESCONOCIDO); candidatos.add(EstadoConciliacion.EN_REVISION); explicaciones.append("Se detectó un tipo de movimiento desconocido; no se fuerza conciliación.")
    if any(m.tipo_operacion == TipoOperacionFinanciera.PAGO_APROBADO and m.fecha_liquidacion_utc is None for m in movimientos):
        motivos.append(MotivoConciliacion.LIQUIDACION_PENDIENTE); candidatos.add(EstadoConciliacion.PENDIENTE_ACREDITACION); explicaciones.append("Hay pago aprobado sin fecha de liquidación; se marca pendiente de acreditación si no hay prioridad mayor.")


def _resultado_para_movimiento_sin_orden(movimiento: MovimientoFinanciero, tolerancia: Decimal, fecha: datetime) -> ResultadoConciliacion:
    es_payout = movimiento.tipo_operacion == TipoOperacionFinanciera.PAYOUT
    estado = EstadoConciliacion.MOVIMIENTO_DE_FONDOS if es_payout else EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL
    motivos = (MotivoConciliacion.PAYOUT_SIN_ORDEN,) if es_payout else (MotivoConciliacion.ORDEN_AUSENTE,)
    explicacion = "PAYOUT sin ID Order tratado como movimiento de fondos, no como pérdida comercial." if es_payout else "Movimiento financiero sin ID Order; se conserva individualmente sin contraparte comercial."
    return _crear_resultado(None, (), (movimiento,), fecha, tolerancia, estado, motivos, (explicacion,), not es_payout, False, None, None, None, None)


def _crear_resultado(id_orden: str | None, operaciones: tuple[OperacionComercial, ...], movimientos: tuple[MovimientoFinanciero, ...], fecha: datetime, tolerancia: Decimal, estado: EstadoConciliacion, motivos: tuple[MotivoConciliacion, ...], explicaciones: tuple[str, ...], requiere_revision: bool, es_pago_dividido: bool, neto_comercial: Decimal | None, neto_pagos: Decimal | None, diferencia: Decimal | None, utilidad: Decimal | None) -> ResultadoConciliacion:
    return ResultadoConciliacion(
        id_orden=id_orden,
        hashes_importacion_comercial=tuple(o.hash_importacion for o in operaciones),
        hashes_importacion_financiera=tuple(m.hash_importacion for m in movimientos),
        numeros_fila_comercial=tuple(o.numero_fila_origen for o in operaciones),
        numeros_fila_financiera=tuple(m.numero_fila_origen for m in movimientos),
        fecha_procesamiento_utc=fecha,
        version_regla=VERSION_REGLA_CONCILIACION,
        estado=estado,
        motivos=motivos,
        explicaciones=explicaciones,
        requiere_revision=requiere_revision,
        es_pago_dividido=es_pago_dividido,
        cantidad_operaciones_comerciales=len(operaciones),
        cantidad_movimientos_financieros=len(movimientos),
        cantidad_pagos_aprobados=sum(1 for m in movimientos if m.tipo_operacion == TipoOperacionFinanciera.PAGO_APROBADO),
        neto_comercial_informado=neto_comercial,
        neto_pagos_aprobados=neto_pagos,
        diferencia_control=diferencia,
        impacto_pagos_envio=_sumar(m for m in movimientos if m.tipo_operacion == TipoOperacionFinanciera.PAGO_ENVIO),
        impacto_devoluciones=_sumar(m for m in movimientos if m.tipo_operacion in DEVOLUCIONES),
        impacto_reclamos_disputas=_sumar(m for m in movimientos if m.tipo_operacion in RECLAMOS_DISPUTAS),
        impacto_otros=_sumar(m for m in movimientos if m.tipo_operacion not in CONTROL_PRINCIPAL),
        neto_financiero_total=_sumar(movimientos),
        utilidad_neta_informada=utilidad,
        tolerancia_aplicada=tolerancia,
        tiene_devolucion=any(m.tipo_operacion in DEVOLUCIONES for m in movimientos),
        tiene_reclamo=any(m.tipo_operacion == TipoOperacionFinanciera.RECLAMO for m in movimientos),
        tiene_disputa=any(m.tipo_operacion == TipoOperacionFinanciera.DISPUTA_ENVIO for m in movimientos),
        tiene_pago_envio=any(m.tipo_operacion == TipoOperacionFinanciera.PAGO_ENVIO for m in movimientos),
        tiene_movimiento_desconocido=any(m.tipo_operacion == TipoOperacionFinanciera.DESCONOCIDA for m in movimientos),
        tiene_liquidacion_pendiente=any(m.tipo_operacion == TipoOperacionFinanciera.PAGO_APROBADO and m.fecha_liquidacion_utc is None for m in movimientos),
        tiene_duplicados=len(operaciones) > 1 or _tiene_duplicados_financieros(movimientos),
    )


def _sumar(movimientos) -> Decimal:
    total = ZERO
    for movimiento in movimientos:
        total += movimiento.monto_neto_impactado
    return total


def _tiene_duplicados_financieros(movimientos: tuple[MovimientoFinanciero, ...]) -> bool:
    claves = Counter((m.id_operacion_mercado_pago, m.tipo_operacion) for m in movimientos)
    return any(cantidad > 1 for cantidad in claves.values())
