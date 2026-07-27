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


COLUMNAS_OBLIGATORIAS_ECCOMAPP_RENTABILIDAD = frozenset(
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

COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS = (
    "# de venta",
    "Fecha de venta",
    "Estado",
    "Descripción del estado",
    "Paquete de varios productos",
    "Pertenece a un kit",
    "Unidades",
    "Ingresos por productos (ARS)",
    "Cargo por venta e impuestos (ARS)",
    "Ingresos por envío (ARS)",
    "Costos de envío (ARS)",
    "Costo de envío basado en medidas y peso declarados",
    "Cargo por diferencias en medidas y peso del paquete",
    "Descuentos y bonificaciones",
    "Anulaciones y reembolsos (ARS)",
    "Total (ARS)",
    "Mes de facturación de tus cargos",
    "Orden de compra",
    "Venta por publicidad",
    "SKU",
    "# de publicación",
    "Canal de venta",
    "Tienda oficial",
    "Título de la publicación",
    "Variante",
    "Precio unitario de venta de la publicación (ARS)",
    "Tiene cuotas agregadas",
    "Factura adjunta",
    "Datos personales o de empresa",
    "Tipo y número de documento",
    "Dirección",
    "Condición fiscal (IVA)",
    "Número IIBB",
    "Comprador",
    "Negocio",
    "DNI",
    "Domicilio",
    "Ciudad",
    "Estado",
    "Código postal",
    "País",
    "Forma de entrega",
    "Fecha en camino",
    "Fecha entregado",
    "Transportista",
    "Número de seguimiento",
    "URL de seguimiento",
    "Unidades",
    "Forma de entrega",
    "Fecha en camino",
    "Fecha entregado",
    "Transportista",
    "Número de seguimiento",
    "URL de seguimiento",
    "Revisado por Mercado Libre",
    "Fecha de revisión",
    "Dinero a favor",
    "Resultado",
    "Destino",
    "Motivo del resultado",
    "Unidades",
    "Reclamo abierto",
    "Reclamo cerrado",
    "Con mediación",
)

COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE_VENTAS = frozenset(
    {
        "# de venta",
        "Fecha de venta",
        "Estado",
        "Unidades",
        "Ingresos por productos (ARS)",
        "Total (ARS)",
        "SKU",
        "# de publicación",
        "Canal de venta",
        "Título de la publicación",
    }
)

COLUMNAS_OPCIONALES_MERCADO_LIBRE_VENTAS = frozenset(COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS) - COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE_VENTAS

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
        TipoFuente.MERCADO_LIBRE_VENTAS,
        COLUMNAS_OBLIGATORIAS_MERCADO_LIBRE_VENTAS,
        COLUMNAS_OPCIONALES_MERCADO_LIBRE_VENTAS,
    ),
    ContratoColumnas(
        TipoFuente.ECCOMAPP_RENTABILIDAD,
        COLUMNAS_OBLIGATORIAS_ECCOMAPP_RENTABILIDAD,
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
