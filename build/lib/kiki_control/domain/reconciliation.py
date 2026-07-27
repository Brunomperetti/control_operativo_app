"""Modelos de dominio para conciliación auditable."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


VERSION_REGLA_CONCILIACION = "ML_MP_ID_ORDER_NETO_V1"


class EstadoConciliacion(StrEnum):
    """Estados estables de conciliación."""

    CONCILIADA = "CONCILIADA"
    CONCILIADA_CON_DIFERENCIA_MENOR = "CONCILIADA_CON_DIFERENCIA_MENOR"
    CONCILIADA_CON_DIFERENCIA = "CONCILIADA_CON_DIFERENCIA"
    PENDIENTE_ACREDITACION = "PENDIENTE_ACREDITACION"
    OPERACION_SIN_MOVIMIENTO_FINANCIERO = "OPERACION_SIN_MOVIMIENTO_FINANCIERO"
    MOVIMIENTO_SIN_OPERACION_COMERCIAL = "MOVIMIENTO_SIN_OPERACION_COMERCIAL"
    DEVUELTA = "DEVUELTA"
    EN_RECLAMO = "EN_RECLAMO"
    EN_REVISION = "EN_REVISION"
    DUPLICADA = "DUPLICADA"
    MOVIMIENTO_DE_FONDOS = "MOVIMIENTO_DE_FONDOS"


class MotivoConciliacion(StrEnum):
    """Códigos auditables de motivos de conciliación."""

    COINCIDENCIA_NETA_EXACTA = "COINCIDENCIA_NETA_EXACTA"
    DIFERENCIA_DENTRO_TOLERANCIA = "DIFERENCIA_DENTRO_TOLERANCIA"
    DIFERENCIA_SUPERA_TOLERANCIA = "DIFERENCIA_SUPERA_TOLERANCIA"
    PAGO_DIVIDIDO = "PAGO_DIVIDIDO"
    SIN_MOVIMIENTO_FINANCIERO = "SIN_MOVIMIENTO_FINANCIERO"
    SIN_OPERACION_COMERCIAL = "SIN_OPERACION_COMERCIAL"
    ORDEN_AUSENTE = "ORDEN_AUSENTE"
    DEVOLUCION_DETECTADA = "DEVOLUCION_DETECTADA"
    RECLAMO_DETECTADO = "RECLAMO_DETECTADO"
    DISPUTA_DETECTADA = "DISPUTA_DETECTADA"
    LIQUIDACION_PENDIENTE = "LIQUIDACION_PENDIENTE"
    MOVIMIENTO_DESCONOCIDO = "MOVIMIENTO_DESCONOCIDO"
    OPERACION_COMERCIAL_DUPLICADA = "OPERACION_COMERCIAL_DUPLICADA"
    MOVIMIENTO_FINANCIERO_DUPLICADO = "MOVIMIENTO_FINANCIERO_DUPLICADO"
    PAYOUT_SIN_ORDEN = "PAYOUT_SIN_ORDEN"


@dataclass(frozen=True)
class ResultadoConciliacion:
    """Resultado inmutable para una orden o movimiento financiero sin orden."""

    id_orden: str | None
    hashes_importacion_comercial: tuple[str, ...]
    hashes_importacion_financiera: tuple[str, ...]
    numeros_fila_comercial: tuple[int, ...]
    numeros_fila_financiera: tuple[int, ...]
    fecha_procesamiento_utc: datetime
    version_regla: str
    estado: EstadoConciliacion
    motivos: tuple[MotivoConciliacion, ...]
    explicaciones: tuple[str, ...]
    requiere_revision: bool
    es_pago_dividido: bool
    cantidad_operaciones_comerciales: int
    cantidad_movimientos_financieros: int
    cantidad_pagos_aprobados: int
    neto_comercial_informado: Decimal | None
    neto_pagos_aprobados: Decimal | None
    diferencia_control: Decimal | None
    impacto_pagos_envio: Decimal
    impacto_devoluciones: Decimal
    impacto_reclamos_disputas: Decimal
    impacto_otros: Decimal
    neto_financiero_total: Decimal
    utilidad_neta_informada: Decimal | None
    tolerancia_aplicada: Decimal
    tiene_devolucion: bool
    tiene_reclamo: bool
    tiene_disputa: bool
    tiene_pago_envio: bool
    tiene_movimiento_desconocido: bool
    tiene_liquidacion_pendiente: bool
    tiene_duplicados: bool


@dataclass(frozen=True)
class ReporteConciliacion:
    """Reporte agregado de conciliación con totales derivados."""

    resultados: tuple[ResultadoConciliacion, ...]
    fecha_procesamiento_utc: datetime
    version_regla: str
    tolerancia: Decimal
    cantidad_operaciones_comerciales: int
    cantidad_movimientos_financieros: int

    @property
    def total_resultados(self) -> int:
        return len(self.resultados)

    @property
    def total_conciliadas(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.CONCILIADA)

    @property
    def total_con_diferencias(self) -> int:
        return sum(1 for r in self.resultados if r.estado in {EstadoConciliacion.CONCILIADA_CON_DIFERENCIA, EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR})

    @property
    def total_pendientes(self) -> int:
        return sum(1 for r in self.resultados if r.estado in {EstadoConciliacion.PENDIENTE_ACREDITACION, EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO})

    @property
    def total_devueltas(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.DEVUELTA)

    @property
    def total_en_reclamo(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.EN_RECLAMO)

    @property
    def total_en_revision(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.EN_REVISION)

    @property
    def total_duplicadas(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.DUPLICADA)

    @property
    def total_movimientos_fondos(self) -> int:
        return sum(1 for r in self.resultados if r.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS)
