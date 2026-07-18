from csv import writer
from dataclasses import fields
from decimal import Decimal
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.financial_movement import MovimientoFinanciero
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

ML_CONFIRMADAS = [
    "Fecha de venta", "Hora", "Producto", "Sku", "ID Order", "ID Carrito", "Cantidad",
    "Precio unitario ($)", "Monto de venta ($)", "Costo unitario (Con IVA) ($)", "Costo Total (Con IVA) ($)",
    "Comisión MeLi  ($)", "Costo de envío (Bruto) ($)", "Costo de envío (Seller) ($)", "Costo de envío prorrateado ($)",
    "Bonificación por envío", "Monto neto (en MP) ($)", "Impuestos y comisiones ($)", "Utilidades netas ($)",
    "precio_equilibrio ($)", "Iva", "Rentabilidad (precio de venta)", "Rentabilidad (costo de producto)",
    "Rentabilidad (suma de costos)", "Comisión MeLi (%)", "Costo de envío (%)", "Parámetros cálculo", "Tipo de envío", "Provincia",
]

MP_CONFIRMADAS = [
    "ID DE OPERACIÓN EN MERCADO PAGO", "TIPO DE OPERACIÓN", "ID DE LA ORDEN", "FECHA DE ORIGEN", "FECHA DE APROBACIÓN",
    "VALOR DE LA COMPRA", "MONEDA", "COMISIONES + IVA", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
    "COMISIÓN DE MERCADO LIBRE + IVA", "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS", "COSTO DE ENVÍO",
    "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB", "CUPÓN DE DESCUENTO", "CANAL DE VENTA", "FECHA DE LIQUIDACIÓN DEL DINERO",
    "CÓDIGO DE PRODUCTO SKU", "NÚMERO DE IDENTIFICACIÓN", "ID DEL ENVÍO", "ID DEL PAQUETE", "ID DE INTENTO DE OPERACIÓN",
    "PLATAFORMA DE COBRO", "TIPO DE MEDIO DE PAGO", "MEDIO DE PAGO", "MODO DE ENVÍO", "MONTO RECIBIDO POR COMPRAS POR SPLIT",
    "MONTO NETO DE LA OPERACIÓN", "MONEDA DE LA LIQUIDACIÓN", "IMPUESTOS DESAGREGADOS", "DATOS EXTRA", "OPERATION_TAGS",
    "NOMBRE DEL PAGADOR", "APELLIDO DEL PAGADOR", "EMAIL DEL PAGADOR", "TELÉFONO DEL PAGADOR", "TIPO DE DOCUMENTO DEL PAGADOR",
    "NÚMERO DE DOCUMENTO DEL PAGADOR", "NÚMERO DE TARJETA", "PRIMEROS 6 DÍGITOS DE LA TARJETA", "ÚLTIMOS 4 DÍGITOS DE LA TARJETA",
    "NOMBRE DEL TITULAR DE LA TARJETA", "TIPO DE DOCUMENTO DEL TITULAR DE LA TARJETA", "NÚMERO DE DOCUMENTO DEL TITULAR DE LA TARJETA",
    "BANCO EMISOR", "CUOTAS", "ESTADO DE LA OPERACIÓN", "MOTIVO DE RECHAZO", "ID DEL PAGADOR", "ID DEL COBRADOR",
]


def _csv_ml() -> bytes:
    valores = {
        "Fecha de venta": "2026-07-18", "Hora": "10:15:00", "Producto": "Producto sintético", "Sku": "SKU-SINT",
        "ID Order": "ORDER-SINT-001", "ID Carrito": "CART-SINT-001", "Cantidad": "1", "Precio unitario ($)": "1.000,00",
        "Monto de venta ($)": "1.000,00", "Costo unitario (Con IVA) ($)": "400,00", "Costo Total (Con IVA) ($)": "400,00",
        "Comisión MeLi  ($)": "110,00", "Costo de envío (Bruto) ($)": "90,00", "Costo de envío (Seller) ($)": "70,00",
        "Costo de envío prorrateado ($)": "70,00", "Bonificación por envío": "20,00", "Monto neto (en MP) ($)": "820,00",
        "Impuestos y comisiones ($)": "180,00", "Utilidades netas ($)": "240,00", "precio_equilibrio ($)": "760,00",
        "Iva": "21%", "Rentabilidad (precio de venta)": "24%", "Rentabilidad (costo de producto)": "60%",
        "Rentabilidad (suma de costos)": "41.38%", "Comisión MeLi (%)": "11%", "Costo de envío (%)": "7%",
        "Parámetros cálculo": "Costo inc. alíc.: Sí | Precio inc. alíc.: Sí | IIBB: 0 (0%)", "Tipo de envío": "Logística sintética", "Provincia": "Provincia sintética",
    }
    out = StringIO(); w = writer(out); w.writerow(ML_CONFIRMADAS); w.writerow([valores[c] for c in ML_CONFIRMADAS])
    return out.getvalue().encode("utf-8")


def _xlsx_mp() -> bytes:
    valores = {c: "" for c in MP_CONFIRMADAS}
    valores.update({
        "ID DE OPERACIÓN EN MERCADO PAGO": "MP-SINT-001", "TIPO DE OPERACIÓN": "Pago aprobado", "ID DE LA ORDEN": "ORDER-SINT-001",
        "FECHA DE ORIGEN": "2026-07-18T10:15:00.000-04:00", "FECHA DE APROBACIÓN": "2026-07-18T10:16:00.000-04:00",
        "VALOR DE LA COMPRA": "1000.00", "MONEDA": "ARS", "COMISIONES + IVA": "-110.00",
        "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "820.00", "COMISIÓN DE MERCADO LIBRE + IVA": "-80.00",
        "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS": "-30.00", "COSTO DE ENVÍO": "-70.00", "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB": "0",
        "CUPÓN DE DESCUENTO": "0", "CANAL DE VENTA": "Mercado Libre", "FECHA DE LIQUIDACIÓN DEL DINERO": "2026-07-19T10:00:00.000-04:00",
        "CÓDIGO DE PRODUCTO SKU": "SKU-SINT", "NÚMERO DE IDENTIFICACIÓN": "NI-SINT", "ID DEL ENVÍO": "SHIP-SINT-001", "ID DEL PAQUETE": "PACK-SINT-001",
        "ID DE INTENTO DE OPERACIÓN": "TRY-SINT-001", "MONTO RECIBIDO POR COMPRAS POR SPLIT": "123.45", "MONTO NETO DE LA OPERACIÓN": "820.00",
        "MONEDA DE LA LIQUIDACIÓN": "ARS", "IMPUESTOS DESAGREGADOS": "[]", "DATOS EXTRA": "{}", "OPERATION_TAGS": "[]",
        "NOMBRE DEL PAGADOR": "Persona Sintética", "NÚMERO DE DOCUMENTO DEL PAGADOR": "DOC-SINT", "NÚMERO DE TARJETA": "CARD-SINT",
    })
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "")
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Movimientos" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        rows = []
        for r, fila in enumerate([MP_CONFIRMADAS, [valores[c] for c in MP_CONFIRMADAS]], 1):
            rows.append(f'<row r="{r}">' + "".join(f'<c t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' for v in fila) + "</row>")
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    return salida.getvalue()


def test_mercado_libre_29_columnas_confirmadas_sin_adicionales_y_alias_normalizados():
    data = _csv_ml()
    inspeccion = inspeccionar_archivo("ventas.csv", data)
    resultado = normalizar_mercado_libre("ventas.csv", data, zona_horaria="UTC")
    op = resultado.operaciones[0]
    assert inspeccion.fuente_detectada == TipoFuente.MERCADO_LIBRE
    assert not [a for a in inspeccion.advertencias if a.codigo == "COLUMNAS_ADICIONALES"]
    assert resultado.cantidad_rechazada == 0
    assert not [a for a in resultado.advertencias if a.codigo == "PRECIO_EQUILIBRIO_VACIO"]
    assert op.precio_equilibrio == Decimal("760.00")
    assert op.costo_unitario_con_iva == Decimal("400.00")
    assert op.bonificacion_envio == Decimal("20.00")
    assert op.tasa_iva == Decimal("0.21")
    assert op.rentabilidad_precio_venta == Decimal("0.24")
    assert op.rentabilidad_costo_producto == Decimal("0.6")
    assert op.rentabilidad_suma_costos == Decimal("0.4138")
    assert op.tasa_comision_mercado_libre == Decimal("0.11")
    assert op.tasa_costo_envio == Decimal("0.07")


def test_mercado_pago_49_columnas_confirmadas_sin_adicionales_alias_y_sin_pii_publica():
    data = _xlsx_mp()
    inspeccion = inspeccionar_archivo("movimientos.xlsx", data)
    resultado = normalizar_mercado_pago("movimientos.xlsx", data)
    mov = resultado.movimientos[0]
    nombres_publicos = {f.name for f in fields(MovimientoFinanciero)}
    assert inspeccion.fuente_detectada == TipoFuente.MERCADO_PAGO
    assert not [a for a in inspeccion.advertencias if a.codigo == "COLUMNAS_ADICIONALES"]
    assert resultado.cantidad_rechazada == 0
    assert mov.monto_recibido_split == Decimal("123.45")
    assert mov.moneda_liquidacion == "ARS"
    assert mov.id_envio == "SHIP-SINT-001"
    assert mov.id_paquete == "PACK-SINT-001"
    assert not {"nombre_pagador", "apellido_pagador", "email_pagador", "numero_documento_pagador", "numero_tarjeta", "ultimos_4_digitos_tarjeta"} & nombres_publicos
