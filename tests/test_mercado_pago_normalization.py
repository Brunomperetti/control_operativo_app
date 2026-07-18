from dataclasses import fields, is_dataclass
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape
import json

from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.financial_movement import TipoOperacionFinanciera
from tests.test_file_inspector import ML, csv_bytes

MP = [
    "ID DE OPERACIÓN EN MERCADO PAGO", "TIPO DE OPERACIÓN", "ID DE LA ORDEN", "FECHA DE ORIGEN", "FECHA DE APROBACIÓN",
    "VALOR DE LA COMPRA", "MONEDA", "COMISIONES + IVA", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
    "COMISIÓN DE MERCADO LIBRE + IVA", "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS", "COSTO DE ENVÍO",
    "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB", "CUPÓN DE DESCUENTO", "CANAL DE VENTA", "FECHA DE LIQUIDACIÓN DEL DINERO",
    "CÓDIGO DE PRODUCTO SKU", "NÚMERO DE IDENTIFICACIÓN", "ID DE ENVÍO", "ID DE PAQUETE", "ID DE INTENTO DE OPERACIÓN",
    "PLATAFORMA DE COBRO", "TIPO DE MEDIO DE PAGO", "MEDIO DE PAGO", "MODO DE ENVÍO", "MONTO RECIBIDO POR SPLIT",
    "MONTO NETO DE LA OPERACIÓN", "MONEDA DE LIQUIDACIÓN", "IMPUESTOS DESAGREGADOS", "DATOS EXTRA", "OPERATION_TAGS",
]


def fila(**overrides):
    base = {
        "ID DE OPERACIÓN EN MERCADO PAGO": "9000000000000001", "TIPO DE OPERACIÓN": "Pago aprobado", "ID DE LA ORDEN": "1234567890123456",
        "FECHA DE ORIGEN": "2026-07-14T23:55:13.000-04:00", "FECHA DE APROBACIÓN": "2026-07-14T23:56:13.000-04:00",
        "VALOR DE LA COMPRA": 7478.66, "MONEDA": "ARS", "COMISIONES + IVA": -10.5,
        "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": 7468.16, "COMISIÓN DE MERCADO LIBRE + IVA": 0,
        "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS": 0, "COSTO DE ENVÍO": 0, "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB": 0,
        "CUPÓN DE DESCUENTO": 0, "CANAL DE VENTA": "Mercado Libre", "FECHA DE LIQUIDACIÓN DEL DINERO": "2026-07-15T03:00:00.000-04:00",
        "CÓDIGO DE PRODUCTO SKU": "SKU-SINT", "NÚMERO DE IDENTIFICACIÓN": "NI-1", "ID DE ENVÍO": "7001", "ID DE PAQUETE": "8001",
        "ID DE INTENTO DE OPERACIÓN": "6001", "PLATAFORMA DE COBRO": "checkout", "TIPO DE MEDIO DE PAGO": "account_money",
        "MEDIO DE PAGO": "Dinero en cuenta", "MODO DE ENVÍO": "me2", "MONTO RECIBIDO POR SPLIT": "0", "MONTO NETO DE LA OPERACIÓN": "7468.16",
        "MONEDA DE LIQUIDACIÓN": "ARS", "IMPUESTOS DESAGREGADOS": json.dumps([{"financial_entity":"synthetic","detail":"tax","amount":"12.34"}]),
        "DATOS EXTRA": json.dumps({"refund_id":"555000"}), "OPERATION_TAGS": json.dumps(["tag_sintetico"]),
    }
    base.update(overrides)
    return [base.get(c, "") for c in MP]


def xlsx(filas, hoja="Movimientos"):
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "")
        z.writestr("xl/workbook.xml", f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(hoja)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        rows = []
        for r, fila_vals in enumerate([MP, *filas], 1):
            cells = "".join(f'<c t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' if v is not None else '<c/>' for v in fila_vals)
            rows.append(f'<row r="{r}">{cells}</row>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    return salida.getvalue()


def test_xlsx_valido_normaliza_modelo_trazable_sin_dataframe():
    data = xlsx([fila()])
    r = normalizar_mercado_pago("mp.xlsx", data)
    m = r.movimientos[0]
    assert r.cantidad_total_recibida == r.cantidad_normalizada == 1
    assert r.cantidad_rechazada == 0
    assert r.hash_importacion == m.hash_importacion
    assert r.hoja_procesada == m.hoja_origen == "Movimientos"
    assert is_dataclass(m)
    assert not hasattr(r, "dataframe")


def test_ids_importes_fechas_json_y_privacidad():
    r = normalizar_mercado_pago("mp.xlsx", xlsx([fila(**{"ID DE OPERACIÓN EN MERCADO PAGO": 9000000000000001, "ID DE LA ORDEN": "1234567890123456", "CÓDIGO DE PRODUCTO SKU": ""})]))
    m = r.movimientos[0]
    assert m.id_operacion_mercado_pago == "9000000000000001"
    assert m.id_orden == "1234567890123456"
    assert m.sku is None
    assert m.valor_compra == Decimal("7478.66")
    assert m.comisiones_mas_iva == Decimal("-10.5")
    assert m.costo_envio == Decimal("0")
    assert m.fecha_origen_original == "2026-07-14T23:55:13.000-04:00"
    assert m.fecha_origen_utc.isoformat() == "2026-07-15T03:55:13+00:00"
    assert m.fecha_origen_local.isoformat() == "2026-07-15T00:55:13-03:00"
    assert m.impuestos_desagregados[0].importe == Decimal("12.34")
    assert m.refund_id == "555000"
    assert not {"nombre_pagador", "numero_identificacion_pagador", "numero_inicial_tarjeta"} & {f.name for f in fields(m)}


def test_todos_los_tipos_y_desconocido():
    tipos = [
        ("Pago aprobado", TipoOperacionFinanciera.PAGO_APROBADO), ("Pago de envío", TipoOperacionFinanciera.PAGO_ENVIO),
        ("Devolución de dinero", TipoOperacionFinanciera.DEVOLUCION_DINERO), ("DISPUTE_SHIPPING", TipoOperacionFinanciera.DISPUTA_ENVIO),
        ("Reclamo", TipoOperacionFinanciera.RECLAMO), ("Devolución de envío", TipoOperacionFinanciera.DEVOLUCION_ENVIO),
        ("PAYOUTS", TipoOperacionFinanciera.PAYOUT), ("Cashback", TipoOperacionFinanciera.CASHBACK), ("NUEVO", TipoOperacionFinanciera.DESCONOCIDA),
    ]
    r = normalizar_mercado_pago("mp.xlsx", xlsx([fila(**{"TIPO DE OPERACIÓN": t}) for t, _ in tipos]))
    assert [m.tipo_operacion for m in r.movimientos] == [e for _, e in tipos]
    assert any(a.codigo == "TIPO_OPERACION_DESCONOCIDO" for a in r.advertencias)


def test_orden_vacia_payout_y_pago_ml_sin_orden_aceptados_con_advertencia():
    r = normalizar_mercado_pago("mp.xlsx", xlsx([
        fila(**{"ID DE LA ORDEN": "", "TIPO DE OPERACIÓN": "PAYOUTS", "FECHA DE LIQUIDACIÓN DEL DINERO": "", "VALOR DE LA COMPRA": -3199.90}),
        fila(**{"ID DE LA ORDEN": "", "TIPO DE OPERACIÓN": "Pago aprobado", "CANAL DE VENTA": "Mercado Libre"}),
    ]))
    assert r.cantidad_normalizada == 2
    assert r.movimientos[0].id_orden is None and r.movimientos[0].valor_compra == Decimal("-3199.9")
    assert any(a.codigo == "ID_ORDEN_AUSENTE_ALTA_RELEVANCIA" for a in r.advertencias)
    assert any(a.codigo == "FECHA_LIQUIDACION_AUSENTE" for a in r.advertencias)


def test_fecha_invalida_e_importe_requerido_rechazan_y_totales():
    r = normalizar_mercado_pago("mp.xlsx", xlsx([fila(), fila(**{"FECHA DE ORIGEN": "fecha mala"}), fila(**{"VALOR DE LA COMPRA": "x"})]))
    assert (r.cantidad_total_recibida, r.cantidad_normalizada, r.cantidad_rechazada) == (3, 1, 2)
    assert {e.codigo for e in r.errores} >= {"FECHA_INVALIDA", "IMPORTE_INVALIDO"}


def test_json_invalidos_se_conservan_con_advertencia_y_no_rechazan():
    r = normalizar_mercado_pago("mp.xlsx", xlsx([fila(**{"IMPUESTOS DESAGREGADOS": "{no", "DATOS EXTRA": "{mal", "OPERATION_TAGS": "[]"})]))
    m = r.movimientos[0]
    assert m.detalle_impuestos_original == "{no"
    assert m.datos_extra_original == "{mal"
    assert m.operation_tags_original == "[]"
    assert r.cantidad_normalizada == 1
    assert any(a.codigo == "JSON_COMPLEMENTARIO_INVALIDO" for a in r.advertencias)


def test_movimientos_no_se_agrupan_y_archivo_ml_rechazado():
    r = normalizar_mercado_pago("mp.xlsx", xlsx([fila(), fila()]))
    assert len(r.movimientos) == 2
    rechazado = normalizar_mercado_pago("ventas.csv", csv_bytes(ML))
    assert rechazado.cantidad_normalizada == 0
    assert rechazado.errores[0].codigo == "FUENTE_NO_COMPATIBLE"
