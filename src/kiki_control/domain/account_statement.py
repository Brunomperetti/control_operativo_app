"""Dominio del estado de cuenta diario de Mercado Pago."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from collections import Counter


class EstadoVinculacionEstadoCuentaMp(StrEnum):
    VINCULADO_SETTLEMENT = "VINCULADO_SETTLEMENT"
    VINCULADO_SIN_ORIGEN_COMERCIAL = "VINCULADO_SIN_ORIGEN_COMERCIAL"
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
    filas_settlement: tuple[int, ...] = tuple()
    id_grupo_ml: str | None = None

    @property
    def fila_settlement(self) -> int | None:
        """Primera fila, conservada únicamente como atajo de compatibilidad."""
        return self.filas_settlement[0] if self.filas_settlement else None


@dataclass(frozen=True)
class EstadisticasMovimientosMp:
    cantidad_movimientos: int
    reference_ids_unicos: int
    importes_positivos: Decimal
    importes_negativos: Decimal
    impacto_neto: Decimal


@dataclass(frozen=True)
class GrupoSettlementPorOperacionMp:
    """Todas las filas settlement que describen un mismo ID de operación."""

    id_operacion_mp: str
    filas_origen: tuple[int, ...]
    ids_orden: tuple[str, ...]
    canales: tuple[str, ...]
    plataformas: tuple[str, ...]
    ids_grupo_ml: tuple[str, ...]
    movimientos: tuple[object, ...]
    es_ambiguo: bool
    motivo_ambiguedad: str | None


@dataclass(frozen=True)
class ControlEstadoCuentaMp:
    resumen: ResumenEstadoCuentaMp
    movimientos: tuple[MovimientoEstadoCuentaClasificado, ...]

    @property
    def cantidad_lineas_entrada(self) -> int:
        return len(self.resumen.movimientos)

    def _frecuencias_clasificacion(self) -> Counter[int]:
        return Counter(m.movimiento.numero_fila_origen for m in self.movimientos)

    @property
    def cantidad_lineas_clasificadas(self) -> int:
        frecuencias = self._frecuencias_clasificacion()
        return sum(frecuencias[m.numero_fila_origen] == 1 for m in self.resumen.movimientos)

    @property
    def cantidad_no_clasificadas(self) -> int:
        frecuencias = self._frecuencias_clasificacion()
        return sum(frecuencias[m.numero_fila_origen] == 0 for m in self.resumen.movimientos)

    @property
    def cantidad_clasificadas_mas_de_una_vez(self) -> int:
        frecuencias = self._frecuencias_clasificacion()
        return sum(frecuencias[m.numero_fila_origen] > 1 for m in self.resumen.movimientos)

    @property
    def cobertura_completa(self) -> bool:
        return (
            self.cantidad_lineas_clasificadas == self.cantidad_lineas_entrada
            and self.cantidad_no_clasificadas == 0
            and self.cantidad_clasificadas_mas_de_una_vez == 0
            and self.diferencia_cobertura_monetaria == Decimal("0")
        )

    @property
    def reference_ids_unicos(self) -> int:
        return len({m.movimiento.reference_id for m in self.movimientos if m.movimiento.reference_id})

    @property
    def lineas_vinculadas(self) -> int:
        return sum(m.estado_vinculacion in self._estados_vinculados for m in self.movimientos)

    @property
    def _estados_vinculados(self) -> frozenset[EstadoVinculacionEstadoCuentaMp]:
        return frozenset({
            EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT,
            EstadoVinculacionEstadoCuentaMp.VINCULADO_SIN_ORIGEN_COMERCIAL,
        })

    @property
    def lineas_sin_vinculo_settlement(self) -> int:
        return sum(m.estado_vinculacion == EstadoVinculacionEstadoCuentaMp.SIN_VINCULO_SETTLEMENT for m in self.movimientos)

    @property
    def operaciones_settlement_vinculadas(self) -> int:
        return len({m.movimiento.reference_id for m in self.movimientos if m.estado_vinculacion in self._estados_vinculados})

    def estadisticas(self, movimientos: tuple[MovimientoEstadoCuentaClasificado, ...]) -> EstadisticasMovimientosMp:
        importes = tuple(m.movimiento.importe_neto for m in movimientos)
        return EstadisticasMovimientosMp(
            cantidad_movimientos=len(movimientos),
            reference_ids_unicos=len({m.movimiento.reference_id for m in movimientos if m.movimiento.reference_id}),
            importes_positivos=sum((importe for importe in importes if importe > 0), Decimal("0")),
            importes_negativos=sum((importe for importe in importes if importe < 0), Decimal("0")),
            impacto_neto=sum(importes, Decimal("0")),
        )

    def estadisticas_categoria(self, categoria: CategoriaEstadoCuentaMp) -> EstadisticasMovimientosMp:
        return self.estadisticas(tuple(m for m in self.movimientos if m.categoria == categoria))

    def estadisticas_estado(self, estado: EstadoVinculacionEstadoCuentaMp) -> EstadisticasMovimientosMp:
        return self.estadisticas(tuple(m for m in self.movimientos if m.estado_vinculacion == estado))

    def estadisticas_vinculadas_categoria(self, categoria: CategoriaEstadoCuentaMp) -> EstadisticasMovimientosMp:
        return self.estadisticas(tuple(
            m for m in self.movimientos
            if m.estado_vinculacion in self._estados_vinculados and m.categoria == categoria
        ))

    @property
    def importe_neto_lineas_vinculadas(self) -> Decimal:
        return self.estadisticas(tuple(m for m in self.movimientos if m.estado_vinculacion in self._estados_vinculados)).impacto_neto

    @property
    def suma_categorias(self) -> Decimal:
        return sum((m.movimiento.importe_neto for m in self.movimientos), Decimal("0"))

    @property
    def diferencia_cobertura(self) -> Decimal:
        return self.suma_categorias - self.resumen.variacion_neta

    @property
    def diferencia_cobertura_monetaria(self) -> Decimal:
        return self.diferencia_cobertura
