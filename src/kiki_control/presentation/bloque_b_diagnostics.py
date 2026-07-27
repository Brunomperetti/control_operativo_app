"""Diagnósticos puros para Bloque B — Conciliación entre el neto ML y Mercado Pago.

Capa sin dependencias de UI ni procesamiento tabular externo.
Trabaja sobre modelos de dominio inmutables y Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable, Mapping

from kiki_control.domain.control_consolidado import (
    ReporteControlConsolidado,
    ResultadoControlConsolidado,
    TipoMovimientoFinanciero,
)
from kiki_control.domain.financial_movement import TratamientoNetoComparable

_ZERO = Decimal("0")


def clasificacion_normalizada_movimiento_mp(movimiento: Any) -> str:
    """Devuelve el tipo normalizado real del movimiento MP como clasificación visible.

    ``MovimientoFinanciero`` no tiene un campo de estado independiente: su
    clasificación normalizada está en ``tipo_operacion``. Se evita inferir una
    clasificación a partir de la fecha de aprobación.
    """
    tipo = getattr(movimiento, "tipo_operacion", None)
    valor = getattr(tipo, "value", tipo)
    texto = str(valor).strip() if valor is not None else ""
    return texto or "Sin clasificación"


def clasificaciones_movimientos_mp_por_fila(movimientos: Iterable[Any]) -> dict[int, str]:
    """Indexa la clasificación normalizada real de cada movimiento por su fila fuente."""
    return {
        numero_fila: clasificacion_normalizada_movimiento_mp(movimiento)
        for movimiento in movimientos
        if (numero_fila := getattr(movimiento, "numero_fila_origen", None)) is not None
    }


def tratamientos_movimientos_mp_por_fila(
    movimientos: Iterable[Any],
) -> dict[int, TratamientoNetoComparable]:
    """Indexa el tratamiento normalizado sin inferirlo desde nombres visibles."""
    return {
        numero_fila: tratamiento
        for movimiento in movimientos
        if (numero_fila := getattr(movimiento, "numero_fila_origen", None)) is not None
        and (tratamiento := getattr(movimiento, "tratamiento_neto_comparable", None)) is not None
    }


class EstadoExplicacionDiferencia(StrEnum):
    """Estado de explicación de una diferencia ML–MP."""

    EXPLICADA = "EXPLICADA"
    INDICIO_TEMPORAL = "INDICIO_TEMPORAL"
    INDICIO_FINANCIERO = "INDICIO_FINANCIERO"
    PENDIENTE_DE_CLASIFICACION = "PENDIENTE_DE_CLASIFICACION"


ESTADOS_EXPLICACION_VISIBLES: dict[EstadoExplicacionDiferencia, str] = {
    EstadoExplicacionDiferencia.EXPLICADA: "Explicada",
    EstadoExplicacionDiferencia.INDICIO_TEMPORAL: "Posible diferencia temporal",
    EstadoExplicacionDiferencia.INDICIO_FINANCIERO: "Posible diferencia por movimientos financieros",
    EstadoExplicacionDiferencia.PENDIENTE_DE_CLASIFICACION: "Pendiente de clasificación",
}


@dataclass(frozen=True)
class DetalleMovimientoMp:
    """Detalle inmutable de un movimiento MP individual asociado a un grupo con diferencia."""

    id_movimiento_mp: str
    id_orden: str
    tipo_movimiento: str
    clasificacion_normalizada: str
    tratamiento_neto_comparable: TratamientoNetoComparable | None
    fecha_origen: str
    fecha_aprobacion: str
    fecha_liquidacion: str
    monto_neto_impactado: Decimal | None
    fila_origen: int


@dataclass(frozen=True)
class GrupoConDiferencia:
    """Grupo comparable con diferencia ML–MP que supera la tolerancia."""

    id_grupo: str
    ids_orden: tuple[str, ...]
    fecha_venta_ml: str
    total_informado_ml: Decimal
    neto_aprobado_mp: Decimal
    impacto_reclamos_disputas_mp: Decimal
    impacto_devoluciones_mp: Decimal
    impacto_pagos_envio_mp: Decimal
    impacto_otros_mp: Decimal
    neto_financiero_total_mp: Decimal
    diferencia_ml_mp: Decimal
    cantidad_movimientos_mp: int
    fecha_min_origen_mp: str
    fecha_max_origen_mp: str
    fecha_min_liquidacion: str
    fecha_max_liquidacion: str
    tipos_movimientos: tuple[str, ...]
    estado_explicacion: EstadoExplicacionDiferencia
    motivo_visible: str
    motivos_secundarios: tuple[str, ...]
    accion_recomendada: str
    movimientos_asociados: tuple[DetalleMovimientoMp, ...]


@dataclass(frozen=True)
class MovimientoMpSinVentaML:
    """Grupo MP con Mercado Pago presente y sin venta oficial ML (excluye payouts y fondos)."""

    id_grupo: str
    ids_movimiento_mp: tuple[str, ...]
    tipos_movimiento: tuple[str, ...]
    fecha_min_origen: str
    fecha_max_liquidacion: str
    neto_aprobado_mp: Decimal | None
    neto_financiero_total_mp: Decimal | None
    categoria_temporal: str
    motivo_sin_venta: str
    accion_recomendada: str


@dataclass(frozen=True)
class ResumenBloqueB:
    """Resumen compacto de Bloque B para presentación."""

    comparables_totales: int
    coincidencias: int
    con_diferencia: int
    neto_ml_comparable: Decimal
    neto_mp_comparable: Decimal
    diferencia_universo_comparable: Decimal
    """Diferencia neto_mp − neto_ml para TODOS los grupos comparables (incluye los dentro de tolerancia)."""
    diferencia_operaciones_fuera_tolerancia: Decimal
    """Suma de diferencia_ml_mp solo para los grupos cuya diferencia absoluta supera la tolerancia."""
    diferencia_subuniverso_conciliado: Decimal
    """Diferencia agregada real de los grupos dentro de tolerancia (puede ser distinta de cero)."""


@dataclass(frozen=True)
class DiagnosticoBloqueB:
    """Diagnóstico completo de Bloque B, auditable e inmutable."""

    resumen: ResumenBloqueB
    grupos_con_diferencia: tuple[GrupoConDiferencia, ...]
    cantidad_mp_sin_venta: int
    """Operaciones/movimientos MP sin venta oficial ML (excluye payouts y movimientos de fondos)."""
    neto_aprobado_mp_sin_venta: Decimal
    neto_financiero_total_mp_sin_venta: Decimal
    movimientos_mp_sin_venta: tuple[MovimientoMpSinVentaML, ...]
    cantidad_movimientos_fondos: int
    """Payouts y movimientos de fondos: no son ventas faltantes."""
    neto_aprobado_mp_fondos: Decimal
    neto_financiero_total_mp_fondos: Decimal
    movimientos_fondos: tuple[MovimientoMpSinVentaML, ...]
    grupos_movimientos_asociados: tuple[tuple[str, tuple[DetalleMovimientoMp, ...]], ...]
    """Detalle individual de todos los grupos MP, aun cuando concilien sin diferencia."""
    suma_diferencias_individuales: Decimal
    coherencia_suma_diferencias: bool
    """Verifica que suma_diferencias_individuales == diferencia_operaciones_fuera_tolerancia."""


# ---------------------------------------------------------------------------
# Funciones puras de clasificación
# ---------------------------------------------------------------------------

def _as_date(v: date | datetime | None) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    return v


def _sum_decimals(valores: Iterable[Decimal | None]) -> Decimal:
    total = _ZERO
    for v in valores:
        if v is not None:
            total += v
    return total


def clasificar_diferencia(
    r: ResultadoControlConsolidado,
    fecha_venta_ml: date | None = None,
    fecha_min_liquidacion: date | None = None,
    fecha_max_liquidacion: date | None = None,
) -> tuple[EstadoExplicacionDiferencia, str, tuple[str, ...]]:
    """Clasifica la diferencia ML–MP de un grupo comparable.

    Reglas prudentes (ninguna asumir causa sin evidencia suficiente):

    1. EXPLICADA: los impactos financieros identificados suman exactamente la
       diferencia dentro de la tolerancia.
    2. INDICIO_FINANCIERO: hay devoluciones, reclamos, disputas o envíos
       que pueden afectar el neto, pero no se verifica identidad monetaria.
    3. INDICIO_TEMPORAL: la liquidación ocurrió después de la venta y esa
       temporalidad puede afectar la interpretación; no implica error.
    4. PENDIENTE_DE_CLASIFICACION: ninguna regla explica la diferencia.

    Devuelve (estado_principal, motivo_visible, motivos_secundarios).
    """
    diferencia = r.diferencia_ml_mp
    if diferencia is None:
        return (
            EstadoExplicacionDiferencia.PENDIENTE_DE_CLASIFICACION,
            "Sin datos suficientes para clasificar",
            (),
        )

    ind = r.indicadores_financieros
    motivos_sec: list[str] = []

    # Recopilar indicios financieros
    if ind.tiene_devolucion:
        motivos_sec.append("Devolución detectada")
    if ind.tiene_reclamo:
        motivos_sec.append("Reclamo detectado")
    if ind.tiene_disputa:
        motivos_sec.append("Disputa detectada")
    if ind.tiene_pago_envio:
        motivos_sec.append("Movimiento de envío detectado")

    # Recopilar indicios temporales
    tiene_indicio_temporal = False
    if fecha_min_liquidacion is not None and fecha_venta_ml is not None:
        if fecha_min_liquidacion > fecha_venta_ml:
            tiene_indicio_temporal = True
            motivos_sec.append("Liquidación posterior a la fecha de venta")

    # Regla 1 — EXPLICADA: suma de impactos identificables ≈ diferencia
    impacto_total = _sum_decimals([
        r.impacto_devoluciones_mp,
        r.impacto_reclamos_disputas_mp,
        r.impacto_pagos_envio_mp,
        r.impacto_otros_mp,
    ])
    tiene_impactos = impacto_total != _ZERO
    if tiene_impactos and abs(impacto_total - diferencia) <= r.tolerancia:
        return (
            EstadoExplicacionDiferencia.EXPLICADA,
            "Diferencia explicada por movimientos financieros identificados",
            tuple(motivos_sec),
        )

    # Regla 3 — INDICIO_FINANCIERO: indicadores presentes pero sin identidad monetaria
    if ind.tiene_devolucion or ind.tiene_reclamo or ind.tiene_disputa or ind.tiene_pago_envio:
        return (
            EstadoExplicacionDiferencia.INDICIO_FINANCIERO,
            "Movimientos financieros que pueden afectar el neto sin identidad monetaria confirmada",
            tuple(motivos_sec),
        )

    # Regla 2 — INDICIO_TEMPORAL: liquidación posterior pero sin explicar el importe
    if tiene_indicio_temporal:
        return (
            EstadoExplicacionDiferencia.INDICIO_TEMPORAL,
            "Liquidación posterior al período de venta; no implica error por sí sola",
            tuple(motivos_sec),
        )

    # Regla 4 — PENDIENTE
    return (
        EstadoExplicacionDiferencia.PENDIENTE_DE_CLASIFICACION,
        "Sin elementos identificados que expliquen la diferencia",
        tuple(motivos_sec),
    )


def _accion_recomendada_diferencia(estado: EstadoExplicacionDiferencia) -> str:
    if estado == EstadoExplicacionDiferencia.EXPLICADA:
        return "Verificar que los movimientos financieros identificados corresponden a esta operación."
    if estado == EstadoExplicacionDiferencia.INDICIO_FINANCIERO:
        return "Revisar devoluciones, reclamos o envíos asociados y confirmar si explican el importe."
    if estado == EstadoExplicacionDiferencia.INDICIO_TEMPORAL:
        return "Revisar si la liquidación fuera del período afecta la interpretación del neto."
    return "Revisar ML oficial, Eccomapp y MP sin asumir causa contable."


def categoria_temporal_mp(
    filas_mp: tuple[int, ...],
    fechas_origen_por_fila: Mapping[int, date | datetime | None],
    inicio_ml: date | None,
    fin_ml: date | None,
) -> str:
    """Clasifica la categoría temporal de un grupo MP según el período ML.

    Categorías:
    - Anterior al período ML
    - Dentro del período ML
    - Posterior al período ML
    - Sin fecha
    - Fechas mixtas
    """
    if not filas_mp or inicio_ml is None or fin_ml is None:
        return "Sin fecha"

    categorias: set[str] = set()
    for fila in filas_mp:
        fecha = _as_date(fechas_origen_por_fila.get(fila))
        if fecha is None:
            categorias.add("Sin fecha")
        elif fecha < inicio_ml:
            categorias.add("Anterior al período ML")
        elif fecha > fin_ml:
            categorias.add("Posterior al período ML")
        else:
            categorias.add("Dentro del período ML")

    if not categorias:
        return "Sin fecha"
    if len(categorias) == 1:
        return next(iter(categorias))
    return "Fechas mixtas"


def _motivo_sin_venta_ml(r: ResultadoControlConsolidado) -> str:
    """Determina el motivo por el que no se encontró venta ML para un grupo MP."""
    ind = r.indicadores_financieros
    tipo = r.tipo_movimiento_financiero

    if tipo == TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS:
        return "Payout o movimiento de fondos — no es una venta"
    if ind.tiene_devolucion:
        return "Devolución o reembolso sin orden ML asociada"
    if ind.tiene_reclamo or ind.tiene_disputa:
        return "Reclamo o disputa sin orden ML asociada"
    if ind.tiene_pago_envio:
        return "Movimiento de envío sin venta ML asociada"
    return "Orden MP sin venta oficial ML encontrada en el período cargado"


def _accion_recomendada_sin_venta(r: ResultadoControlConsolidado) -> str:
    ind = r.indicadores_financieros
    tipo = r.tipo_movimiento_financiero

    if tipo == TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS:
        return "No presentar como venta faltante; es un movimiento de fondos."
    if ind.tiene_devolucion:
        return "Verificar si la devolución corresponde a una venta fuera del período cargado."
    if ind.tiene_reclamo or ind.tiene_disputa:
        return "Verificar si el reclamo o disputa corresponde a una orden fuera del período."
    return "Verificar cobertura de archivos y si la orden pertenece al período cargado."


def _id_grupo(r: ResultadoControlConsolidado) -> str:
    if r.id_grupo_canonico:
        return r.id_grupo_canonico
    if r.ids_orden:
        return ", ".join(r.ids_orden)
    if r.filas_origen_mp:
        return f"fila MP {','.join(map(str, r.filas_origen_mp))}"
    return r.clave_resultado


def _fecha_str(d: date | datetime | None) -> str:
    if d is None:
        return "Sin fecha"
    if hasattr(d, "date"):
        d = d.date()
    return d.strftime("%d/%m/%Y")


def _fechas_rango(
    filas: tuple[int, ...],
    fechas_por_fila: Mapping[int, date | datetime | None],
) -> tuple[str, str]:
    """Devuelve (mínimo, máximo) formateados para las filas dadas."""
    fechas = [_as_date(fechas_por_fila.get(f)) for f in filas]
    fechas_valid = [f for f in fechas if f is not None]
    if not fechas_valid:
        return "Sin fecha", "Sin fecha"
    return _fecha_str(min(fechas_valid)), _fecha_str(max(fechas_valid))


def _tipos_movimiento_para_filas(
    filas: tuple[int, ...],
    tipos_por_fila: Mapping[int, str],
) -> tuple[str, ...]:
    tipos = sorted({tipos_por_fila[f] for f in filas if f in tipos_por_fila})
    return tuple(tipos) if tipos else ("Sin tipo",)


def _ids_operacion_para_filas(
    filas: tuple[int, ...],
    ids_por_fila: Mapping[int, str],
) -> tuple[str, ...]:
    ids = [ids_por_fila[f] for f in filas if f in ids_por_fila]
    return tuple(ids) if ids else ()


def _construir_detalle_movimientos(
    filas_mp: tuple[int, ...],
    ids_op: Mapping[int, str],
    ids_orden: Mapping[int, str | None],
    tipos: Mapping[int, str],
    fechas_origen: Mapping[int, date | datetime | None],
    fechas_aprobacion: Mapping[int, date | datetime | None],
    fechas_liq: Mapping[int, date | datetime | None],
    montos_neto: Mapping[int, Decimal | None],
    clasificaciones: Mapping[int, str],
    tratamientos: Mapping[int, TratamientoNetoComparable],
) -> tuple[DetalleMovimientoMp, ...]:
    """Construye la tupla de detalle de movimientos MP para las filas dadas."""
    detalles: list[DetalleMovimientoMp] = []
    for fila in filas_mp:
        tipo_mov = tipos.get(fila, "Sin tipo")
        detalles.append(DetalleMovimientoMp(
            id_movimiento_mp=ids_op.get(fila, "—"),
            id_orden=ids_orden.get(fila) or "—",
            tipo_movimiento=tipo_mov,
            clasificacion_normalizada=clasificaciones.get(fila, "Sin clasificación"),
            tratamiento_neto_comparable=tratamientos.get(fila),
            fecha_origen=_fecha_str(_as_date(fechas_origen.get(fila))),
            fecha_aprobacion=_fecha_str(_as_date(fechas_aprobacion.get(fila))),
            fecha_liquidacion=_fecha_str(_as_date(fechas_liq.get(fila))),
            monto_neto_impactado=montos_neto.get(fila),
            fila_origen=fila,
        ))
    return tuple(detalles)


# ---------------------------------------------------------------------------
# Función principal de diagnóstico
# ---------------------------------------------------------------------------

def diagnosticar_bloque_b(
    reporte: ReporteControlConsolidado,
    inicio_ml: date | datetime | None = None,
    fin_ml: date | datetime | None = None,
    fechas_origen_mp_por_fila: Mapping[int, date | datetime | None] | None = None,
    fechas_liquidacion_mp_por_fila: Mapping[int, date | datetime | None] | None = None,
    tipos_movimiento_mp_por_fila: Mapping[int, str] | None = None,
    ids_operacion_mp_por_fila: Mapping[int, str] | None = None,
    fechas_venta_ml_por_fila: Mapping[int, date | datetime | None] | None = None,
    ids_orden_mp_por_fila: Mapping[int, str | None] | None = None,
    fechas_aprobacion_mp_por_fila: Mapping[int, date | datetime | None] | None = None,
    montos_neto_mp_por_fila: Mapping[int, Decimal | None] | None = None,
    clasificaciones_mp_por_fila: Mapping[int, str] | None = None,
    tratamientos_mp_por_fila: Mapping[int, TratamientoNetoComparable] | None = None,
) -> DiagnosticoBloqueB:
    """Genera el diagnóstico completo de Bloque B.

    Universo MP sin venta ML: resultados donde tiene_mercado_pago == True y
    tiene_mercado_libre_oficial == False. Los resultados con
    tipo_movimiento_financiero == MOVIMIENTO_DE_FONDOS se segregan en el bucket
    de fondos/payouts y nunca se presentan como ventas faltantes.

    Parámetros de enriquecimiento opcionales:
    - fechas_origen_mp_por_fila: fila MP → fecha de origen
    - fechas_liquidacion_mp_por_fila: fila MP → fecha de liquidación
    - tipos_movimiento_mp_por_fila: fila MP → tipo normalizado de movimiento (str)
    - ids_operacion_mp_por_fila: fila MP → ID de operación MP
    - fechas_venta_ml_por_fila: fila ML → fecha de venta
    - ids_orden_mp_por_fila: fila MP → ID de orden ML asociado (puede ser None)
    - fechas_aprobacion_mp_por_fila: fila MP → fecha de aprobación
    - montos_neto_mp_por_fila: fila MP → monto neto impactado
    - tratamientos_mp_por_fila: fila MP → semántica normalizada para el neto comparable
    """
    inicio = _as_date(inicio_ml)
    fin = _as_date(fin_ml)
    fechas_origen = fechas_origen_mp_por_fila or {}
    fechas_liq = fechas_liquidacion_mp_por_fila or {}
    tipos = tipos_movimiento_mp_por_fila or {}
    ids_op = ids_operacion_mp_por_fila or {}
    fechas_ml = fechas_venta_ml_por_fila or {}
    ids_orden_mp = ids_orden_mp_por_fila or {}
    fechas_aprobacion = fechas_aprobacion_mp_por_fila or {}
    montos_neto = montos_neto_mp_por_fila or {}
    clasificaciones = clasificaciones_mp_por_fila or {}
    tratamientos = tratamientos_mp_por_fila or {}

    # --- Universo comparable (ML + MP) ---
    comparables = tuple(
        r for r in reporte.resultados
        if r.total_informado_ml is not None and r.neto_financiero_total_mp is not None
    )
    diferencias_r = tuple(
        r for r in comparables
        if r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > reporte.tolerancia
    )
    dentro_tolerancia_r = tuple(r for r in comparables if r not in set(diferencias_r))

    neto_ml = _sum_decimals(r.total_informado_ml for r in comparables)
    neto_mp = _sum_decimals(r.neto_financiero_total_mp for r in comparables)
    diferencia_universo = neto_mp - neto_ml

    # Diferencia real del subuniverso conciliado (grupos dentro de tolerancia)
    dif_conciliado = _sum_decimals(
        r.diferencia_ml_mp for r in dentro_tolerancia_r if r.diferencia_ml_mp is not None
    )

    # Diferencia de las operaciones fuera de tolerancia
    dif_fuera_tolerancia = _sum_decimals(
        r.diferencia_ml_mp for r in diferencias_r if r.diferencia_ml_mp is not None
    )

    resumen = ResumenBloqueB(
        comparables_totales=len(comparables),
        coincidencias=len(dentro_tolerancia_r),
        con_diferencia=len(diferencias_r),
        neto_ml_comparable=neto_ml,
        neto_mp_comparable=neto_mp,
        diferencia_universo_comparable=diferencia_universo,
        diferencia_operaciones_fuera_tolerancia=dif_fuera_tolerancia,
        diferencia_subuniverso_conciliado=dif_conciliado,
    )

    # --- Grupos con diferencia ---
    grupos_con_dif: list[GrupoConDiferencia] = []
    for r in diferencias_r:
        id_g = _id_grupo(r)

        # Fecha de venta ML (desde las filas ML)
        fechas_venta = [_as_date(fechas_ml.get(f)) for f in r.filas_origen_ml]
        fechas_venta_valid = [f for f in fechas_venta if f is not None]
        fecha_venta_ml_val: date | None = min(fechas_venta_valid) if fechas_venta_valid else None

        # Rango de origen MP
        f_min_origen, f_max_origen = _fechas_rango(r.filas_origen_mp, fechas_origen)

        # Rango de liquidación
        f_min_liq, f_max_liq = _fechas_rango(r.filas_origen_mp, fechas_liq)

        # Clasificar diferencia
        fecha_min_liq_d = _as_date(
            min(
                (v for v in (fechas_liq.get(f) for f in r.filas_origen_mp) if v is not None),
                default=None,
            )
        )
        estado_expl, motivo_vis, motivos_sec = clasificar_diferencia(
            r,
            fecha_venta_ml=fecha_venta_ml_val,
            fecha_min_liquidacion=fecha_min_liq_d,
            fecha_max_liquidacion=_as_date(
                max(
                    (v for v in (fechas_liq.get(f) for f in r.filas_origen_mp) if v is not None),
                    default=None,
                )
            ),
        )

        movimientos_asociados = _construir_detalle_movimientos(
            r.filas_origen_mp, ids_op, ids_orden_mp, tipos,
            fechas_origen, fechas_aprobacion, fechas_liq, montos_neto,
            clasificaciones, tratamientos,
        )

        grupos_con_dif.append(GrupoConDiferencia(
            id_grupo=id_g,
            ids_orden=r.ids_orden,
            fecha_venta_ml=_fecha_str(fecha_venta_ml_val),
            total_informado_ml=r.total_informado_ml,  # type: ignore[arg-type]
            neto_aprobado_mp=r.neto_aprobado_mp,  # type: ignore[arg-type]
            impacto_reclamos_disputas_mp=r.impacto_reclamos_disputas_mp or _ZERO,
            impacto_devoluciones_mp=r.impacto_devoluciones_mp or _ZERO,
            impacto_pagos_envio_mp=r.impacto_pagos_envio_mp or _ZERO,
            impacto_otros_mp=r.impacto_otros_mp or _ZERO,
            neto_financiero_total_mp=r.neto_financiero_total_mp,  # type: ignore[arg-type]
            diferencia_ml_mp=r.diferencia_ml_mp,  # type: ignore[arg-type]
            cantidad_movimientos_mp=len(r.filas_origen_mp),
            fecha_min_origen_mp=f_min_origen,
            fecha_max_origen_mp=f_max_origen,
            fecha_min_liquidacion=f_min_liq,
            fecha_max_liquidacion=f_max_liq,
            tipos_movimientos=_tipos_movimiento_para_filas(r.filas_origen_mp, tipos),
            estado_explicacion=estado_expl,
            motivo_visible=motivo_vis,
            motivos_secundarios=motivos_sec,
            accion_recomendada=_accion_recomendada_diferencia(estado_expl),
            movimientos_asociados=movimientos_asociados,
        ))

    grupos_movimientos = tuple(
        (
            _id_grupo(r),
            _construir_detalle_movimientos(
                r.filas_origen_mp, ids_op, ids_orden_mp, tipos,
                fechas_origen, fechas_aprobacion, fechas_liq, montos_neto,
                clasificaciones, tratamientos,
            ),
        )
        for r in reporte.resultados
        if r.tiene_mercado_pago
    )

    # --- Universo MP sin venta ML (por presencia real de fuentes) ---
    # Incluye SOLO_MOVIMIENTO_FINANCIERO, SIN_VENTA_OFICIAL y cualquier estado
    # donde tiene_mercado_pago == True y tiene_mercado_libre_oficial == False.
    mp_sin_ml_todos = tuple(
        r for r in reporte.resultados
        if r.tiene_mercado_pago and not r.tiene_mercado_libre_oficial
    )

    # Separar fondos/payouts de ventas faltantes
    fondos_r = tuple(
        r for r in mp_sin_ml_todos
        if r.tipo_movimiento_financiero == TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS
    )
    solo_mp = tuple(r for r in mp_sin_ml_todos if r not in set(fondos_r))

    # --- Métricas y listas de ventas faltantes (excluye fondos) ---
    neto_ap_sin_venta = _sum_decimals(r.neto_aprobado_mp for r in solo_mp)
    neto_fin_sin_venta = _sum_decimals(r.neto_financiero_total_mp for r in solo_mp)

    movs_sin_venta: list[MovimientoMpSinVentaML] = []
    for r in solo_mp:
        id_g = _id_grupo(r)
        f_min_orig, _ = _fechas_rango(r.filas_origen_mp, fechas_origen)
        _, f_max_liq_mv = _fechas_rango(r.filas_origen_mp, fechas_liq)
        cat_temp = categoria_temporal_mp(r.filas_origen_mp, fechas_origen, inicio, fin)
        motivo = _motivo_sin_venta_ml(r)
        accion = _accion_recomendada_sin_venta(r)

        movs_sin_venta.append(MovimientoMpSinVentaML(
            id_grupo=id_g,
            ids_movimiento_mp=_ids_operacion_para_filas(r.filas_origen_mp, ids_op),
            tipos_movimiento=_tipos_movimiento_para_filas(r.filas_origen_mp, tipos),
            fecha_min_origen=f_min_orig,
            fecha_max_liquidacion=f_max_liq_mv,
            neto_aprobado_mp=r.neto_aprobado_mp,
            neto_financiero_total_mp=r.neto_financiero_total_mp,
            categoria_temporal=cat_temp,
            motivo_sin_venta=motivo,
            accion_recomendada=accion,
        ))

    # --- Métricas y listas de fondos/payouts ---
    neto_ap_fondos = _sum_decimals(r.neto_aprobado_mp for r in fondos_r)
    neto_fin_fondos = _sum_decimals(r.neto_financiero_total_mp for r in fondos_r)

    movimientos_fondos: list[MovimientoMpSinVentaML] = []
    for r in fondos_r:
        id_g = _id_grupo(r)
        f_min_orig, _ = _fechas_rango(r.filas_origen_mp, fechas_origen)
        _, f_max_liq_mv = _fechas_rango(r.filas_origen_mp, fechas_liq)
        cat_temp = categoria_temporal_mp(r.filas_origen_mp, fechas_origen, inicio, fin)

        movimientos_fondos.append(MovimientoMpSinVentaML(
            id_grupo=id_g,
            ids_movimiento_mp=_ids_operacion_para_filas(r.filas_origen_mp, ids_op),
            tipos_movimiento=_tipos_movimiento_para_filas(r.filas_origen_mp, tipos),
            fecha_min_origen=f_min_orig,
            fecha_max_liquidacion=f_max_liq_mv,
            neto_aprobado_mp=r.neto_aprobado_mp,
            neto_financiero_total_mp=r.neto_financiero_total_mp,
            categoria_temporal=cat_temp,
            motivo_sin_venta=_motivo_sin_venta_ml(r),
            accion_recomendada=_accion_recomendada_sin_venta(r),
        ))

    # Coherencia: suma_diferencias_individuales debe igualar diferencia_operaciones_fuera_tolerancia
    suma_ind = _sum_decimals(g.diferencia_ml_mp for g in grupos_con_dif)
    coherencia = abs(suma_ind - dif_fuera_tolerancia) <= reporte.tolerancia

    return DiagnosticoBloqueB(
        resumen=resumen,
        grupos_con_diferencia=tuple(grupos_con_dif),
        cantidad_mp_sin_venta=len(solo_mp),
        neto_aprobado_mp_sin_venta=neto_ap_sin_venta,
        neto_financiero_total_mp_sin_venta=neto_fin_sin_venta,
        movimientos_mp_sin_venta=tuple(movs_sin_venta),
        cantidad_movimientos_fondos=len(fondos_r),
        neto_aprobado_mp_fondos=neto_ap_fondos,
        neto_financiero_total_mp_fondos=neto_fin_fondos,
        movimientos_fondos=tuple(movimientos_fondos),
        grupos_movimientos_asociados=grupos_movimientos,
        suma_diferencias_individuales=suma_ind,
        coherencia_suma_diferencias=coherencia,
    )
