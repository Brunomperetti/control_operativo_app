"""Modelo interno de movimientos financieros normalizados."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TipoOperacionFinanciera(StrEnum):
    """Tipos estables de movimientos financieros, independientes del proveedor."""

    PAGO_APROBADO = "PAGO_APROBADO"
    PAGO_ENVIO = "PAGO_ENVIO"
    DEVOLUCION_DINERO = "DEVOLUCION_DINERO"
    DISPUTA_ENVIO = "DISPUTA_ENVIO"
    RECLAMO = "RECLAMO"
    DEVOLUCION_ENVIO = "DEVOLUCION_ENVIO"
    PAYOUT = "PAYOUT"
    CASHBACK = "CASHBACK"
    DESCONOCIDA = "DESCONOCIDA"


class TratamientoNetoComparable(StrEnum):
    """Semántica contable explícita de un movimiento para el neto ML–MP."""

    MODIFICA_NETO_COMPARABLE = "MODIFICA_NETO_COMPARABLE"
    COMPONENTE_YA_INCLUIDO = "COMPONENTE_YA_INCLUIDO"
    MOVIMIENTO_DE_FONDOS = "MOVIMIENTO_DE_FONDOS"


@dataclass(frozen=True)
class DetalleImpuesto:
    """Detalle inmutable de un impuesto informado por la fuente financiera."""

    entidad_financiera: str | None
    detalle: str | None
    importe: Decimal


@dataclass(frozen=True)
class MovimientoFinanciero:
    """Movimiento financiero estable, auditable y sin datos personales innecesarios."""

    fuente: str
    hash_importacion: str
    numero_fila_origen: int
    hoja_origen: str
    numero_identificacion: str | None
    id_operacion_mercado_pago: str
    id_orden: str | None
    id_envio: str | None
    id_paquete: str | None
    id_intento_operacion: str | None
    sku: str | None
    refund_id: str | None
    tipo_operacion: TipoOperacionFinanciera
    tipo_operacion_original: str
    canal_venta: str | None
    plataforma_cobro: str | None
    tipo_medio_pago: str | None
    medio_pago: str | None
    modo_envio: str | None
    valor_compra: Decimal
    monto_recibido_split: Decimal | None
    comisiones_mas_iva: Decimal
    monto_neto_impactado: Decimal
    monto_neto_operacion: Decimal | None
    cupon_descuento: Decimal
    comision_mercado_libre_mas_iva: Decimal
    comision_cuotas_sin_interes: Decimal
    costo_envio: Decimal
    retencion_iibb: Decimal
    moneda_operacion: str
    moneda_liquidacion: str | None
    fecha_origen_original: str
    fecha_origen_utc: datetime
    fecha_origen_local: datetime
    fecha_aprobacion_original: str
    fecha_aprobacion_utc: datetime
    fecha_aprobacion_local: datetime
    fecha_liquidacion_original: str | None
    fecha_liquidacion_utc: datetime | None
    fecha_liquidacion_local: datetime | None
    detalle_impuestos_original: str | None
    impuestos_desagregados: tuple[DetalleImpuesto, ...]
    datos_extra_original: str | None
    operation_tags_original: str | None

    @property
    def tratamiento_neto_comparable(self) -> TratamientoNetoComparable:
        """Clasifica el movimiento sin inferir impacto por estar asociado a una orden.

        El reporte MP presenta ``Pago de envío`` como desglose del pago aprobado:
        su importe queda visible, pero ya está contenido en el neto aprobado bruto.
        Un PAYOUT mueve fondos y pertenece a un universo separado.
        """
        if self.tipo_operacion == TipoOperacionFinanciera.PAGO_ENVIO:
            return TratamientoNetoComparable.COMPONENTE_YA_INCLUIDO
        if self.tipo_operacion == TipoOperacionFinanciera.PAYOUT:
            return TratamientoNetoComparable.MOVIMIENTO_DE_FONDOS
        return TratamientoNetoComparable.MODIFICA_NETO_COMPARABLE

    @property
    def modifica_neto_comparable(self) -> bool:
        """Indica si el importe integra algebraicamente el neto comparable."""
        return self.tratamiento_neto_comparable == TratamientoNetoComparable.MODIFICA_NETO_COMPARABLE
