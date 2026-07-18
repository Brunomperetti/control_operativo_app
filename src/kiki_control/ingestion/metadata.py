"""Utilidades para construir metadatos auditables."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


def calcular_sha256(contenido: bytes) -> str:
    """Calcula el hash SHA-256 del contenido recibido."""

    return sha256(contenido).hexdigest()


def obtener_extension(nombre_archivo: str) -> str:
    """Obtiene la extensión normalizada de un nombre de archivo."""

    return Path(nombre_archivo).suffix.lower()


def fecha_actual_utc() -> datetime:
    """Devuelve una fecha auditable con zona horaria UTC."""

    return datetime.now(UTC)
