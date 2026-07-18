"""Utilidades puras para el ciclo seguro de sesión de la interfaz."""

from collections.abc import MutableMapping
from decimal import Decimal
import hashlib
import json
from typing import Any

SESSION_KEYS_TO_CLEAR = (
    "archivo_ml",
    "archivo_mp",
    "hash_ml",
    "hash_mp",
    "normalizacion",
    "cobertura",
    "reporte",
    "firma_procesamiento",
    "firma_actual",
    "filtro_estados",
    "filtro_busqueda_orden",
    "filtro_solo_revision",
    "filtro_solo_divididos",
    "detalle_operacion",
)

RESULT_KEYS_TO_CLEAR = (
    "normalizacion",
    "cobertura",
    "reporte",
    "firma_procesamiento",
    "firma_actual",
    "filtro_estados",
    "filtro_busqueda_orden",
    "filtro_solo_revision",
    "filtro_solo_divididos",
    "detalle_operacion",
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
