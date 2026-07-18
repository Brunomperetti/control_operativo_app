from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from kiki_control.domain.enums import TipoFuente
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

ML = ["Fecha de venta","Hora","Producto","Sku","ID Order","Cantidad","Monto de venta ($)","Costo Total (Con IVA) ($)","Comisión MeLi  ($)","Costo de envío (Seller) ($)","Monto neto (en MP) ($)","Utilidades netas ($)","Parámetros cálculo"]
MP = ["ID DE OPERACIÓN EN MERCADO PAGO","TIPO DE OPERACIÓN","ID DE LA ORDEN","FECHA DE ORIGEN","FECHA DE APROBACIÓN","VALOR DE LA COMPRA","MONEDA","COMISIONES + IVA","MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO","COMISIÓN DE MERCADO LIBRE + IVA","COMISIÓN POR OFRECER CUOTAS SIN INTERÉS","COSTO DE ENVÍO","IMPUESTOS COBRADOS POR RETENCIONES DE IIBB","CUPÓN DE DESCUENTO","CANAL DE VENTA","FECHA DE LIQUIDACIÓN DEL DINERO","CÓDIGO DE PRODUCTO SKU"]


def csv_bytes(columnas, fila=None):
    valores = fila or ["dato"] * len(columnas)
    return (",".join(columnas) + "\n" + ",".join(valores) + "\n").encode()


def xlsx_bytes(hojas):
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "")
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(hojas, 1)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(hojas)+1)) + "</Relationships>")
        for i, filas in enumerate(hojas.values(), 1):
            rows = []
            for r, fila in enumerate(filas, 1):
                cells = "".join(f'<c r="A{r}" t="inlineStr"><is><t>{v}</t></is></c>' if c == 0 else f'<c t="inlineStr"><is><t>{v}</t></is></c>' for c, v in enumerate(fila))
                rows.append(f'<row r="{r}">{cells}</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    return salida.getvalue()


def test_archivo_vacio():
    resultado = inspeccionar_archivo("archivo.csv", b"")
    assert not resultado.es_valido
    assert resultado.errores[0].codigo == "ARCHIVO_VACIO"


def test_extension_no_soportada():
    resultado = inspeccionar_archivo("archivo.txt", b"contenido")
    assert not resultado.es_valido
    assert resultado.errores[0].codigo == "EXTENSION_NO_SOPORTADA"


def test_csv_valido_mercado_libre():
    resultado = inspeccionar_archivo("ventas.csv", csv_bytes(ML))
    assert resultado.es_valido
    assert resultado.fuente_detectada == TipoFuente.MERCADO_LIBRE
    assert resultado.metadatos.cantidad_filas == 1


def test_csv_mercado_libre_con_bom():
    resultado = inspeccionar_archivo("ventas.csv", b"\xef\xbb\xbf" + csv_bytes(ML))
    assert resultado.es_valido
    assert resultado.metadatos.columnas_encontradas[0] == "Fecha de venta"


def test_mercado_libre_con_columna_obligatoria_faltante():
    columnas = [c for c in ML if c != "Sku"]
    resultado = inspeccionar_archivo("ventas.csv", csv_bytes(columnas))
    assert resultado.fuente_detectada == TipoFuente.MERCADO_LIBRE
    assert not resultado.es_valido
    assert resultado.errores[0].columna == "Sku"


def test_mercado_libre_con_columnas_adicionales():
    resultado = inspeccionar_archivo("ventas.csv", csv_bytes([*ML, "Columna sintética extra"]))
    assert resultado.es_valido
    assert resultado.advertencias[0].codigo == "COLUMNAS_ADICIONALES"


def test_archivo_legible_de_fuente_desconocida():
    resultado = inspeccionar_archivo("desconocido.csv", csv_bytes(["A", "B"]))
    assert resultado.fuente_detectada == TipoFuente.DESCONOCIDA
    assert not resultado.es_valido
    assert resultado.errores[0].codigo == "FUENTE_DESCONOCIDA"
