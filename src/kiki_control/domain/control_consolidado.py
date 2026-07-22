"""Modelos inmutables para control financiero consolidado de tres fuentes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from kiki_control.domain.reconciliation import ResultadoConciliacion
from kiki_control.domain.commercial_link import ResultadoVinculacionComercial

VERSION_REGLA_CONTROL_CONSOLIDADO = "ML_OFICIAL_ECCOM_MP_V1"


class ErrorControlConsolidado(ValueError):
    """Error de dominio al impedir un cruce consolidado inseguro."""


class EstadoControlConsolidado(StrEnum):
    """Estados estables con prioridad determinista de control consolidado."""

    DUPLICADA_O_AMBIGUA = "DUPLICADA_O_AMBIGUA"
    SOLO_MOVIMIENTO_FINANCIERO = "SOLO_MOVIMIENTO_FINANCIERO"
    SIN_VENTA_OFICIAL = "SIN_VENTA_OFICIAL"
    SIN_COSTO_PRODUCTO = "SIN_COSTO_PRODUCTO"
    SIN_MOVIMIENTO_FINANCIERO = "SIN_MOVIMIENTO_FINANCIERO"
    EN_REVISION_FINANCIERA = "EN_REVISION_FINANCIERA"
    CON_DIFERENCIA = "CON_DIFERENCIA"
    COMPLETA = "COMPLETA"


class TipoMovimientoFinanciero(StrEnum):
    """Clasificación prudente de resultados financieros sin venta."""

    ORDEN_FINANCIERA = "ORDEN_FINANCIERA"
    MOVIMIENTO_DE_FONDOS = "MOVIMIENTO_DE_FONDOS"


@dataclass(frozen=True)
class IndicadoresFinancieros:
    """Indicadores financieros conservados sin recalcular reglas fiscales."""

    tiene_liquidacion_pendiente: bool
    tiene_devolucion: bool
    tiene_reclamo: bool
    tiene_disputa: bool
    tiene_pago_dividido: bool
    tiene_movimiento_desconocido: bool
    tiene_duplicados: bool
    tiene_pago_envio: bool


@dataclass(frozen=True)
class ResultadoControlConsolidado:
    """Resultado consolidado inmutable, auditable y libre de datos personales."""

    clave_resultado: str
    id_grupo_canonico: str | None
    ids_orden: tuple[str, ...]
    tiene_mercado_libre_oficial: bool
    tiene_eccomapp: bool
    tiene_mercado_pago: bool
    tipo_movimiento_financiero: TipoMovimientoFinanciero | None
    monto_venta_ml: Decimal | None
    cargo_venta_impuestos_ml: Decimal | None
    ingresos_envio_ml: Decimal | None
    costo_envio_ml: Decimal | None
    descuentos_bonificaciones_ml: Decimal | None
    anulaciones_reembolsos_ml: Decimal | None
    total_informado_ml: Decimal | None
    monto_venta_eccomapp_informado: Decimal | None
    costo_productos_eccomapp: Decimal | None
    costo_envio_seller_eccomapp_informado: Decimal | None
    neto_mp_eccomapp_informado: Decimal | None
    utilidad_eccomapp_informada: Decimal | None
    neto_aprobado_mp: Decimal | None
    neto_financiero_total_mp: Decimal | None
    impacto_pagos_envio_mp: Decimal | None
    impacto_devoluciones_mp: Decimal | None
    impacto_reclamos_disputas_mp: Decimal | None
    impacto_otros_mp: Decimal | None
    diferencia_venta_ml_eccomapp: Decimal | None
    diferencia_neto_ml_eccomapp: Decimal | None
    diferencia_ml_mp: Decimal | None
    utilidad_preliminar_control: Decimal | None
    tolerancia: Decimal
    estado: EstadoControlConsolidado
    requiere_revision: bool
    motivos: tuple[str, ...]
    explicaciones: tuple[str, ...]
    indicadores_financieros: IndicadoresFinancieros
    version_regla: str
    hashes_importacion_ml: tuple[str, ...]
    hashes_importacion_eccomapp: tuple[str, ...]
    hashes_importacion_mp: tuple[str, ...]
    filas_origen_ml: tuple[int, ...]
    filas_origen_eccomapp: tuple[int, ...]
    filas_origen_mp: tuple[int, ...]
    claves_resultados_comerciales: tuple[str, ...]
    claves_resultados_financieros: tuple[str, ...]


@dataclass(frozen=True)
class ReporteControlConsolidado:
    """Reporte consolidado que particiona exactamente ambos reportes de entrada."""

    resultados: tuple[ResultadoControlConsolidado, ...]
    version_regla: str
    tolerancia: Decimal
    total_resultados_comerciales_recibidos: int
    total_resultados_financieros_recibidos: int
    total_resultados: int
    total_requieren_revision: int
    total_completa: int
    total_con_diferencia: int
    total_sin_movimiento_financiero: int
    total_solo_movimiento_financiero: int
    total_sin_venta_oficial: int
    total_sin_costo_producto: int
    total_en_revision_financiera: int
    total_duplicada_o_ambigua: int
    suma_total_informado_ml: Decimal
    suma_neto_aprobado_mp: Decimal
    suma_costo_productos_eccomapp: Decimal
