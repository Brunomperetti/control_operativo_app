"""Dominio inmutable del diagnóstico comercial ML oficial / Eccomapp."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.official_sale import VentaOficialMercadoLibre


class EstadoCruceMlEccomapp(StrEnum):
    COINCIDENCIA_EXACTA = "COINCIDENCIA_EXACTA"
    COINCIDENCIA_POR_GRUPO = "COINCIDENCIA_POR_GRUPO"
    SOLO_ML = "SOLO_ML"
    SOLO_ECCOMAPP = "SOLO_ECCOMAPP"
    IDENTIFICADOR_INCOMPLETO = "IDENTIFICADOR_INCOMPLETO"
    IDENTIFICADOR_AMBIGUO = "IDENTIFICADOR_AMBIGUO"
    DUPLICADO_ML = "DUPLICADO_ML"
    DUPLICADO_ECCOMAPP = "DUPLICADO_ECCOMAPP"


class EstadoAptitudUtilidad(StrEnum):
    UTILIDAD_CALCULABLE = "UTILIDAD_CALCULABLE"
    SIN_COSTO = "SIN_COSTO"
    SIN_TOTAL_ML = "SIN_TOTAL_ML"
    SIN_VINCULO_ECCOMAPP = "SIN_VINCULO_ECCOMAPP"
    VINCULO_AMBIGUO = "VINCULO_AMBIGUO"
    DATOS_CRITICOS_INCOMPLETOS = "DATOS_CRITICOS_INCOMPLETOS"


@dataclass(frozen=True)
class CasoCruceMlEccomapp:
    clave: str
    id_grupo: str | None
    ids_venta_ml: tuple[str, ...]
    ids_orden_eccomapp: tuple[str, ...]
    ventas_ml: tuple[VentaOficialMercadoLibre, ...]
    operaciones_eccomapp: tuple[OperacionComercial, ...]
    estado: EstadoCruceMlEccomapp
    aptitud_utilidad: EstadoAptitudUtilidad
    motivo: str
    accion_recomendada: str
    fecha: datetime | None
    total_ml: Decimal | None
    costo_eccomapp: Decimal | None

    @property
    def requiere_revision(self) -> bool:
        return self.estado not in {EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA, EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO} or self.aptitud_utilidad != EstadoAptitudUtilidad.UTILIDAD_CALCULABLE


@dataclass(frozen=True)
class DiagnosticoMlEccomapp:
    casos: tuple[CasoCruceMlEccomapp, ...]
    cantidad_filas_ml: int
    cantidad_ventas_unicas_ml: int
    cantidad_grupos_ml: int
    cantidad_filas_eccomapp: int
    cantidad_operaciones_unicas_eccomapp: int
    cantidad_grupos_eccomapp: int
    cantidad_coincidencias_exactas: int
    cantidad_coincidencias_por_grupo: int
    cantidad_solo_ml: int
    cantidad_solo_eccomapp: int
    cantidad_identificador_incompleto: int
    cantidad_ambiguas: int
    cantidad_duplicadas: int
    cantidad_apta_utilidad: int
    cantidad_no_apta_utilidad: int

    @property
    def cantidad_coincidencias(self) -> int:
        return self.cantidad_coincidencias_exactas + self.cantidad_coincidencias_por_grupo
