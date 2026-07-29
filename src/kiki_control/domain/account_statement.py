"""Dominio del estado de cuenta diario de Mercado Pago."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class EstadoVinculacionEstadoCuentaMp(StrEnum):
    VINCULADO_SETTLEMENT = "VINCULADO_SETTLEMENT"
    SIN_VINCULO_SETTLEMENT = "SIN_VINCULO_SETTLEMENT"
    ID_VACIO = "ID_VACIO"
    ID_AMBIGUO = "ID_AMBIGUO"


class CategoriaEstadoCuentaMp(StrEnum):
    ASOCIADO_A_VENTA_ML = "ASOCIADO_A_VENTA_ML"
    OTRO_INGRESO_NO_ML_IDENTIFICADO = "OTRO_INGRESO_NO_ML_IDENTIFICADO"
    SALIDA_O_AJUSTE_IDENTIFICADO = "SALIDA_O_AJUSTE_IDENTIFICADO"
    SIN_ASOCIACION_SUFICIENTE = "SIN_ASOCIACION_SUFICIENTE"


@dataclass(frozen=True)
class MovimientoEstadoCuentaMp:
    numero_fila_origen: int
    fecha_liberacion: datetime
    tipo_movimiento_original: str
    reference_id: str | None
    importe_neto: Decimal
    saldo_parcial: Decimal | None
    hash_importacion: str
    hoja_origen: str


@dataclass(frozen=True)
class ResumenEstadoCuentaMp:
    saldo_inicial: Decimal
    creditos_informados: Decimal
    debitos_informados: Decimal
    saldo_final_informado: Decimal
    movimientos: tuple[MovimientoEstadoCuentaMp, ...]
    fecha_desde: datetime
    fecha_hasta: datetime

    @property
    def variacion_neta(self) -> Decimal:
        return sum((m.importe_neto for m in self.movimientos), Decimal("0"))

    @property
    def saldo_final_calculado(self) -> Decimal:
        return self.saldo_inicial + self.variacion_neta

    @property
    def diferencia_control(self) -> Decimal:
        return self.saldo_final_calculado - self.saldo_final_informado


@dataclass(frozen=True)
class MovimientoEstadoCuentaClasificado:
    movimiento: MovimientoEstadoCuentaMp
    estado_vinculacion: EstadoVinculacionEstadoCuentaMp
    categoria: CategoriaEstadoCuentaMp
    subtipo: str
    motivo: str
    accion_recomendada: str
    fila_settlement: int | None = None
    id_grupo_ml: str | None = None


@dataclass(frozen=True)
class ControlEstadoCuentaMp:
    resumen: ResumenEstadoCuentaMp
    movimientos: tuple[MovimientoEstadoCuentaClasificado, ...]

    @property
    def reference_ids_unicos(self) -> int:
        return len({m.movimiento.reference_id for m in self.movimientos if m.movimiento.reference_id})

    @property
    def lineas_vinculadas(self) -> int:
        return sum(m.estado_vinculacion == EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT for m in self.movimientos)

    @property
    def operaciones_settlement_vinculadas(self) -> int:
        return len({m.movimiento.reference_id for m in self.movimientos if m.estado_vinculacion == EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT})

    @property
    def suma_categorias(self) -> Decimal:
        return sum((m.movimiento.importe_neto for m in self.movimientos), Decimal("0"))

    @property
    def diferencia_cobertura(self) -> Decimal:
        return self.suma_categorias - self.resumen.variacion_neta
