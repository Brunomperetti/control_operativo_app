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

_COLUMNA_MONTO_MP = "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO"

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


class CategoriaPrincipalMpSinVenta(StrEnum):
    ANTERIOR_AL_PERIODO_ML = "ANTERIOR_AL_PERIODO_ML"
    DENTRO_DEL_PERIODO_ML_SIN_VENTA = "DENTRO_DEL_PERIODO_ML_SIN_VENTA"
    POSTERIOR_AL_PERIODO_ML = "POSTERIOR_AL_PERIODO_ML"
    SIN_FECHA_DE_ORIGEN = "SIN_FECHA_DE_ORIGEN"


class SubclasificacionFinanciera(StrEnum):
    PAGO_APROBADO = "PAGO_APROBADO"
    RECLAMO_O_DISPUTA = "RECLAMO_O_DISPUTA"
    DEVOLUCION = "DEVOLUCION"
    ENVIO = "ENVIO"
    OTRO_MOVIMIENTO = "OTRO_MOVIMIENTO"
    MULTIPLES_TIPOS = "MULTIPLES_TIPOS"


class PrioridadOperativa(StrEnum):
    PRIORIDAD_ALTA = "PRIORIDAD_ALTA"
    PRIORIDAD_MEDIA = "PRIORIDAD_MEDIA"
    PRIORIDAD_BAJA = "PRIORIDAD_BAJA"
    NO_ES_VENTA = "NO_ES_VENTA"


class CombinacionResumida(StrEnum):
    NO_APLICA = "NO_APLICA"
    PAGO_DEVOLUCION = "PAGO + DEVOLUCIÓN"
    PAGO_RECLAMO = "PAGO + RECLAMO"
    PAGO_ENVIO = "PAGO + ENVÍO"
    ENVIO_DEVOLUCION = "ENVÍO + DEVOLUCIÓN"
    ENVIO_DISPUTA = "ENVÍO + DISPUTA"
    OTRAS_COMBINACIONES = "OTRAS COMBINACIONES"


class EstadoCoherenciaGrupo(StrEnum):
    """Resultado de contrastar el agregado con el detalle monetario visible."""

    COHERENTE = "COHERENTE"
    INCOHERENTE = "INCOHERENTE"
    NO_VERIFICABLE = "NO_VERIFICABLE"


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
    importe_crudo: str = ""
    columna_fuente_importe: str = _COLUMNA_MONTO_MP
    estado_correspondencia_fila: str = "CORRESPONDENCIA_OK"


@dataclass(frozen=True)
class EnriquecimientoMovimientoMpPorFila:
    """Instantánea atómica de los campos que necesariamente pertenecen a una fila MP."""

    fila_origen: int
    id_movimiento: str
    id_orden: str | None
    tipo_operacion: str
    monto_neto_impactado: Decimal
    tratamiento: TratamientoNetoComparable
    fecha_origen: date | datetime | None
    fecha_aprobacion: date | datetime | None
    fecha_liquidacion: date | datetime | None
    importe_crudo: str
    columna_fuente_importe: str = _COLUMNA_MONTO_MP


def enriquecimientos_movimientos_mp_por_fila(movimientos: Iterable[Any]) -> dict[int, EnriquecimientoMovimientoMpPorFila]:
    """Crea un único índice por número de fila Excel y rechaza filas duplicadas."""
    resultado: dict[int, EnriquecimientoMovimientoMpPorFila] = {}
    for m in movimientos:
        fila = m.numero_fila_origen
        if fila in resultado:
            raise ValueError(f"Fila MP duplicada en el enriquecimiento: {fila}")
        resultado[fila] = EnriquecimientoMovimientoMpPorFila(
            fila, m.id_operacion_mercado_pago, m.id_orden, m.tipo_operacion.value,
            m.monto_neto_impactado, m.tratamiento_neto_comparable, m.fecha_origen_local,
            m.fecha_aprobacion_local, m.fecha_liquidacion_local,
            m.monto_neto_impactado_original or str(m.monto_neto_impactado),
        )
    return resultado


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
    categoria_principal: CategoriaPrincipalMpSinVenta = CategoriaPrincipalMpSinVenta.SIN_FECHA_DE_ORIGEN
    subclasificacion_financiera: SubclasificacionFinanciera = SubclasificacionFinanciera.OTRO_MOVIMIENTO
    tiene_id_orden_utilizable: bool = False
    cantidad_movimientos: int = 0
    cantidad_ids_movimiento_mp: int = 0
    fecha_origen_maxima: str = "Sin fecha"
    fecha_liquidacion_minima: str = "Sin fecha"
    filas_origen_mp: tuple[int, ...] = ()
    movimientos_asociados: tuple[DetalleMovimientoMp, ...] = ()
    prioridad_operativa: PrioridadOperativa = PrioridadOperativa.NO_ES_VENTA
    combinacion_resumida: CombinacionResumida = CombinacionResumida.NO_APLICA
    interpretacion: str = "Movimiento financiero o promocional que no representa una venta ML."
    posible_venta_faltante: bool = False
    suma_reconstruida_movimientos_mp: Decimal | None = None
    neto_financiero_agregado_original_mp: Decimal | None = None
    diferencia_agregado_detalle_mp: Decimal | None = None
    coherencia_grupo: bool = True
    estado_coherencia: EstadoCoherenciaGrupo = EstadoCoherenciaGrupo.COHERENTE
    motivo_coherencia: str = "El agregado coincide con la suma reconstruida del detalle."
    advertencia_inconsistencia: str = ""


@dataclass(frozen=True)
class ResumenCategoriaMpSinVenta:
    categoria: CategoriaPrincipalMpSinVenta
    cantidad_grupos: int
    cantidad_movimientos: int
    neto_aprobado_bruto: Decimal
    neto_financiero_total: Decimal
    con_id_orden: int
    sin_id_orden: int
    accion_recomendada: str


@dataclass(frozen=True)
class ResumenOperativoMpSinVenta:
    prioridad_operativa: PrioridadOperativa
    subclasificacion_financiera: SubclasificacionFinanciera
    cantidad_grupos: int
    cantidad_movimientos: int
    neto_aprobado_bruto: Decimal
    neto_financiero_total: Decimal
    con_id_orden: int
    sin_id_orden: int
    interpretacion: str
    accion_recomendada: str


@dataclass(frozen=True)
class CalidadMonetariaMpSinVenta:
    """Calidad del detalle monetario, sin convertir ausencias en importes cero."""

    grupos_coherentes: int
    grupos_incoherentes: int
    grupos_no_verificables: int
    movimientos_correspondencia_inconsistente: int
    pagos_aprobados_negativos: int
    importe_reconstruido_confiable: Decimal
    importe_excluido_o_no_verificable: Decimal | None
    cantidad_grupos_excluidos: int


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
    resumen_mp_sin_venta: tuple[ResumenCategoriaMpSinVenta, ...]
    coherencia_mp_sin_venta: bool
    resumen_operativo_dentro_periodo: tuple[ResumenOperativoMpSinVenta, ...]
    coherencia_operativa_dentro_periodo: bool
    coherencia_detalle_importes_mp_sin_venta: bool
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
    composicion_cantidades_coherente: bool = True
    composicion_movimientos_coherente: bool = True
    composicion_neto_aprobado_coherente: bool = True
    composicion_neto_financiero_coherente: bool = True
    existen_grupos_monetarios_inconsistentes: bool = False
    calidad_monetaria_mp_sin_venta: CalidadMonetariaMpSinVenta | None = None


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


def categoria_principal_mp(
    filas_mp: tuple[int, ...],
    fechas_origen_por_fila: Mapping[int, date | datetime | None],
    inicio_ml: date | None,
    fin_ml: date | None,
) -> CategoriaPrincipalMpSinVenta:
    """Clasificación excluyente y conservadora basada en la cobertura ML real."""
    fechas = [_as_date(fechas_origen_por_fila.get(f)) for f in filas_mp]
    validas = [f for f in fechas if f is not None]
    if not validas or inicio_ml is None or fin_ml is None:
        return CategoriaPrincipalMpSinVenta.SIN_FECHA_DE_ORIGEN
    if max(validas) < inicio_ml:
        return CategoriaPrincipalMpSinVenta.ANTERIOR_AL_PERIODO_ML
    if min(validas) > fin_ml:
        return CategoriaPrincipalMpSinVenta.POSTERIOR_AL_PERIODO_ML
    if any(inicio_ml <= fecha <= fin_ml for fecha in validas):
        return CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA
    # Si hay fechas anteriores y posteriores pero ninguna dentro, el intervalo
    # del grupo atraviesa la cobertura ML. Conservadoramente se revisa como
    # DENTRO_DEL_PERIODO_ML_SIN_VENTA; nunca se lo presenta como carente de fecha.
    return CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA


def subclasificar_financieramente(tipos: tuple[str, ...]) -> SubclasificacionFinanciera:
    normalizados = {t.upper().strip() for t in tipos if t and t != "Sin tipo"}
    if len(normalizados) > 1:
        return SubclasificacionFinanciera.MULTIPLES_TIPOS
    texto = next(iter(normalizados), "")
    if "RECLAM" in texto or "DISPUT" in texto:
        return SubclasificacionFinanciera.RECLAMO_O_DISPUTA
    if "DEVOL" in texto or "REEMBOL" in texto:
        return SubclasificacionFinanciera.DEVOLUCION
    if "ENVIO" in texto or "ENVÍO" in texto:
        return SubclasificacionFinanciera.ENVIO
    if "APROBAD" in texto or texto in {"PAGO", "PAYMENT"}:
        return SubclasificacionFinanciera.PAGO_APROBADO
    return SubclasificacionFinanciera.OTRO_MOVIMIENTO


def combinacion_resumida(tipos: tuple[str, ...]) -> CombinacionResumida:
    """Resume una combinación sin descartar los tipos originales auditables."""
    textos = {t.upper().strip() for t in tipos if t and t != "Sin tipo"}
    if len(textos) <= 1:
        return CombinacionResumida.NO_APLICA
    pago = any("APROBAD" in t or t in {"PAGO", "PAYMENT"} for t in textos)
    devolucion = any("DEVOL" in t or "REEMBOL" in t for t in textos)
    reclamo = any("RECLAM" in t for t in textos)
    disputa = any("DISPUT" in t for t in textos)
    envio = any("ENVIO" in t or "ENVÍO" in t for t in textos)
    if pago and devolucion:
        return CombinacionResumida.PAGO_DEVOLUCION
    if pago and reclamo:
        return CombinacionResumida.PAGO_RECLAMO
    if pago and envio:
        return CombinacionResumida.PAGO_ENVIO
    if envio and devolucion:
        return CombinacionResumida.ENVIO_DEVOLUCION
    if envio and disputa:
        return CombinacionResumida.ENVIO_DISPUTA
    return CombinacionResumida.OTRAS_COMBINACIONES


def _datos_operativos(sub: SubclasificacionFinanciera) -> tuple[PrioridadOperativa, str, str]:
    if sub == SubclasificacionFinanciera.PAGO_APROBADO:
        return (PrioridadOperativa.PRIORIDAD_ALTA,
                "Pago aprobado originado dentro del período ML sin venta oficial encontrada. Requiere revisión prioritaria.",
                "Buscar la venta oficial por ID de orden y validar la cobertura ML de forma prioritaria.")
    if sub == SubclasificacionFinanciera.MULTIPLES_TIPOS:
        return (PrioridadOperativa.PRIORIDAD_MEDIA,
                "Grupo financiero con múltiples movimientos asociados. Revisar el ciclo completo antes de considerarlo venta faltante.",
                "Revisar todos los movimientos y su secuencia antes de escalar como posible venta faltante.")
    if sub == SubclasificacionFinanciera.ENVIO:
        return (PrioridadOperativa.PRIORIDAD_BAJA,
                "Componente de envío sin pago principal localizado en el universo cargado. No implica por sí mismo una venta faltante.",
                "Buscar el pago principal asociado; no registrar el envío aislado como venta faltante.")
    return (PrioridadOperativa.NO_ES_VENTA,
            "Movimiento financiero o promocional que no representa una venta ML.",
            "Clasificar como movimiento financiero o informativo; no tratar como venta omitida.")


def _motivo_categoria(categoria: CategoriaPrincipalMpSinVenta) -> str:
    return {
        CategoriaPrincipalMpSinVenta.ANTERIOR_AL_PERIODO_ML: "Movimiento originado antes del período de ventas ML cargado. No puede considerarse venta faltante con los archivos actuales.",
        CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA: "Movimiento originado dentro del período ML cargado sin venta oficial encontrada. Requiere revisión prioritaria.",
        CategoriaPrincipalMpSinVenta.POSTERIOR_AL_PERIODO_ML: "Movimiento posterior al período ML cargado.",
        CategoriaPrincipalMpSinVenta.SIN_FECHA_DE_ORIGEN: "No existe una fecha de origen válida para clasificar temporalmente.",
    }[categoria]


def _accion_categoria(categoria: CategoriaPrincipalMpSinVenta) -> str:
    return {
        CategoriaPrincipalMpSinVenta.ANTERIOR_AL_PERIODO_ML: "Revisión financiera histórica; ampliar la cobertura ML solo si corresponde.",
        CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA: "Revisar prioritariamente la vinculación y la venta oficial ML.",
        CategoriaPrincipalMpSinVenta.POSTERIOR_AL_PERIODO_ML: "Revisar cuando se cargue el período ML posterior.",
        CategoriaPrincipalMpSinVenta.SIN_FECHA_DE_ORIGEN: "Completar o validar la fecha de origen y el tipo de movimiento.",
    }[categoria]


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
    enriquecimientos: Mapping[int, EnriquecimientoMovimientoMpPorFila] | None = None,
) -> tuple[DetalleMovimientoMp, ...]:
    """Construye la tupla de detalle de movimientos MP para las filas dadas."""
    detalles: list[DetalleMovimientoMp] = []
    for fila in filas_mp:
        if enriquecimientos is not None:
            e = enriquecimientos.get(fila)
            if e is None:
                detalles.append(DetalleMovimientoMp("—", "—", "Sin tipo", "Sin clasificación", None,
                    "Sin fecha", "Sin fecha", "Sin fecha", None, fila,
                    estado_correspondencia_fila="ESTADO_DATO_INCONSISTENTE: fila ausente"))
                continue
            estado = "CORRESPONDENCIA_OK"
            if e.fila_origen != fila:
                estado = "ESTADO_DATO_INCONSISTENTE: clave y fila original no coinciden"
            if e.tipo_operacion == "PAGO_APROBADO" and e.monto_neto_impactado < _ZERO:
                estado = "ESTADO_DATO_INCONSISTENTE: PAGO_APROBADO negativo"
            detalles.append(DetalleMovimientoMp(
                e.id_movimiento, e.id_orden or "—", e.tipo_operacion, e.tipo_operacion,
                e.tratamiento, _fecha_str(_as_date(e.fecha_origen)),
                _fecha_str(_as_date(e.fecha_aprobacion)), _fecha_str(_as_date(e.fecha_liquidacion)),
                e.monto_neto_impactado, fila, e.importe_crudo, e.columna_fuente_importe, estado,
            ))
            continue
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


def _tratamiento_detalle(detalle: DetalleMovimientoMp) -> TratamientoNetoComparable:
    """Obtiene el tratamiento contable, con una reserva para entradas antiguas.

    El enriquecimiento productivo informa el tratamiento explícito. La reserva
    solo permite auditar reportes creados antes de que ese mapa existiera y
    conserva las dos exclusiones inequívocas (envíos ya incluidos y payouts).
    """
    if detalle.tratamiento_neto_comparable is not None:
        return detalle.tratamiento_neto_comparable
    tipo = detalle.tipo_movimiento.upper().strip()
    if tipo in {"PAGO_ENVIO", "PAGO DE ENVÍO", "PAGO DE ENVIO"}:
        return TratamientoNetoComparable.COMPONENTE_YA_INCLUIDO
    if tipo == "PAYOUT":
        return TratamientoNetoComparable.MOVIMIENTO_DE_FONDOS
    return TratamientoNetoComparable.MODIFICA_NETO_COMPARABLE


def _importes_desde_detalle(
    detalles: tuple[DetalleMovimientoMp, ...],
    neto_financiero_respaldo: Decimal | None,
) -> tuple[Decimal | None, Decimal | None, EstadoCoherenciaGrupo, str]:
    """Reconstruye ambos importes usando exactamente las filas visibles.

    Sin filas o con importes faltantes no existe evidencia para reconstruir: los
    importes calculados quedan en ``None`` y el agregado solo puede mostrarse por
    separado como referencia de auditoría.
    """
    if not detalles:
        return (None, None, EstadoCoherenciaGrupo.NO_VERIFICABLE,
                "No hay movimientos asociados para reconstruir los importes del grupo.")
    inconsistentes = tuple(d for d in detalles if d.estado_correspondencia_fila != "CORRESPONDENCIA_OK")
    if inconsistentes:
        return (None, None, EstadoCoherenciaGrupo.INCOHERENTE,
                "Enriquecimiento MP inconsistente en filas: "
                + ", ".join(str(d.fila_origen) for d in inconsistentes) + ".")
    filas_sin_importe = tuple(d.fila_origen for d in detalles if d.monto_neto_impactado is None)
    if filas_sin_importe:
        return (None, None, EstadoCoherenciaGrupo.NO_VERIFICABLE,
                "Detalle monetario incompleto: falta monto_neto_impactado en las filas MP "
                + ", ".join(map(str, filas_sin_importe)) + ".")
    neto_aprobado = _sum_decimals(
        d.monto_neto_impactado for d in detalles
        if d.tipo_movimiento.upper().strip() == "PAGO_APROBADO"
    )
    reconstruido = _sum_decimals(
        d.monto_neto_impactado for d in detalles
        if _tratamiento_detalle(d) == TratamientoNetoComparable.MODIFICA_NETO_COMPARABLE
    )
    if neto_financiero_respaldo is None:
        return (neto_aprobado, reconstruido, EstadoCoherenciaGrupo.NO_VERIFICABLE,
                "El detalle monetario pudo reconstruirse, pero no existe agregado financiero original para verificar la coincidencia.")
    if reconstruido == neto_financiero_respaldo:
        return (neto_aprobado, reconstruido, EstadoCoherenciaGrupo.COHERENTE,
                "El agregado coincide con la suma reconstruida del detalle.")
    return (neto_aprobado, reconstruido, EstadoCoherenciaGrupo.INCOHERENTE,
            "El agregado financiero no coincide con la suma de los movimientos visibles asociados.")


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
    enriquecimientos_mp_por_fila: Mapping[int, EnriquecimientoMovimientoMpPorFila] | None = None,
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
    enriquecimientos = enriquecimientos_mp_por_fila
    if enriquecimientos is not None:
        # Una sola fuente atómica evita que posición, índice interno y fila Excel
        # se desplacen independientemente entre diccionarios paralelos.
        fechas_origen = {f: e.fecha_origen for f, e in enriquecimientos.items()}
        fechas_liq = {f: e.fecha_liquidacion for f, e in enriquecimientos.items()}
        fechas_aprobacion = {f: e.fecha_aprobacion for f, e in enriquecimientos.items()}
        tipos = {f: e.tipo_operacion for f, e in enriquecimientos.items()}
        ids_op = {f: e.id_movimiento for f, e in enriquecimientos.items()}
        ids_orden_mp = {f: e.id_orden for f, e in enriquecimientos.items()}
        montos_neto = {f: e.monto_neto_impactado for f, e in enriquecimientos.items()}
        clasificaciones = dict(tipos)
        tratamientos = {f: e.tratamiento for f, e in enriquecimientos.items()}

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
            clasificaciones, tratamientos, enriquecimientos,
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
                clasificaciones, tratamientos, enriquecimientos,
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
    movs_sin_venta: list[MovimientoMpSinVentaML] = []
    for r in solo_mp:
        id_g = _id_grupo(r)
        f_min_orig, f_max_orig = _fechas_rango(r.filas_origen_mp, fechas_origen)
        f_min_liq_mv, f_max_liq_mv = _fechas_rango(r.filas_origen_mp, fechas_liq)
        cat_temp = categoria_temporal_mp(r.filas_origen_mp, fechas_origen, inicio, fin)
        categoria = categoria_principal_mp(r.filas_origen_mp, fechas_origen, inicio, fin)
        tipos_grupo = _tipos_movimiento_para_filas(r.filas_origen_mp, tipos)
        ids_grupo = _ids_operacion_para_filas(r.filas_origen_mp, ids_op)
        detalles = _construir_detalle_movimientos(
            r.filas_origen_mp, ids_op, ids_orden_mp, tipos, fechas_origen,
            fechas_aprobacion, fechas_liq, montos_neto, clasificaciones, tratamientos, enriquecimientos,
        )
        neto_aprobado_detalle, neto_financiero_detalle, estado_coherencia, motivo_coherencia = _importes_desde_detalle(
            detalles, r.neto_financiero_total_mp,
        )
        coherencia_grupo = estado_coherencia == EstadoCoherenciaGrupo.COHERENTE
        diferencia_detalle = (
            neto_financiero_detalle - r.neto_financiero_total_mp
            if neto_financiero_detalle is not None and r.neto_financiero_total_mp is not None
            else None
        )
        subclasificacion = subclasificar_financieramente(tipos_grupo)
        prioridad, interpretacion, accion_operativa = _datos_operativos(subclasificacion)
        dentro_periodo = categoria == CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA
        if not dentro_periodo:
            prioridad = PrioridadOperativa.NO_ES_VENTA

        movs_sin_venta.append(MovimientoMpSinVentaML(
            id_grupo=id_g,
            ids_movimiento_mp=ids_grupo,
            tipos_movimiento=tipos_grupo,
            fecha_min_origen=f_min_orig,
            fecha_max_liquidacion=f_max_liq_mv,
            neto_aprobado_mp=neto_aprobado_detalle,
            neto_financiero_total_mp=neto_financiero_detalle,
            categoria_temporal=cat_temp,
            motivo_sin_venta=_motivo_categoria(categoria),
            accion_recomendada=accion_operativa if dentro_periodo else _accion_categoria(categoria),
            categoria_principal=categoria,
            subclasificacion_financiera=subclasificacion,
            tiene_id_orden_utilizable=any(ids_orden_mp.get(f) for f in r.filas_origen_mp),
            cantidad_movimientos=len(r.filas_origen_mp),
            cantidad_ids_movimiento_mp=len(set(ids_grupo)),
            fecha_origen_maxima=f_max_orig,
            fecha_liquidacion_minima=f_min_liq_mv,
            filas_origen_mp=r.filas_origen_mp,
            movimientos_asociados=detalles,
            prioridad_operativa=prioridad,
            combinacion_resumida=combinacion_resumida(tipos_grupo),
            interpretacion=interpretacion if dentro_periodo else _motivo_categoria(categoria),
            posible_venta_faltante=(dentro_periodo and coherencia_grupo
                                    and subclasificacion == SubclasificacionFinanciera.PAGO_APROBADO),
            suma_reconstruida_movimientos_mp=neto_financiero_detalle,
            neto_financiero_agregado_original_mp=r.neto_financiero_total_mp,
            diferencia_agregado_detalle_mp=diferencia_detalle,
            coherencia_grupo=coherencia_grupo,
            estado_coherencia=estado_coherencia,
            motivo_coherencia=motivo_coherencia,
            advertencia_inconsistencia=("" if coherencia_grupo else
                f"{estado_coherencia.value}: {motivo_coherencia}"),
        ))

    # Los KPI operativos se reconstruyen después de armar el detalle; nunca
    # vuelven a sumar los agregados potencialmente contaminados del reporte.
    neto_ap_sin_venta = _sum_decimals(m.neto_aprobado_mp for m in movs_sin_venta)
    neto_fin_sin_venta = _sum_decimals(m.neto_financiero_total_mp for m in movs_sin_venta)

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

    resumen_categorias: list[ResumenCategoriaMpSinVenta] = []
    for categoria in CategoriaPrincipalMpSinVenta:
        items = tuple(m for m in movs_sin_venta if m.categoria_principal == categoria)
        resumen_categorias.append(ResumenCategoriaMpSinVenta(
            categoria=categoria,
            cantidad_grupos=len(items),
            cantidad_movimientos=sum(m.cantidad_movimientos for m in items),
            neto_aprobado_bruto=_sum_decimals(m.neto_aprobado_mp for m in items),
            neto_financiero_total=_sum_decimals(m.neto_financiero_total_mp for m in items),
            con_id_orden=sum(m.tiene_id_orden_utilizable for m in items),
            sin_id_orden=sum(not m.tiene_id_orden_utilizable for m in items),
            accion_recomendada=_accion_categoria(categoria),
        ))
    coherencia_mp = (
        sum(x.cantidad_grupos for x in resumen_categorias) == len(solo_mp)
        and _sum_decimals(x.neto_aprobado_bruto for x in resumen_categorias) == neto_ap_sin_venta
        and _sum_decimals(x.neto_financiero_total for x in resumen_categorias) == neto_fin_sin_venta
    )

    dentro_periodo = tuple(
        m for m in movs_sin_venta
        if m.categoria_principal == CategoriaPrincipalMpSinVenta.DENTRO_DEL_PERIODO_ML_SIN_VENTA
    )
    resumen_operativo: list[ResumenOperativoMpSinVenta] = []
    # Se conservan todas las subclasificaciones, incluso las que hoy tienen cero casos.
    for subclasificacion in SubclasificacionFinanciera:
        items = tuple(m for m in dentro_periodo if m.subclasificacion_financiera == subclasificacion)
        prioridad, interpretacion, accion = _datos_operativos(subclasificacion)
        resumen_operativo.append(ResumenOperativoMpSinVenta(
            prioridad_operativa=prioridad,
            subclasificacion_financiera=subclasificacion,
            cantidad_grupos=len(items),
            cantidad_movimientos=sum(m.cantidad_movimientos for m in items),
            neto_aprobado_bruto=_sum_decimals(m.neto_aprobado_mp for m in items),
            neto_financiero_total=_sum_decimals(m.neto_financiero_total_mp for m in items),
            con_id_orden=sum(m.tiene_id_orden_utilizable for m in items),
            sin_id_orden=sum(not m.tiene_id_orden_utilizable for m in items),
            interpretacion=interpretacion,
            accion_recomendada=accion,
        ))
    coherencia_detalle = all(m.coherencia_grupo for m in movs_sin_venta)
    composicion_cantidades = sum(x.cantidad_grupos for x in resumen_operativo) == len(dentro_periodo)
    composicion_movimientos = (
        sum(x.cantidad_movimientos for x in resumen_operativo)
        == sum(m.cantidad_movimientos for m in dentro_periodo)
    )
    composicion_aprobado = (
        _sum_decimals(x.neto_aprobado_bruto for x in resumen_operativo)
        == _sum_decimals(m.neto_aprobado_mp for m in dentro_periodo)
    )
    composicion_financiero = (
        _sum_decimals(x.neto_financiero_total for x in resumen_operativo)
        == _sum_decimals(m.neto_financiero_total_mp for m in dentro_periodo)
    )
    coherencia_operativa = all((composicion_cantidades, composicion_movimientos,
                                composicion_aprobado, composicion_financiero))

    grupos_excluidos = tuple(m for m in movs_sin_venta if not m.coherencia_grupo)
    importes_excluidos = tuple(
        m.neto_financiero_agregado_original_mp for m in grupos_excluidos
        if m.neto_financiero_agregado_original_mp is not None
    )
    calidad = CalidadMonetariaMpSinVenta(
        grupos_coherentes=sum(m.estado_coherencia == EstadoCoherenciaGrupo.COHERENTE for m in movs_sin_venta),
        grupos_incoherentes=sum(m.estado_coherencia == EstadoCoherenciaGrupo.INCOHERENTE for m in movs_sin_venta),
        grupos_no_verificables=sum(m.estado_coherencia == EstadoCoherenciaGrupo.NO_VERIFICABLE for m in movs_sin_venta),
        movimientos_correspondencia_inconsistente=sum(
            d.estado_correspondencia_fila != "CORRESPONDENCIA_OK"
            for m in movs_sin_venta for d in m.movimientos_asociados
        ),
        pagos_aprobados_negativos=sum(
            d.tipo_movimiento.upper().strip() == "PAGO_APROBADO"
            and d.monto_neto_impactado is not None and d.monto_neto_impactado < _ZERO
            for m in movs_sin_venta for d in m.movimientos_asociados
        ),
        importe_reconstruido_confiable=_sum_decimals(
            m.suma_reconstruida_movimientos_mp for m in movs_sin_venta if m.coherencia_grupo
        ),
        # None comunica que al menos un grupo carece de importe auditable; no se lo presenta como $0.
        importe_excluido_o_no_verificable=(
            _sum_decimals(importes_excluidos)
            if len(importes_excluidos) == len(grupos_excluidos) else None
        ),
        cantidad_grupos_excluidos=len(grupos_excluidos),
    )

    return DiagnosticoBloqueB(
        resumen=resumen,
        grupos_con_diferencia=tuple(grupos_con_dif),
        cantidad_mp_sin_venta=len(solo_mp),
        neto_aprobado_mp_sin_venta=neto_ap_sin_venta,
        neto_financiero_total_mp_sin_venta=neto_fin_sin_venta,
        movimientos_mp_sin_venta=tuple(movs_sin_venta),
        resumen_mp_sin_venta=tuple(resumen_categorias),
        coherencia_mp_sin_venta=coherencia_mp,
        resumen_operativo_dentro_periodo=tuple(resumen_operativo),
        coherencia_operativa_dentro_periodo=coherencia_operativa,
        coherencia_detalle_importes_mp_sin_venta=coherencia_detalle,
        cantidad_movimientos_fondos=len(fondos_r),
        neto_aprobado_mp_fondos=neto_ap_fondos,
        neto_financiero_total_mp_fondos=neto_fin_fondos,
        movimientos_fondos=tuple(movimientos_fondos),
        grupos_movimientos_asociados=grupos_movimientos,
        suma_diferencias_individuales=suma_ind,
        coherencia_suma_diferencias=coherencia,
        composicion_cantidades_coherente=composicion_cantidades,
        composicion_movimientos_coherente=composicion_movimientos,
        composicion_neto_aprobado_coherente=composicion_aprobado,
        composicion_neto_financiero_coherente=composicion_financiero,
        existen_grupos_monetarios_inconsistentes=bool(grupos_excluidos),
        calidad_monetaria_mp_sin_venta=calidad,
    )
