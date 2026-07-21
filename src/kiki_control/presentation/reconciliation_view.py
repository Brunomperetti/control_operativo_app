"""Transformaciones puras de reportes de conciliación para interfaz."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.financial_movement import MovimientoFinanciero
from kiki_control.domain.reconciliation import EstadoConciliacion, ReporteConciliacion, ResultadoConciliacion, VERSION_REGLA_CONCILIACION
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
class RangoFechasPresentacion:
    desde: date | None
    hasta: date | None
    texto: str


@dataclass(frozen=True)
class CoberturaArchivosPresentacion:
    periodo_ventas_ml: RangoFechasPresentacion
    periodo_origen_mp: RangoFechasPresentacion
    periodo_liquidacion_mp: RangoFechasPresentacion
    movimientos_sin_fecha_liquidacion: int
    origenes_coinciden: bool
    advertencia_origenes: str | None


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

ENCABEZADOS_TABLA_CLIENTE = {
    "id_orden": "ID de orden",
    "estado": "Estado",
    "neto_informado_ml": "Neto informado ML",
    "neto_pagos_aprobados_mp": "Neto aprobado MP",
    "diferencia": "Diferencia",
    "neto_financiero_total": "Neto financiero total",
    "utilidad_informada": "Utilidad informada ML",
    "pago_dividido": "Pago dividido",
    "devolucion": "Devolución",
    "reclamo_o_disputa": "Reclamo o disputa",
    "pendiente_acreditacion": "Pendiente de acreditación",
    "requiere_revision": "Requiere revisión",
}

def etiqueta_estado(estado: EstadoConciliacion) -> str:
    return ETIQUETAS_ESTADO[estado]


def cobertura_archivos(operaciones: Sequence[OperacionComercial], movimientos: Sequence[MovimientoFinanciero]) -> CoberturaArchivosPresentacion:
    """Calcula cobertura temporal usando fechas locales normalizadas, sin DataFrames ni Streamlit."""

    ventas = _rango_fechas(o.fecha_hora_venta.date() for o in operaciones)
    origen_mp = _rango_fechas(m.fecha_origen_local.date() for m in movimientos)
    liquidacion_mp = _rango_fechas(m.fecha_liquidacion_local.date() for m in movimientos if m.fecha_liquidacion_local is not None)
    sin_liquidacion = sum(1 for m in movimientos if m.fecha_liquidacion_local is None)
    coinciden = ventas.desde == origen_mp.desde and ventas.hasta == origen_mp.hasta
    advertencia = None
    if not coinciden:
        advertencia = "Los períodos de origen de Mercado Libre y Mercado Pago no coinciden. La conciliación continúa sin recortar movimientos; un movimiento financiero sin contraparte comercial puede pertenecer a otro período y requiere análisis."
    return CoberturaArchivosPresentacion(ventas, origen_mp, liquidacion_mp, sin_liquidacion, coinciden, advertencia)


def _rango_fechas(fechas: Iterable[date]) -> RangoFechasPresentacion:
    valores = tuple(fechas)
    if not valores:
        return RangoFechasPresentacion(None, None, "Sin fechas informadas")
    desde = min(valores)
    hasta = max(valores)
    texto = _formato_fecha(desde) if desde == hasta else f"{_formato_fecha(desde)} a {_formato_fecha(hasta)}"
    return RangoFechasPresentacion(desde, hasta, texto)


def _formato_fecha(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def clave_resultado(resultado: ResultadoConciliacion) -> str:
    if resultado.id_orden:
        return resultado.id_orden
    fila = resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else "sin-fila"
    return f"{resultado.estado.value.lower()}-fila-{fila}"


def resultado_a_fila(resultado: ResultadoConciliacion) -> FilaResultadoPresentacion:
    return FilaResultadoPresentacion(
        clave=clave_resultado(resultado),
        id_orden=resultado.id_orden or f"Movimiento MP sin ID de orden — referencia interna fila {resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else 'sin fila'}",
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


def es_excepcion_o_caso_especial(resultado: ResultadoConciliacion) -> bool:
    """Clasificación de presentación para destacar resultados que merecen revisión visual."""

    return (
        resultado.requiere_revision
        or resultado.estado != EstadoConciliacion.CONCILIADA
        or (resultado.diferencia_control is not None and resultado.diferencia_control != Decimal("0"))
        or resultado.tiene_devolucion
        or resultado.tiene_reclamo
        or resultado.tiene_disputa
        or resultado.tiene_liquidacion_pendiente
        or resultado.es_pago_dividido
        or resultado.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS
    )


def filtrar_resultados_por_vista(resultados: Iterable[ResultadoConciliacion], vista: str) -> list[ResultadoConciliacion]:
    ordenados = sorted(resultados, key=lambda r: (r.id_orden is None, r.id_orden or "", r.numeros_fila_financiera, r.estado.value))
    if vista == "Excepciones y casos especiales":
        return [r for r in ordenados if es_excepcion_o_caso_especial(r)]
    return ordenados


def tabla_principal(filas: Iterable[FilaResultadoPresentacion]) -> list[dict[str, str]]:
    """Devuelve solo columnas seguras y encabezados visibles para cliente."""

    return [{titulo: getattr(fila, campo) for campo, titulo in ENCABEZADOS_TABLA_CLIENTE.items()} for fila in filas]


def resumen_kpis_tipado(reporte: ReporteConciliacion) -> dict[str, int | Decimal | None]:
    """Devuelve KPIs con tipos nativos para reutilizar en interfaz y exportaciones."""

    resultados = reporte.resultados
    comparables = tuple(r for r in resultados if r.diferencia_control is not None)
    financieros_sin_operacion = tuple(r for r in resultados if r.cantidad_operaciones_comerciales == 0 and r.estado != EstadoConciliacion.MOVIMIENTO_DE_FONDOS)
    comerciales_sin_movimiento = tuple(r for r in resultados if r.cantidad_operaciones_comerciales > 0 and r.cantidad_movimientos_financieros == 0)
    movimientos_fondos = tuple(r for r in resultados if r.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS)
    return {
        "Comparables": len(comparables),
        "Coincidencias exactas": sum(1 for r in comparables if r.estado == EstadoConciliacion.CONCILIADA),
        "Con diferencia": sum(1 for r in comparables if r.diferencia_control != Decimal("0")),
        "Sin venta en ML": len(financieros_sin_operacion),
        "Sin movimiento en MP": len(comerciales_sin_movimiento),
        "Requieren revisión": sum(1 for r in resultados if r.requiere_revision),
        "Movimientos de fondos": len(movimientos_fondos),
        "Utilidad informada ML": _sumar(r.utilidad_neta_informada for r in resultados),
        "Neto ML comparable": _sumar(r.neto_comercial_informado for r in comparables),
        "Neto MP comparable": _sumar(r.neto_pagos_aprobados for r in comparables),
        "Diferencia comparable": _sumar(r.diferencia_control for r in comparables),
        "Neto MP fuera del archivo ML": _sumar(r.neto_pagos_aprobados for r in financieros_sin_operacion),
    }


def resumen_kpis(reporte: ReporteConciliacion) -> dict[str, int | str]:
    monetarios = {"Utilidad informada ML", "Neto ML comparable", "Neto MP comparable", "Diferencia comparable", "Neto MP fuera del archivo ML"}
    salida: dict[str, int | str] = {}
    for nombre, valor in resumen_kpis_tipado(reporte).items():
        salida[nombre] = formato_pesos_argentino(valor) if nombre in monetarios else int(valor or 0)
    return salida


def conclusion_ejecutiva(reporte: ReporteConciliacion) -> tuple[str, str]:
    """Genera una conclusión ejecutiva sin recalcular importes ni modificar estados."""

    resultados = reporte.resultados
    comparables = tuple(r for r in resultados if r.diferencia_control is not None)
    exactas = sum(1 for r in comparables if r.estado == EstadoConciliacion.CONCILIADA and r.diferencia_control == Decimal("0"))
    con_diferencia = sum(1 for r in comparables if r.diferencia_control != Decimal("0"))
    solo_mp = sum(1 for r in resultados if r.cantidad_operaciones_comerciales == 0 and r.estado != EstadoConciliacion.MOVIMIENTO_DE_FONDOS)
    solo_ml = sum(1 for r in resultados if r.cantidad_operaciones_comerciales > 0 and r.cantidad_movimientos_financieros == 0)
    excepciones = sum(1 for r in resultados if es_excepcion_o_caso_especial(r))
    requieren_revision = sum(1 for r in resultados if es_excepcion_o_caso_especial(r) and r.requiere_revision)
    fondos = sum(1 for r in resultados if r.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS)
    mensaje = (
        f"{_frase_contador(len(comparables), 'Se comparó', 'Se compararon', 'operación', 'operaciones')}: "
        f"{_frase_contador(exactas, '', '', 'coincide exactamente', 'coinciden exactamente')} y "
        f"{_frase_contador(con_diferencia, '', '', 'presenta diferencias', 'presentan diferencias')}. "
        f"Se detectaron {_sustantivo_contado(excepciones, 'resultado con excepciones o condiciones especiales', 'resultados con excepciones o condiciones especiales')}, "
        f"de los cuales {_frase_contador(requieren_revision, '', '', 'requiere revisión manual', 'requieren revisión manual')}. "
        f"Además, existen {_sustantivo_contado(solo_mp, 'grupo presente solo en Mercado Pago', 'grupos presentes solo en Mercado Pago')}, "
        f"{_sustantivo_contado(solo_ml, 'operación presente solo en Mercado Libre', 'operaciones presentes solo en Mercado Libre')} y "
        f"{_sustantivo_contado(fondos, 'movimiento de fondos informado por separado', 'movimientos de fondos informados por separado')}."
    )
    severidad = "ok" if con_diferencia == 0 and excepciones == 0 and solo_mp == 0 and solo_ml == 0 else "advertencia"
    return mensaje, severidad


def _frase_contador(cantidad: int, verbo_singular: str, verbo_plural: str, singular: str, plural: str) -> str:
    verbo = verbo_singular if cantidad == 1 else verbo_plural
    sujeto = singular if cantidad == 1 else plural
    partes = [verbo, str(cantidad), sujeto]
    return " ".join(p for p in partes if p)


def _sustantivo_contado(cantidad: int, singular: str, plural: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural}"


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
        "ID de orden": resultado.id_orden or f"Movimiento MP sin ID de orden — referencia interna fila {resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else 'sin fila'}",
        "Estado": etiqueta_estado(resultado.estado),
        "Motivos": ", ".join(m.value for m in resultado.motivos) or "—",
        "Explicaciones": " | ".join(resultado.explicaciones) or "—",
        "Filas comerciales de origen": ", ".join(map(str, resultado.numeros_fila_comercial)) or "—",
        "Filas financieras de origen": ", ".join(map(str, resultado.numeros_fila_financiera)) or "—",
        "Cantidad de pagos aprobados": resultado.cantidad_pagos_aprobados,
        "Pago dividido": formato_bool(resultado.es_pago_dividido),
        "Neto comercial informado": formato_pesos_argentino(resultado.neto_comercial_informado),
        "Neto aprobado de Mercado Pago del resultado": formato_pesos_argentino(resultado.neto_pagos_aprobados),
        "Diferencia de control — operaciones comparables": formato_pesos_argentino(resultado.diferencia_control),
        "Impacto de pagos de envío": formato_pesos_argentino(resultado.impacto_pagos_envio),
        "Impacto de devoluciones": formato_pesos_argentino(resultado.impacto_devoluciones),
        "Impacto de reclamos/disputas": formato_pesos_argentino(resultado.impacto_reclamos_disputas),
        "Impacto de otros movimientos": formato_pesos_argentino(resultado.impacto_otros),
        "Neto financiero total": formato_pesos_argentino(resultado.neto_financiero_total),
        "Utilidad neta informada": formato_pesos_argentino(resultado.utilidad_neta_informada),
        "Indicadores de revisión": "Sí" if resultado.requiere_revision or resultado.tiene_duplicados or resultado.tiene_movimiento_desconocido else "No",
    }


def detalle_cliente(resultado: ResultadoConciliacion) -> dict[str, str | int]:
    return {
        "ID de orden": resultado.id_orden or f"Movimiento MP sin ID de orden — referencia interna fila {resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else 'sin fila'}",
        "Estado": etiqueta_estado(resultado.estado),
        "Neto informado ML": formato_pesos_argentino(resultado.neto_comercial_informado),
        "Neto aprobado MP": formato_pesos_argentino(resultado.neto_pagos_aprobados),
        "Neto financiero total": formato_pesos_argentino(resultado.neto_financiero_total),
        "Utilidad informada ML": formato_pesos_argentino(resultado.utilidad_neta_informada),
        "Diferencia": formato_pesos_argentino(resultado.diferencia_control),
        "Pago dividido": formato_bool(resultado.es_pago_dividido),
        "Devolución": formato_bool(resultado.tiene_devolucion),
        "Reclamo o disputa": formato_bool(resultado.tiene_reclamo or resultado.tiene_disputa),
        "Pendiente de acreditación": formato_bool(resultado.tiene_liquidacion_pendiente),
        "Requiere revisión": formato_bool(resultado.requiere_revision),
        "Explicación": " | ".join(resultado.explicaciones) or "Sin observaciones adicionales.",
    }


def detalle_tecnico_seguro(resultado: ResultadoConciliacion) -> dict[str, str | int]:
    return {
        "Motivos internos": ", ".join(m.value for m in resultado.motivos) or "—",
        "Filas comerciales de origen": ", ".join(map(str, resultado.numeros_fila_comercial)) or "—",
        "Filas financieras de origen": ", ".join(map(str, resultado.numeros_fila_financiera)) or "—",
        "Versión de regla": resultado.version_regla or VERSION_REGLA_CONCILIACION,
        "Cantidad de pagos aprobados": resultado.cantidad_pagos_aprobados,
        "Cantidad de movimientos financieros": resultado.cantidad_movimientos_financieros,
        "Tolerancia aplicada": formato_pesos_argentino(resultado.tolerancia_aplicada),
    }
