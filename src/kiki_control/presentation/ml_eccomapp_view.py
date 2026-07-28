"""Proyección de negocio del diagnóstico ML oficial / Eccomapp.

Este módulo es deliberadamente una capa de presentación: los enums y los textos
de auditoría del dominio no se modifican.
"""

from collections import Counter
from datetime import datetime
from decimal import Decimal

from kiki_control.domain.ml_eccomapp_diagnostic import (
    EstadoAptitudUtilidad,
    EstadoCruceMlEccomapp,
)


ETIQUETAS_ESTADO = {
    EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA: "Coincidencia exacta",
    EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO: "Coincidencia agrupada por carrito u orden",
    EstadoCruceMlEccomapp.SOLO_ML: "Solo en Mercado Libre",
    EstadoCruceMlEccomapp.SOLO_ECCOMAPP: "Solo en Eccomapp",
    EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO: "Identificación ambigua",
    EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO: "Identificación incompleta",
    EstadoCruceMlEccomapp.DUPLICADO_ML: "Identificación duplicada en Mercado Libre",
    EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP: "Identificación duplicada en Eccomapp",
}

ETIQUETAS_APTITUD = {
    EstadoAptitudUtilidad.UTILIDAD_CALCULABLE: "Apta para calcular utilidad",
    EstadoAptitudUtilidad.SIN_COSTO: "Sin costo informado",
    EstadoAptitudUtilidad.SIN_TOTAL_ML: "Sin total informado por Mercado Libre",
    EstadoAptitudUtilidad.SIN_VINCULO_ECCOMAPP: "Sin operación correspondiente en Eccomapp",
    EstadoAptitudUtilidad.VINCULO_AMBIGUO: "Vinculación ambigua",
    EstadoAptitudUtilidad.DATOS_CRITICOS_INCOMPLETOS: "Información necesaria incompleta",
}


def etiqueta_estado_ml_eccomapp(estado: EstadoCruceMlEccomapp) -> str:
    return ETIQUETAS_ESTADO[estado]


def etiqueta_aptitud_ml_eccomapp(aptitud: EstadoAptitudUtilidad) -> str:
    return ETIQUETAS_APTITUD[aptitud]


def formato_fecha_ml_eccomapp(fecha: datetime | None) -> str:
    """Formatea sin convertir ni reinterpretar la zona horaria almacenada."""
    return "Sin fecha informada" if fecha is None else fecha.strftime("%d/%m/%Y %H:%M")


def motivo_visible_ml_eccomapp(caso) -> str:
    if caso.estado == EstadoCruceMlEccomapp.SOLO_ML:
        if _es_total_cero_con_anulaciones(caso):
            return ("La operación tiene total comercial cero y presenta anulaciones, devoluciones o "
                    "reembolsos. No debe considerarse automáticamente una venta faltante.")
        return ("No se encontró una operación correspondiente en Eccomapp utilizando el ID de "
                "carrito o el ID de orden.")
    if caso.estado == EstadoCruceMlEccomapp.SOLO_ECCOMAPP:
        return "No se encontró una venta correspondiente en Mercado Libre utilizando el ID de carrito o el ID de orden."
    return caso.motivo or "Sin información adicional."


def accion_visible_ml_eccomapp(caso) -> str:
    if caso.estado == EstadoCruceMlEccomapp.SOLO_ML:
        return "Verificar si la operación fue cancelada, devuelta o excluida del archivo Eccomapp."
    if caso.estado == EstadoCruceMlEccomapp.SOLO_ECCOMAPP:
        return "Verificar el ID comercial y la cobertura del archivo de Mercado Libre."
    return caso.accion_recomendada or "Sin acción requerida."


def _es_total_cero_con_anulaciones(caso) -> bool:
    return caso.total_ml == Decimal("0") and any(
        v.anulaciones_reembolsos is not None and v.anulaciones_reembolsos != Decimal("0")
        for v in caso.ventas_ml
    )


def conclusion_ejecutiva_ml_eccomapp(d) -> str:
    solo_ec = ("ninguno presente únicamente en Eccomapp" if d.cantidad_solo_eccomapp == 0
               else f"{d.cantidad_solo_eccomapp} grupos presentes únicamente en Eccomapp")
    return (
        f"El archivo contiene {d.cantidad_ventas_unicas_ml} ventas únicas de Mercado Libre y "
        f"{d.cantidad_operaciones_unicas_eccomapp} operaciones únicas de Eccomapp. "
        f"Al agruparlas por carrito u orden comercial, se encontraron {d.cantidad_coincidencias} grupos coincidentes. "
        f"Hay {d.cantidad_solo_ml} grupos presentes solo en Mercado Libre y {solo_ec}. "
        f"De los grupos analizados, {d.cantidad_apta_utilidad} pueden utilizarse para calcular utilidad y "
        f"{d.cantidad_no_apta_utilidad} requieren revisión o información adicional. "
        "Una coincidencia agrupada puede contener varias ventas o filas de Mercado Libre y una o más operaciones de Eccomapp."
    )


def filas_casos_ml_eccomapp(casos):
    return [{
        "Grupo u orden": c.id_grupo or "Sin ID informado",
        "IDs venta ML": ", ".join(c.ids_venta_ml) or "Sin ID informado",
        "IDs orden Eccomapp": ", ".join(c.ids_orden_eccomapp) or "Sin ID informado",
        "Estado de vinculación": etiqueta_estado_ml_eccomapp(c.estado),
        "Aptitud para utilidad": etiqueta_aptitud_ml_eccomapp(c.aptitud_utilidad),
        "Fecha": formato_fecha_ml_eccomapp(c.fecha),
        "Filas ML": ", ".join(str(v.fila_origen) for v in c.ventas_ml) or "Sin dato",
        "Filas Eccomapp": ", ".join(str(o.numero_fila_origen) for o in c.operaciones_eccomapp) or "Sin dato",
        "Total ML": c.total_ml if c.total_ml is not None else "Sin dato",
        "Costo Eccomapp": c.costo_eccomapp if c.costo_eccomapp is not None else "Sin costo informado",
        "Motivo": motivo_visible_ml_eccomapp(c),
        "Acción recomendada": accion_visible_ml_eccomapp(c),
    } for c in casos]


def resumen_estados_ml_eccomapp(d):
    counts = Counter(c.estado for c in d.casos)
    return [{"Estado de vinculación": etiqueta_estado_ml_eccomapp(estado), "Cantidad": cantidad}
            for estado, cantidad in sorted(counts.items(), key=lambda item: etiqueta_estado_ml_eccomapp(item[0]))]
