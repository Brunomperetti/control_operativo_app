"""Resultados y problemas de validación."""

from dataclasses import dataclass

from kiki_control.domain.enums import SeveridadValidacion


@dataclass(frozen=True)
class ProblemaValidacion:
    """Problema detectado durante la inspección estructural."""

    codigo: str
    mensaje: str
    severidad: SeveridadValidacion
    columna: str | None = None
    detalle: str | None = None
