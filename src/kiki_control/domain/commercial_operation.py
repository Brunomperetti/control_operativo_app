"""Modelo interno de operaciones comerciales normalizadas."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class OperacionComercial:
    """Operación comercial estable e independiente de columnas externas."""

    fuente: str
    hash_importacion: str
    numero_fila_origen: int
    id_orden: str
    id_carrito: str | None
    sku: str | None
    fecha_venta_original: str
    hora_venta_original: str
    fecha_hora_venta: datetime
    producto: str
    tipo_envio: str | None
    provincia: str | None
    cantidad: int
    precio_unitario: Decimal | None
    monto_venta: Decimal
    costo_unitario_con_iva: Decimal | None
    costo_total_con_iva: Decimal
    comision_mercado_libre_informada: Decimal | None
    costo_envio_bruto: Decimal | None
    costo_envio_vendedor: Decimal | None
    costo_envio_prorrateado: Decimal | None
    bonificacion_envio: Decimal | None
    monto_neto_mercado_pago_informado: Decimal
    impuestos_y_comisiones_informados: Decimal | None
    utilidad_neta_informada: Decimal
    precio_equilibrio: Decimal | None
    tasa_iva: Decimal | None
    rentabilidad_precio_venta: Decimal | None
    rentabilidad_costo_producto: Decimal | None
    rentabilidad_suma_costos: Decimal | None
    tasa_comision_mercado_libre: Decimal | None
    tasa_costo_envio: Decimal | None
    parametros_calculo_original: str
    costo_incluye_alicuota: bool | None
    precio_incluye_alicuota: bool | None
    tasa_iibb_configurada: Decimal | None
