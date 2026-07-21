"""Clasificación pura de revisiones pendientes para presentación."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from kiki_control.domain.reconciliation import EstadoConciliacion, MotivoConciliacion, ResultadoConciliacion
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.reconciliation_view import clave_resultado, etiqueta_estado


class TipoRevision(StrEnum):
    DUPLICACION_COMERCIAL = "DUPLICACION_COMERCIAL"
    DUPLICACION_FINANCIERA = "DUPLICACION_FINANCIERA"
    MOVIMIENTO_DESCONOCIDO_EN_REVISION = "MOVIMIENTO_DESCONOCIDO_EN_REVISION"
    RECLAMO_O_DISPUTA = "RECLAMO_O_DISPUTA"
    MP_SIN_ID_ORDEN = "MP_SIN_ID_ORDEN"
    ORDEN_MP_SIN_VENTA_ML = "ORDEN_MP_SIN_VENTA_ML"
    VENTA_ML_SIN_MOVIMIENTO_MP = "VENTA_ML_SIN_MOVIMIENTO_MP"
    OTRA_REVISION = "OTRA_REVISION"


@dataclass(frozen=True)
class DefinicionRevision:
    tipo: TipoRevision
    nombre_visible: str
    descripcion: str
    accion_recomendada: str
    columnas_utilizadas: tuple[str, ...]


@dataclass(frozen=True)
class CasoRevision:
    tipo: TipoRevision
    nombre_visible: str
    descripcion: str
    accion_recomendada: str
    resultado: ResultadoConciliacion
    columnas_utilizadas: tuple[str, ...]
    filas_ml: tuple[int, ...]
    filas_mp: tuple[int, ...]
    condiciones_adicionales: tuple[TipoRevision, ...]


@dataclass(frozen=True)
class FilaRevisionPendiente:
    clave: str
    id_orden_o_referencia: str
    tipo_revision: str
    tipo_revision_codigo: str
    estado: str
    motivo_explicado: str
    accion_recomendada: str
    neto_informado_ml: str
    neto_aprobado_mp: str
    neto_financiero_total: str
    filas_ml: str
    filas_mp: str
    columnas_origen: str


DEFINICIONES_REVISION: dict[TipoRevision, DefinicionRevision] = {
    TipoRevision.MP_SIN_ID_ORDEN: DefinicionRevision(TipoRevision.MP_SIN_ID_ORDEN, "Pago o movimiento MP sin ID de orden", "El movimiento de Mercado Pago no posee ID de orden y no puede vincularse automáticamente con una venta de Mercado Libre.", "Revisar el movimiento en Mercado Pago utilizando su fila y datos operativos. Verificar si el archivo exportado contiene el ID o si corresponde a un movimiento que no pertenece a una venta.", ("ID DE LA ORDEN", "TIPO DE OPERACIÓN", "ID DE OPERACIÓN EN MERCADO PAGO")),
    TipoRevision.ORDEN_MP_SIN_VENTA_ML: DefinicionRevision(TipoRevision.ORDEN_MP_SIN_VENTA_ML, "Orden MP sin venta en el archivo ML", "El ID de orden aparece en Mercado Pago, pero no se encontró en el archivo comercial cargado.", "Buscar el ID en Mercado Libre y verificar la cobertura temporal. Puede corresponder a una venta de otro período.", ("MP: ID DE LA ORDEN", "ML: ID Order", "MP: FECHA DE ORIGEN", "ML: Fecha de venta")),
    TipoRevision.VENTA_ML_SIN_MOVIMIENTO_MP: DefinicionRevision(TipoRevision.VENTA_ML_SIN_MOVIMIENTO_MP, "Venta ML sin movimiento MP", "La venta aparece en Mercado Libre, pero no se encontró movimiento asociado en el XLSX cargado.", "Verificar que el archivo de Mercado Pago cubra el mismo período y revisar si el movimiento todavía no fue generado o acreditado.", ("ID Order", "ID DE LA ORDEN", "Fecha de venta", "FECHA DE ORIGEN")),
    TipoRevision.RECLAMO_O_DISPUTA: DefinicionRevision(TipoRevision.RECLAMO_O_DISPUTA, "Reclamo o disputa", "Mercado Pago informa un reclamo o una disputa asociada al resultado.", "Revisar el caso en Mercado Pago y confirmar su estado, importe y resolución.", ("ID DE LA ORDEN", "TIPO DE OPERACIÓN", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO")),
    TipoRevision.MOVIMIENTO_DESCONOCIDO_EN_REVISION: DefinicionRevision(TipoRevision.MOVIMIENTO_DESCONOCIDO_EN_REVISION, "Movimiento desconocido o en revisión", "El tipo de movimiento no coincide con las categorías financieras actualmente reconocidas.", "Revisar el valor original de TIPO DE OPERACIÓN. No clasificarlo automáticamente hasta confirmar su significado.", ("ID DE LA ORDEN", "TIPO DE OPERACIÓN")),
    TipoRevision.DUPLICACION_COMERCIAL: DefinicionRevision(TipoRevision.DUPLICACION_COMERCIAL, "Duplicación comercial", "Existe más de una fila comercial con el mismo ID Order.", "Revisar las filas comerciales y confirmar si representan productos de una misma orden o un duplicado del archivo. La aplicación no las suma automáticamente.", ("ID Order",)),
    TipoRevision.DUPLICACION_FINANCIERA: DefinicionRevision(TipoRevision.DUPLICACION_FINANCIERA, "Duplicación financiera", "Se repite la clave financiera utilizada para detectar duplicados.", "Revisar las filas repetidas antes de cerrar la conciliación.", ("ID DE OPERACIÓN EN MERCADO PAGO", "TIPO DE OPERACIÓN")),
    TipoRevision.OTRA_REVISION: DefinicionRevision(TipoRevision.OTRA_REVISION, "Otra revisión", "La aplicación no puede resolverlo automáticamente con los datos disponibles.", "Revisar las filas y columnas de origen indicadas antes de cerrar la conciliación.", ("ID Order", "ID DE LA ORDEN", "TIPO DE OPERACIÓN")),
}

PRIORIDAD_REVISION = (
    TipoRevision.DUPLICACION_COMERCIAL,
    TipoRevision.DUPLICACION_FINANCIERA,
    TipoRevision.MOVIMIENTO_DESCONOCIDO_EN_REVISION,
    TipoRevision.RECLAMO_O_DISPUTA,
    TipoRevision.MP_SIN_ID_ORDEN,
    TipoRevision.ORDEN_MP_SIN_VENTA_ML,
    TipoRevision.VENTA_ML_SIN_MOVIMIENTO_MP,
    TipoRevision.OTRA_REVISION,
)


def condiciones_revision(resultado: ResultadoConciliacion) -> tuple[TipoRevision, ...]:
    if not resultado.requiere_revision:
        return ()
    condiciones: list[TipoRevision] = []
    motivos = set(resultado.motivos)
    if MotivoConciliacion.OPERACION_COMERCIAL_DUPLICADA in motivos:
        condiciones.append(TipoRevision.DUPLICACION_COMERCIAL)
    if MotivoConciliacion.MOVIMIENTO_FINANCIERO_DUPLICADO in motivos:
        condiciones.append(TipoRevision.DUPLICACION_FINANCIERA)
    if resultado.estado == EstadoConciliacion.EN_REVISION or resultado.tiene_movimiento_desconocido or MotivoConciliacion.MOVIMIENTO_DESCONOCIDO in motivos:
        condiciones.append(TipoRevision.MOVIMIENTO_DESCONOCIDO_EN_REVISION)
    if resultado.estado == EstadoConciliacion.EN_RECLAMO or resultado.tiene_reclamo or resultado.tiene_disputa or MotivoConciliacion.RECLAMO_DETECTADO in motivos or MotivoConciliacion.DISPUTA_DETECTADA in motivos:
        condiciones.append(TipoRevision.RECLAMO_O_DISPUTA)
    if resultado.id_orden is None and resultado.cantidad_movimientos_financieros > 0:
        condiciones.append(TipoRevision.MP_SIN_ID_ORDEN)
    if resultado.id_orden is not None and resultado.cantidad_movimientos_financieros > 0 and resultado.cantidad_operaciones_comerciales == 0 and resultado.estado != EstadoConciliacion.MOVIMIENTO_DE_FONDOS:
        condiciones.append(TipoRevision.ORDEN_MP_SIN_VENTA_ML)
    if resultado.cantidad_operaciones_comerciales > 0 and resultado.cantidad_movimientos_financieros == 0:
        condiciones.append(TipoRevision.VENTA_ML_SIN_MOVIMIENTO_MP)
    if not condiciones:
        condiciones.append(TipoRevision.OTRA_REVISION)
    return tuple(dict.fromkeys(condiciones))


def clasificar_revision(resultado: ResultadoConciliacion) -> CasoRevision | None:
    condiciones = condiciones_revision(resultado)
    if not condiciones:
        return None
    principal = next(tipo for tipo in PRIORIDAD_REVISION if tipo in condiciones)
    definicion = DEFINICIONES_REVISION[principal]
    return CasoRevision(principal, definicion.nombre_visible, definicion.descripcion, definicion.accion_recomendada, resultado, definicion.columnas_utilizadas, resultado.numeros_fila_comercial, resultado.numeros_fila_financiera, tuple(t for t in condiciones if t != principal))


def clasificar_revisiones(resultados: Iterable[ResultadoConciliacion]) -> tuple[CasoRevision, ...]:
    return tuple(c for r in resultados if (c := clasificar_revision(r)) is not None)


def conteo_por_tipo(casos: Iterable[CasoRevision]) -> dict[TipoRevision, int]:
    conteos = {tipo: 0 for tipo in PRIORIDAD_REVISION}
    for caso in casos:
        conteos[caso.tipo] += 1
    return {tipo: cantidad for tipo, cantidad in conteos.items() if cantidad}


def clave_caso_revision(caso: CasoRevision) -> str:
    """Clave estable interna para vincular UI con resultado, sin usarla como texto visible."""

    return clave_resultado(caso.resultado)


def referencia_visible_caso(caso: CasoRevision) -> str:
    """Referencia segura visible para la clienta: ID real o referencia interna de fila."""

    r = caso.resultado
    return r.id_orden or f"Movimiento MP sin ID de orden — referencia interna fila {r.numeros_fila_financiera[0] if r.numeros_fila_financiera else 'sin fila'}"


def caso_a_fila(caso: CasoRevision) -> FilaRevisionPendiente:
    r = caso.resultado
    return FilaRevisionPendiente(
        clave=clave_caso_revision(caso),
        id_orden_o_referencia=referencia_visible_caso(caso),
        tipo_revision=caso.nombre_visible,
        tipo_revision_codigo=caso.tipo.value,
        estado=etiqueta_estado(r.estado),
        motivo_explicado=caso.descripcion,
        accion_recomendada=caso.accion_recomendada,
        neto_informado_ml=formato_pesos_argentino(r.neto_comercial_informado),
        neto_aprobado_mp=formato_pesos_argentino(r.neto_pagos_aprobados),
        neto_financiero_total=formato_pesos_argentino(r.neto_financiero_total),
        filas_ml=", ".join(map(str, caso.filas_ml)) or "—",
        filas_mp=", ".join(map(str, caso.filas_mp)) or "—",
        columnas_origen=", ".join(caso.columnas_utilizadas),
    )


def filas_revisiones(casos: Iterable[CasoRevision]) -> list[FilaRevisionPendiente]:
    return [caso_a_fila(c) for c in sorted(casos, key=lambda c: (PRIORIDAD_REVISION.index(c.tipo), c.resultado.id_orden is None, c.resultado.id_orden or "", c.resultado.numeros_fila_financiera))]


def filtrar_casos(casos: Iterable[CasoRevision], tipo: TipoRevision | None = None, busqueda: str = "") -> list[CasoRevision]:
    texto = busqueda.strip().lower()
    salida = []
    for caso in casos:
        ref_visible = referencia_visible_caso(caso)
        ref_interna = clave_caso_revision(caso)
        if tipo is not None and caso.tipo != tipo:
            continue
        if texto and texto not in ref_visible.lower() and texto not in ref_interna.lower():
            continue
        salida.append(caso)
    return salida
