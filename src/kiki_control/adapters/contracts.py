"""Contratos estructurales iniciales de fuentes externas."""

from dataclasses import dataclass

from kiki_control.domain.enums import TipoFuente


@dataclass(frozen=True)
class ContratoColumnas:
    """Columnas esperadas para reconocer y validar una fuente."""

    tipo_fuente: TipoFuente
    obligatorias: frozenset[str]
    opcionales_conocidas: frozenset[str]

    @property
    def conocidas(self) -> frozenset[str]:
        return self.obligatorias | self.opcionales_conocidas


COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE = frozenset(
    {
        "Fecha de venta",
        "Hora",
        "Producto",
        "Sku",
        "ID Order",
        "Cantidad",
        "Monto de venta ($)",
        "Costo Total (Con IVA) ($)",
        "Comisión MeLi  ($)",
        "Costo de envío (Seller) ($)",
        "Monto neto (en MP) ($)",
        "Utilidades netas ($)",
        "Parámetros cálculo",
    }
)

COLUMNAS_OBLIGATORIAS_MERCADO_PAGO = frozenset(
    {
        "ID DE OPERACIÓN EN MERCADO PAGO",
        "TIPO DE OPERACIÓN",
        "ID DE LA ORDEN",
        "FECHA DE ORIGEN",
        "FECHA DE APROBACIÓN",
        "VALOR DE LA COMPRA",
        "MONEDA",
        "COMISIONES + IVA",
        "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
        "COMISIÓN DE MERCADO LIBRE + IVA",
        "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS",
        "COSTO DE ENVÍO",
        "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB",
        "CUPÓN DE DESCUENTO",
        "CANAL DE VENTA",
        "FECHA DE LIQUIDACIÓN DEL DINERO",
        "CÓDIGO DE PRODUCTO SKU",
    }
)

CONTRATOS = (
    ContratoColumnas(TipoFuente.MERCADO_LIBRE, COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE, frozenset()),
    ContratoColumnas(TipoFuente.MERCADO_PAGO, COLUMNAS_OBLIGATORIAS_MERCADO_PAGO, frozenset()),
)
