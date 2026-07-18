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
    ContratoColumnas(
        TipoFuente.MERCADO_LIBRE,
        COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE,
        frozenset(
            {
                "ID Carrito",
                "Precio unitario ($)",
                "Costo Unitario (Con IVA) ($)",
                "Costo de envío (Bruto) ($)",
                "Costo de envío prorrateado ($)",
                "Bonificación envío ($)",
                "Impuestos y comisiones ($)",
                "Precio de equilibrio ($)",
                "IVA",
                "Rentabilidad s/ precio venta",
                "Rentabilidad s/ costo producto",
                "Rentabilidad s/ suma costos",
                "% Comisión MeLi",
                "% Costo de envío",
                "Tipo de envío",
                "Provincia",
            }
        ),
    ),
    ContratoColumnas(
        TipoFuente.MERCADO_PAGO,
        COLUMNAS_OBLIGATORIAS_MERCADO_PAGO,
        frozenset(
            {
                "NÚMERO DE IDENTIFICACIÓN",
                "ID DE ENVÍO",
                "ID DE PAQUETE",
                "ID DE INTENTO DE OPERACIÓN",
                "PLATAFORMA DE COBRO",
                "TIPO DE MEDIO DE PAGO",
                "MEDIO DE PAGO",
                "MODO DE ENVÍO",
                "MONTO RECIBIDO POR SPLIT",
                "MONTO NETO DE LA OPERACIÓN",
                "MONEDA DE LIQUIDACIÓN",
                "IMPUESTOS DESAGREGADOS",
                "DATOS EXTRA",
                "OPERATION_TAGS",
                # Columnas estructurales confirmadas con datos de pagador, documento y tarjeta.
                # Se reconocen para evitar COLUMNAS_ADICIONALES, pero no se normalizan al modelo público.
                "NOMBRE DEL PAGADOR",
                "APELLIDO DEL PAGADOR",
                "EMAIL DEL PAGADOR",
                "TELÉFONO DEL PAGADOR",
                "TIPO DE DOCUMENTO DEL PAGADOR",
                "NÚMERO DE DOCUMENTO DEL PAGADOR",
                "NÚMERO DE TARJETA",
                "PRIMEROS 6 DÍGITOS DE LA TARJETA",
                "ÚLTIMOS 4 DÍGITOS DE LA TARJETA",
                "NOMBRE DEL TITULAR DE LA TARJETA",
                "TIPO DE DOCUMENTO DEL TITULAR DE LA TARJETA",
                "NÚMERO DE DOCUMENTO DEL TITULAR DE LA TARJETA",
                "BANCO EMISOR",
                "CUOTAS",
                "ESTADO DE LA OPERACIÓN",
                "MOTIVO DE RECHAZO",
                "ID DEL PAGADOR",
                "ID DEL COBRADOR",
            }
        ),
    ),
)
