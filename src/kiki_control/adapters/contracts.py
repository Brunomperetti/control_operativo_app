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
                "CÓDIGO DE LA CUENTA DEL VENDEDOR",
                "TIPO DE MEDIO DE PAGO",
                "MEDIO DE PAGO",
                "PAÍS DE ORIGEN DE LA CUENTA DE MERCADO PAGO",
                "MONTO RECIBIDO POR SPLIT",
                "MONEDA DE LIQUIDACIÓN",
                "MONTO NETO DE LA OPERACIÓN",
                "DATOS EXTRA",
                "CUOTAS",
                "DETALLE DE IMPUESTOS",
                "ID DE CAJA",
                "ID DE LOCAL",
                "NOMBRE DE LOCAL",
                "ID DE CAJA DEFINIDO POR EL USUARIO",
                "NOMBRE DE CAJA",
                "ID DE LOCAL DEFINIDO POR EL USUARIO",
                "ID DE ENVÍO",
                "MODO DE ENVÍO",
                "ID DE PAQUETE",
                "IMPUESTOS DESAGREGADOS",
                "NÚMERO DE SERIE DEL LECTOR (S/N)",
                "BILLETERA VIRTUAL",
                "BANCO DE ORIGEN",
                "NÚMERO INICIAL DE TARJETA",
                "OPERATION_TAGS",
                # Columnas sensibles confirmadas estructuralmente.
                # Se reconocen para evitar COLUMNAS_ADICIONALES, pero no se normalizan al modelo público.
                "TIPO DE IDENTIFICACIÓN DEL PAGADOR",
                "NÚMERO DE IDENTIFICACIÓN DEL PAGADOR",
                "PAGADOR",
                "PLATAFORMA DE COBRO",
                "DETALLE DE LA VENTA",
                "ID DE INTENTO DE OPERACIÓN",
            }
        ),
    ),
)
