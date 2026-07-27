"""Modelos de dominio para la ingesta inicial."""

from dataclasses import dataclass
from datetime import datetime

from kiki_control.domain.enums import TipoFuente
from kiki_control.validation.results import ProblemaValidacion


@dataclass(frozen=True)
class MetadatosArchivo:
    """Metadatos auditables de un archivo inspeccionado."""

    nombre_original: str
    extension: str
    tamaño_bytes: int
    sha256: str
    fecha_inspeccion: datetime
    tipo_fuente: TipoFuente
    nombre_hoja: str | None
    cantidad_filas: int
    columnas_encontradas: tuple[str, ...]


@dataclass(frozen=True)
class ResultadoInspeccion:
    """Resultado público de la inspección estructural de un archivo."""

    metadatos: MetadatosArchivo
    fuente_detectada: TipoFuente
    es_valido: bool
    errores: tuple[ProblemaValidacion, ...]
    advertencias: tuple[ProblemaValidacion, ...]
