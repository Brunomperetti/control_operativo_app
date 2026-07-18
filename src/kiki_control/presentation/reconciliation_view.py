"""Transformaciones puras de reportes de conciliación para interfaz."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from kiki_control.domain.reconciliation import EstadoConciliacion, ReporteConciliacion, ResultadoConciliacion
from kiki_control.presentation.formatters import formato_bool, formato_pesos_argentino

ETIQUETAS_ESTADO: dict[EstadoConciliacion, str] = {
    EstadoConciliacion.CONCILIADA: "Conciliada",
    EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR: "Diferencia menor",
    EstadoConciliacion.CONCILIADA_CON_DIFERENCIA: "Con diferencia",
    EstadoConciliacion.PENDIENTE_ACREDITACION: "Pendiente de acreditación",
    EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO: "Sin movimiento financiero",
    EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL: "Sin operación comercial",
    EstadoConciliacion.DEVUELTA: "Devuelta",
    EstadoConciliacion.EN_RECLAMO: "En reclamo",
    EstadoConciliacion.EN_REVISION: "En revisión",
    EstadoConciliacion.DUPLICADA: "Duplicada",
    EstadoConciliacion.MOVIMIENTO_DE_FONDOS: "Movimiento de fondos",
}

@dataclass(frozen=True)
class FilaResultadoPresentacion:
    clave: str
    id_orden: str
    estado: str
    estado_codigo: str
    neto_informado_ml: str
    neto_pagos_aprobados_mp: str
    diferencia: str
    diferencia_valor: Decimal | None
    neto_financiero_total: str
    utilidad_informada: str
    pago_dividido: str
    devolucion: str
    reclamo_o_disputa: str
    pendiente_acreditacion: str
    requiere_revision: str
    motivo_principal: str

COLUMNAS_SEGURAS = tuple(FilaResultadoPresentacion.__dataclass_fields__)


def etiqueta_estado(estado: EstadoConciliacion) -> str:
    return ETIQUETAS_ESTADO[estado]


def clave_resultado(resultado: ResultadoConciliacion) -> str:
    if resultado.id_orden:
        return resultado.id_orden
    fila = resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else "sin-fila"
    return f"{resultado.estado.value.lower()}-fila-{fila}"


def resultado_a_fila(resultado: ResultadoConciliacion) -> FilaResultadoPresentacion:
    return FilaResultadoPresentacion(
        clave=clave_resultado(resultado),
        id_orden=resultado.id_orden or clave_resultado(resultado),
        estado=etiqueta_estado(resultado.estado),
        estado_codigo=resultado.estado.value,
        neto_informado_ml=formato_pesos_argentino(resultado.neto_comercial_informado),
        neto_pagos_aprobados_mp=formato_pesos_argentino(resultado.neto_pagos_aprobados),
        diferencia=formato_pesos_argentino(resultado.diferencia_control),
        diferencia_valor=resultado.diferencia_control,
        neto_financiero_total=formato_pesos_argentino(resultado.neto_financiero_total),
        utilidad_informada=formato_pesos_argentino(resultado.utilidad_neta_informada),
        pago_dividido=formato_bool(resultado.es_pago_dividido),
        devolucion=formato_bool(resultado.tiene_devolucion),
        reclamo_o_disputa=formato_bool(resultado.tiene_reclamo or resultado.tiene_disputa),
        pendiente_acreditacion=formato_bool(resultado.tiene_liquidacion_pendiente or resultado.estado == EstadoConciliacion.PENDIENTE_ACREDITACION),
        requiere_revision=formato_bool(resultado.requiere_revision),
        motivo_principal=resultado.motivos[0].value if resultado.motivos else "—",
    )


def filas_presentacion(resultados: Iterable[ResultadoConciliacion]) -> list[FilaResultadoPresentacion]:
    return [resultado_a_fila(r) for r in sorted(resultados, key=lambda r: (r.id_orden is None, r.id_orden or "", r.numeros_fila_financiera, r.estado.value))]


def filtrar_filas(filas: Iterable[FilaResultadoPresentacion], estados: set[str] | None = None, busqueda_id: str = "", solo_revision: bool = False, solo_pago_dividido: bool = False) -> list[FilaResultadoPresentacion]:
    texto = busqueda_id.strip().lower()
    salida = []
    for fila in filas:
        if estados and fila.estado_codigo not in estados:
            continue
        if texto and texto not in fila.id_orden.lower():
            continue
        if solo_revision and fila.requiere_revision != "Sí":
            continue
        if solo_pago_dividido and fila.pago_dividido != "Sí":
            continue
        salida.append(fila)
    return salida


def resumen_kpis(reporte: ReporteConciliacion) -> dict[str, int | str]:
    resultados = reporte.resultados
    total_neto_comercial = _sumar(r.neto_comercial_informado for r in resultados)
    total_pagos = _sumar(r.neto_pagos_aprobados for r in resultados)
    total_diferencia = _sumar(r.diferencia_control for r in resultados)
    total_utilidad = _sumar(r.utilidad_neta_informada for r in resultados)
    sin_contraparte = sum(1 for r in resultados if r.estado in {EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO, EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL})
    return {
        "Operaciones comerciales": reporte.cantidad_operaciones_comerciales,
        "Movimientos financieros": reporte.cantidad_movimientos_financieros,
        "Conciliadas": reporte.total_conciliadas,
        "Con diferencias": reporte.total_con_diferencias,
        "Sin contraparte": sin_contraparte,
        "Pendientes de acreditación": sum(1 for r in resultados if r.estado == EstadoConciliacion.PENDIENTE_ACREDITACION or r.tiene_liquidacion_pendiente),
        "Devueltas": reporte.total_devueltas,
        "En reclamo": reporte.total_en_reclamo,
        "En revisión": reporte.total_en_revision,
        "Movimientos de fondos": reporte.total_movimientos_fondos,
        "Utilidad informada por Mercado Libre": formato_pesos_argentino(total_utilidad),
        "Neto comercial informado": formato_pesos_argentino(total_neto_comercial),
        "Neto de pagos aprobados": formato_pesos_argentino(total_pagos),
        "Diferencia total de control": formato_pesos_argentino(total_diferencia),
    }


def _sumar(valores: Iterable[Decimal | None]) -> Decimal | None:
    total = Decimal("0")
    encontro = False
    for valor in valores:
        if valor is not None:
            total += valor
            encontro = True
    return total if encontro else None


def detalle_presentacion(resultado: ResultadoConciliacion) -> dict[str, str | int]:
    return {
        "ID de orden": resultado.id_orden or clave_resultado(resultado),
        "Estado": etiqueta_estado(resultado.estado),
        "Motivos": ", ".join(m.value for m in resultado.motivos) or "—",
        "Explicaciones": " | ".join(resultado.explicaciones) or "—",
        "Filas comerciales de origen": ", ".join(map(str, resultado.numeros_fila_comercial)) or "—",
        "Filas financieras de origen": ", ".join(map(str, resultado.numeros_fila_financiera)) or "—",
        "Cantidad de pagos aprobados": resultado.cantidad_pagos_aprobados,
        "Pago dividido": formato_bool(resultado.es_pago_dividido),
        "Neto comercial informado": formato_pesos_argentino(resultado.neto_comercial_informado),
        "Neto de pagos aprobados": formato_pesos_argentino(resultado.neto_pagos_aprobados),
        "Diferencia": formato_pesos_argentino(resultado.diferencia_control),
        "Impacto de pagos de envío": formato_pesos_argentino(resultado.impacto_pagos_envio),
        "Impacto de devoluciones": formato_pesos_argentino(resultado.impacto_devoluciones),
        "Impacto de reclamos/disputas": formato_pesos_argentino(resultado.impacto_reclamos_disputas),
        "Impacto de otros movimientos": formato_pesos_argentino(resultado.impacto_otros),
        "Neto financiero total": formato_pesos_argentino(resultado.neto_financiero_total),
        "Utilidad neta informada": formato_pesos_argentino(resultado.utilidad_neta_informada),
        "Indicadores de revisión": "Sí" if resultado.requiere_revision or resultado.tiene_duplicados or resultado.tiene_movimiento_desconocido else "No",
    }
