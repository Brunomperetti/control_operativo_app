"""Modelo público seguro para ventas oficiales de Mercado Libre."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class VentaOficialMercadoLibre:
    """Venta normalizada desde el reporte oficial de Mercado Libre sin datos personales."""

    fila_origen: int
    hash_importacion: str
    id_venta: str
    fecha_venta: datetime | None
    estado: str | None
    descripcion_estado: str | None
    paquete_varios_productos: bool | None
    pertenece_kit: bool | None
    unidades: int | None
    ingresos_productos: Decimal | None
    cargo_venta_impuestos: Decimal | None
    ingresos_envio: Decimal | None
    costos_envio: Decimal | None
    costo_envio_declarado: Decimal | None
    cargo_diferencias_envio: Decimal | None
    descuentos_bonificaciones: Decimal | None
    anulaciones_reembolsos: Decimal | None
    total_informado_ml: Decimal | None
    sku: str | None
    id_publicacion: str | None
    canal_venta: str | None
    titulo_publicacion: str | None
    variante: str | None
    precio_unitario: Decimal | None
    forma_entrega: str | None
    reclamo_abierto: bool | None
    reclamo_cerrado: bool | None
    con_mediacion: bool | None
