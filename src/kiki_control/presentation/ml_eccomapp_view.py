"""Proyección de negocio del diagnóstico ML oficial / Eccomapp."""

from collections import Counter
from kiki_control.domain.ml_eccomapp_diagnostic import DiagnosticoMlEccomapp


def conclusion_ejecutiva_ml_eccomapp(d):
    causas = Counter(c.motivo for c in d.casos if c.requiere_revision)
    principales = "; ".join(f"{texto} ({n})" for texto, n in causas.most_common(3)) or "sin causas pendientes"
    return (f"{d.cantidad_coincidencias} operaciones o grupos ML tienen contraparte Eccomapp; "
            f"{d.cantidad_solo_ml} están solo en ML y {d.cantidad_solo_eccomapp} solo en Eccomapp. "
            f"{d.cantidad_apta_utilidad} son utilizables para calcular utilidad y {d.cantidad_no_apta_utilidad} requieren revisión o datos adicionales. "
            f"Principales causas: {principales}.")


def filas_casos_ml_eccomapp(casos):
    return [{
        "Grupo u orden": c.id_grupo or "Sin identificador", "IDs venta ML": ", ".join(c.ids_venta_ml),
        "IDs orden Eccomapp": ", ".join(c.ids_orden_eccomapp), "Estado de vinculación": c.estado.value,
        "Aptitud para utilidad": c.aptitud_utilidad.value, "Fecha": c.fecha,
        "Filas ML": ", ".join(str(v.fila_origen) for v in c.ventas_ml),
        "Filas Eccomapp": ", ".join(str(o.numero_fila_origen) for o in c.operaciones_eccomapp),
        "Total ML": c.total_ml, "Costo Eccomapp": c.costo_eccomapp, "Motivo": c.motivo,
        "Acción recomendada": c.accion_recomendada,
    } for c in casos]


def resumen_estados_ml_eccomapp(d):
    counts = Counter(c.estado.value for c in d.casos)
    return [{"Estado de vinculación": estado, "Cantidad": cantidad} for estado, cantidad in sorted(counts.items())]
