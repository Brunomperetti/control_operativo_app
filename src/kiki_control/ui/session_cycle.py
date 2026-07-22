"""Utilidades puras para el ciclo seguro de sesión de la interfaz."""

from collections.abc import MutableMapping
from decimal import Decimal
import hashlib
import json
from typing import Any

SESSION_KEYS_TO_CLEAR = (
    "archivo_ml",
    "archivo_mp",
    "archivo_ml_oficial",
    "archivo_eccomapp",
    "hash_ml",
    "hash_mp",
    "hash_ml_oficial",
    "hash_eccomapp",
    "normalizacion",
    "cobertura",
    "cobertura_consolidada",
    "reporte",
    "reporte_comercial",
    "reporte_financiero",
    "reporte_consolidado",
    "firma_procesamiento",
    "firma_actual",
    "filtro_estados",
    "filtro_busqueda_orden",
    "filtro_solo_revision",
    "filtro_solo_divididos",
    "filtro_solo_diferencia",
    "filtro_solo_faltantes",
    "detalle_operacion",
    "vista_resultados",
    "revision_tipo",
    "revision_busqueda",
    "revision_detalle",
    "filtro_motivo_revision",
)

RESULT_KEYS_TO_CLEAR = (
    "normalizacion",
    "cobertura",
    "cobertura_consolidada",
    "reporte",
    "reporte_comercial",
    "reporte_financiero",
    "reporte_consolidado",
    "firma_procesamiento",
    "firma_actual",
    "filtro_estados",
    "filtro_busqueda_orden",
    "filtro_solo_revision",
    "filtro_solo_divididos",
    "filtro_solo_diferencia",
    "filtro_solo_faltantes",
    "detalle_operacion",
    "vista_resultados",
    "revision_tipo",
    "revision_busqueda",
    "revision_detalle",
    "filtro_motivo_revision",
)

VIEW_FILTER_KEYS_TO_CLEAR = (
    "filtro_estados",
    "filtro_busqueda_orden",
    "filtro_solo_revision",
    "filtro_solo_divididos",
    "filtro_solo_diferencia",
    "filtro_solo_faltantes",
    "detalle_operacion",
    "filtro_motivo_revision",
)


def tolerancia_canonica(tolerancia: Decimal) -> str:
    """Devuelve una representación textual determinista para una tolerancia Decimal."""
    return str(tolerancia.normalize())


def construir_firma_procesamiento(hash_ml: str, hash_mp: str, zona_horaria: str, tolerancia: Decimal) -> str:
    """Construye una firma SHA-256 determinista para archivos y configuración."""
    payload = {
        "hash_ml": hash_ml,
        "hash_mp": hash_mp,
        "zona_horaria": zona_horaria,
        "tolerancia": tolerancia_canonica(tolerancia),
    }
    serializado = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()



def construir_firma_procesamiento_tres_fuentes(hash_ml_oficial: str | None, hash_eccomapp: str | None, hash_mp: str | None, zona_horaria: str, tolerancia: Decimal) -> str:
    """Construye una firma SHA-256 determinística para tres archivos y configuración."""
    payload = {
        "hash_ml_oficial": hash_ml_oficial or "",
        "hash_eccomapp": hash_eccomapp or "",
        "hash_mp": hash_mp or "",
        "zona_horaria": zona_horaria,
        "tolerancia": tolerancia_canonica(tolerancia),
    }
    serializado = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()

def detectar_cambio(valor_anterior: Any, valor_actual: Any) -> bool:
    """Indica si una entrada relevante cambió, incluyendo altas y bajas de archivo."""
    return valor_anterior != valor_actual


def limpiar_claves_conocidas(estado: MutableMapping[str, Any], claves: tuple[str, ...] = SESSION_KEYS_TO_CLEAR) -> None:
    """Elimina del estado las claves conocidas mantenidas por la aplicación."""
    for clave in claves:
        estado.pop(clave, None)


def invalidar_resultados_conocidos(estado: MutableMapping[str, Any]) -> None:
    """Elimina resultados derivados que dejan de ser confiables ante cambios de entrada."""
    limpiar_claves_conocidas(estado, RESULT_KEYS_TO_CLEAR)


def limpiar_filtros_de_vista(estado: MutableMapping[str, Any]) -> None:
    """Elimina solo filtros dependientes de la vista, sin invalidar resultados procesados."""
    limpiar_claves_conocidas(estado, VIEW_FILTER_KEYS_TO_CLEAR)


def limpiar_detalle_revision(estado: MutableMapping[str, Any]) -> None:
    """Elimina la selección de detalle de revisión sin borrar reporte ni filtros."""
    estado.pop("revision_detalle", None)


def limpiar_detalle_revision_si_obsoleto(estado: MutableMapping[str, Any], claves_validas: set[str]) -> None:
    """Evita conservar un caso seleccionado que ya no pertenece al filtro vigente."""
    seleccion = estado.get("revision_detalle")
    if seleccion is not None and seleccion not in claves_validas:
        estado.pop("revision_detalle", None)
