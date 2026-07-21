"""Modelos auditables para vinculación comercial ML oficial / Eccomapp."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.official_sale import VentaOficialMercadoLibre


class EstadoVinculacionComercial(str, Enum):
    """Estados estables del resultado de vinculación comercial."""

    VINCULADA = "VINCULADA"
    VINCULADA_CON_OBSERVACIONES = "VINCULADA_CON_OBSERVACIONES"
    SOLO_MERCADO_LIBRE = "SOLO_MERCADO_LIBRE"
    SOLO_ECCOMAPP = "SOLO_ECCOMAPP"
    AMBIGUA = "AMBIGUA"
    DUPLICADA = "DUPLICADA"


class MetodoVinculacionComercial(str, Enum):
    """Métodos explícitos usados para vincular por identidad externa."""

    ID_CARRITO = "ID_CARRITO"
    ID_ORDER = "ID_ORDER"
    ID_ORDER_DENTRO_DE_CARRITO = "ID_ORDER_DENTRO_DE_CARRITO"
    SIN_VINCULO = "SIN_VINCULO"


class EstadoValidacionSku(str, Enum):
    """Resultado de validación secundaria por SKU agregado de grupo."""

    COINCIDE = "COINCIDE"
    NO_DISPONIBLE_EN_AMBAS = "NO_DISPONIBLE_EN_AMBAS"
    FALTA_EN_MERCADO_LIBRE = "FALTA_EN_MERCADO_LIBRE"
    FALTA_EN_ECCOMAPP = "FALTA_EN_ECCOMAPP"
    DIFIERE = "DIFIERE"


@dataclass(frozen=True)
class ResultadoVinculacionComercial:
    """Resultado inmutable y trazable de una vinculación comercial."""

    clave_resultado: str
    id_grupo_canonico: str | None
    id_carrito: str | None
    ids_orden: tuple[str, ...]
    venta_principal_ml: VentaOficialMercadoLibre | None
    ventas_detalle_ml: tuple[VentaOficialMercadoLibre, ...]
    operaciones_eccomapp: tuple[OperacionComercial, ...]
    estado: EstadoVinculacionComercial
    metodos_vinculacion: tuple[MetodoVinculacionComercial, ...]
    estado_validacion_sku: EstadoValidacionSku
    requiere_revision: bool
    motivos: tuple[str, ...]
    explicaciones: tuple[str, ...]
    hashes_importacion_ml: tuple[str, ...]
    hashes_importacion_eccomapp: tuple[str, ...]
    filas_origen_ml: tuple[int, ...]
    filas_origen_eccomapp: tuple[int, ...]


@dataclass(frozen=True)
class ReporteVinculacionComercial:
    """Reporte agregado de resultados comerciales vinculados y pendientes."""

    resultados: tuple[ResultadoVinculacionComercial, ...]
    total_ventas_oficiales_recibidas: int
    total_operaciones_eccomapp_recibidas: int
    total_grupos_eccomapp: int
    total_grupos_vinculados: int
    total_vinculados_sin_observaciones: int
    total_vinculados_con_observaciones: int
    total_solo_mercado_libre: int
    total_solo_eccomapp: int
    total_ambiguos: int
    total_duplicados: int
    total_requieren_revision: int
    hashes_importacion_ml: tuple[str, ...]
    hashes_importacion_eccomapp: tuple[str, ...]
