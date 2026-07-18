from csv import writer
from dataclasses import asdict, fields
from decimal import Decimal
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.financial_movement import MovimientoFinanciero
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.presentation.reconciliation_view import detalle_presentacion, filas_presentacion
from kiki_control.reconciliation import reconciliar
from tests.test_reconciliation_engine import op as op_conciliacion

ML_CONFIRMADAS = [
    "Fecha de venta", "Hora", "Producto", "Sku", "ID Order", "ID Carrito", "Cantidad",
    "Precio unitario ($)", "Monto de venta ($)", "Costo unitario (Con IVA) ($)", "Costo Total (Con IVA) ($)",
    "Comisión MeLi  ($)", "Costo de envío (Bruto) ($)", "Costo de envío (Seller) ($)", "Costo de envío prorrateado ($)",
    "Bonificación por envío", "Monto neto (en MP) ($)", "Impuestos y comisiones ($)", "Utilidades netas ($)",
    "precio_equilibrio ($)", "Iva", "Rentabilidad (precio de venta)", "Rentabilidad (costo de producto)",
    "Rentabilidad (suma de costos)", "Comisión MeLi (%)", "Costo de envío (%)", "Parámetros cálculo", "Tipo de envío", "Provincia",
]

MP_CONFIRMADAS = [
    "NÚMERO DE IDENTIFICACIÓN",
    "ID DE OPERACIÓN EN MERCADO PAGO",
    "CÓDIGO DE LA CUENTA DEL VENDEDOR",
    "TIPO DE MEDIO DE PAGO",
    "MEDIO DE PAGO",
    "PAÍS DE ORIGEN DE LA CUENTA DE MERCADO PAGO",
    "TIPO DE OPERACIÓN",
    "VALOR DE LA COMPRA",
    "MONEDA",
    "MONTO RECIBIDO POR COMPRAS POR SPLIT",
    "FECHA DE ORIGEN",
    "COMISIONES + IVA",
    "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
    "MONEDA DE LA LIQUIDACIÓN",
    "FECHA DE APROBACIÓN",
    "MONTO NETO DE LA OPERACIÓN",
    "CUPÓN DE DESCUENTO",
    "DATOS EXTRA",
    "COMISIÓN DE MERCADO LIBRE + IVA",
    "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS",
    "COSTO DE ENVÍO",
    "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB",
    "CUOTAS",
    "DETALLE DE IMPUESTOS",
    "ID DE CAJA",
    "ID DE LOCAL",
    "NOMBRE DE LOCAL",
    "ID DE CAJA DEFINIDO POR EL USUARIO",
    "NOMBRE DE CAJA",
    "ID DE LOCAL DEFINIDO POR EL USUARIO",
    "ID DE LA ORDEN",
    "ID DEL ENVÍO",
    "MODO DE ENVÍO",
    "ID DEL PAQUETE",
    "IMPUESTOS DESAGREGADOS",
    "NÚMERO DE SERIE DEL LECTOR (S/N)",
    "BILLETERA VIRTUAL",
    "BANCO DE ORIGEN",
    "NÚMERO INICIAL DE TARJETA",
    "OPERATION_TAGS",
    "TIPO DE IDENTIFICACIÓN DEL PAGADOR",
    "NÚMERO DE IDENTIFICACIÓN DEL PAGADOR",
    "PAGADOR",
    "CANAL DE VENTA",
    "PLATAFORMA DE COBRO",
    "FECHA DE LIQUIDACIÓN DEL DINERO",
    "CÓDIGO DE PRODUCTO SKU",
    "DETALLE DE LA VENTA",
    "ID DE INTENTO DE OPERACIÓN",
]

SENTINELAS_PII = {
    "PAGADOR": "SENTINELA_PAGADOR_SINTETICO",
    "TIPO DE IDENTIFICACIÓN DEL PAGADOR": "SENTINELA_TIPO_DOC_SINTETICO",
    "NÚMERO DE IDENTIFICACIÓN DEL PAGADOR": "SENTINELA_NUM_DOC_SINTETICO",
    "NÚMERO INICIAL DE TARJETA": "SENTINELA_TARJETA_SINTETICA",
}


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


def _valores_mp(**overrides: str) -> dict[str, str]:
    valores = {c: "" for c in MP_CONFIRMADAS}
    valores.update({
        "NÚMERO DE IDENTIFICACIÓN": "NI-SINT", "ID DE OPERACIÓN EN MERCADO PAGO": "MP-SINT-001",
        "CÓDIGO DE LA CUENTA DEL VENDEDOR": "SELLER-SINT", "TIPO DE MEDIO DE PAGO": "account_money",
        "MEDIO DE PAGO": "Dinero sintético", "PAÍS DE ORIGEN DE LA CUENTA DE MERCADO PAGO": "AR",
        "TIPO DE OPERACIÓN": "Pago aprobado", "VALOR DE LA COMPRA": "1000.00", "MONEDA": "ARS",
        "MONTO RECIBIDO POR COMPRAS POR SPLIT": "123.45", "FECHA DE ORIGEN": "2026-07-18T10:15:00.000-04:00",
        "COMISIONES + IVA": "-110.00", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "820.00",
        "MONEDA DE LA LIQUIDACIÓN": "ARS", "FECHA DE APROBACIÓN": "2026-07-18T10:16:00.000-04:00",
        "MONTO NETO DE LA OPERACIÓN": "820.00", "CUPÓN DE DESCUENTO": "0", "DATOS EXTRA": "{}",
        "COMISIÓN DE MERCADO LIBRE + IVA": "-80.00", "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS": "-30.00",
        "COSTO DE ENVÍO": "-70.00", "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB": "0", "CUOTAS": "1",
        "DETALLE DE IMPUESTOS": "Detalle sintético", "ID DE CAJA": "CAJA-SINT", "ID DE LOCAL": "LOCAL-SINT",
        "NOMBRE DE LOCAL": "Local sintético", "ID DE CAJA DEFINIDO POR EL USUARIO": "CAJA-USR-SINT",
        "NOMBRE DE CAJA": "Caja sintética", "ID DE LOCAL DEFINIDO POR EL USUARIO": "LOCAL-USR-SINT",
        "ID DE LA ORDEN": "ORDER-SINT-001", "ID DEL ENVÍO": "SHIP-SINT-001", "MODO DE ENVÍO": "me2",
        "ID DEL PAQUETE": "PACK-SINT-001", "IMPUESTOS DESAGREGADOS": "[]", "NÚMERO DE SERIE DEL LECTOR (S/N)": "LECTOR-SINT",
        "BILLETERA VIRTUAL": "Billetera sintética", "BANCO DE ORIGEN": "Banco sintético", "OPERATION_TAGS": "[]",
        "CANAL DE VENTA": "Mercado Libre", "PLATAFORMA DE COBRO": "checkout", "FECHA DE LIQUIDACIÓN DEL DINERO": "2026-07-19T10:00:00.000-04:00",
        "CÓDIGO DE PRODUCTO SKU": "SKU-SINT", "DETALLE DE LA VENTA": "Venta sintética", "ID DE INTENTO DE OPERACIÓN": "TRY-SINT-001",
        **SENTINELAS_PII,
    })
    valores.update(overrides)
    return valores


def _xlsx(columnas: list[str], valores: dict[str, str]) -> bytes:
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "")
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Movimientos" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        rows = []
        for r, fila in enumerate([columnas, [valores.get(c, "") for c in columnas]], 1):
            rows.append(f'<row r="{r}">' + "".join(f'<c t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' for v in fila) + "</row>")
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    return salida.getvalue()


def _xlsx_mp(**overrides: str) -> bytes:
    return _xlsx(MP_CONFIRMADAS, _valores_mp(**overrides))


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
    texto_publico = f"{asdict(mov)} {mov!r}"
    reporte = reconciliar([op_conciliacion(id_orden="ORDER-SINT-001", neto="820")], [mov])
    presentacion = f"{filas_presentacion(reporte.resultados)} {detalle_presentacion(reporte.resultados[0])}"

    assert inspeccion.fuente_detectada == TipoFuente.MERCADO_PAGO
    assert inspeccion.metadatos.columnas_encontradas == tuple(MP_CONFIRMADAS)
    assert not [a for a in inspeccion.advertencias if a.codigo == "COLUMNAS_ADICIONALES"]
    assert resultado.cantidad_normalizada == 1
    assert resultado.cantidad_rechazada == 0
    assert mov.monto_recibido_split == Decimal("123.45")
    assert mov.moneda_liquidacion == "ARS"
    assert mov.id_envio == "SHIP-SINT-001"
    assert mov.id_paquete == "PACK-SINT-001"
    assert not {"pagador", "tipo_identificacion_pagador", "numero_identificacion_pagador", "numero_inicial_tarjeta"} & nombres_publicos
    assert all(sentinel not in texto_publico for sentinel in SENTINELAS_PII.values())
    assert all(sentinel not in presentacion for sentinel in SENTINELAS_PII.values())


def test_mercado_pago_encabezados_canonicos_anteriores_siguen_funcionando():
    columnas = [
        "MONTO RECIBIDO POR SPLIT" if c == "MONTO RECIBIDO POR COMPRAS POR SPLIT" else
        "MONEDA DE LIQUIDACIÓN" if c == "MONEDA DE LA LIQUIDACIÓN" else
        "ID DE ENVÍO" if c == "ID DEL ENVÍO" else
        "ID DE PAQUETE" if c == "ID DEL PAQUETE" else c
        for c in MP_CONFIRMADAS
    ]
    valores = _valores_mp(
        **{
            "MONTO RECIBIDO POR SPLIT": "234.56",
            "MONEDA DE LIQUIDACIÓN": "USD",
            "ID DE ENVÍO": "SHIP-CANONICO",
            "ID DE PAQUETE": "PACK-CANONICO",
        }
    )
    data = _xlsx(columnas, valores)
    inspeccion = inspeccionar_archivo("movimientos.xlsx", data)
    resultado = normalizar_mercado_pago("movimientos.xlsx", data)
    mov = resultado.movimientos[0]
    assert not [a for a in inspeccion.advertencias if a.codigo == "COLUMNAS_ADICIONALES"]
    assert resultado.cantidad_rechazada == 0
    assert mov.monto_recibido_split == Decimal("234.56")
    assert mov.moneda_liquidacion == "USD"
    assert mov.id_envio == "SHIP-CANONICO"
    assert mov.id_paquete == "PACK-CANONICO"


def test_alias_y_nombre_canonico_simultaneos_priorizan_valor_canonico():
    columnas = [*MP_CONFIRMADAS, "MONTO RECIBIDO POR SPLIT", "MONEDA DE LIQUIDACIÓN", "ID DE ENVÍO", "ID DE PAQUETE"]
    valores = _valores_mp(
        **{
            "MONTO RECIBIDO POR COMPRAS POR SPLIT": "111.11",
            "MONTO RECIBIDO POR SPLIT": "222.22",
            "MONEDA DE LA LIQUIDACIÓN": "ARS",
            "MONEDA DE LIQUIDACIÓN": "USD",
            "ID DEL ENVÍO": "SHIP-ALIAS",
            "ID DE ENVÍO": "SHIP-CANONICO",
            "ID DEL PAQUETE": "PACK-ALIAS",
            "ID DE PAQUETE": "PACK-CANONICO",
        }
    )
    data = _xlsx(columnas, valores)
    resultado = normalizar_mercado_pago("movimientos.xlsx", data)
    mov = resultado.movimientos[0]
    assert resultado.cantidad_rechazada == 0
    assert mov.monto_recibido_split == Decimal("222.22")
    assert mov.moneda_liquidacion == "USD"
    assert mov.id_envio == "SHIP-CANONICO"
    assert mov.id_paquete == "PACK-CANONICO"
