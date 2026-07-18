from kiki_control.domain.enums import TipoFuente
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from tests.test_file_inspector import ML, MP, csv_bytes, xlsx_bytes


def test_xlsx_valido_mercado_pago():
    contenido = xlsx_bytes({"Movimientos": [MP, ["dato"] * len(MP)]})
    resultado = inspeccionar_archivo("movimientos.xlsx", contenido)
    assert resultado.es_valido
    assert resultado.fuente_detectada == TipoFuente.MERCADO_PAGO
    assert resultado.metadatos.nombre_hoja == "Movimientos"


def test_mercado_pago_con_columna_obligatoria_faltante():
    columnas = [c for c in MP if c != "ID DE LA ORDEN"]
    contenido = xlsx_bytes({"Movimientos": [columnas, ["dato"] * len(columnas)]})
    resultado = inspeccionar_archivo("movimientos.xlsx", contenido)
    assert resultado.fuente_detectada == TipoFuente.MERCADO_PAGO
    assert not resultado.es_valido
    assert resultado.errores[0].columna == "ID DE LA ORDEN"


def test_xlsx_con_mas_de_una_hoja_no_vacia():
    contenido = xlsx_bytes({"Primera": [MP, ["dato"] * len(MP)], "Segunda": [["Otra"], ["dato"]]})
    resultado = inspeccionar_archivo("movimientos.xlsx", contenido)
    assert resultado.es_valido
    assert any(a.codigo == "VARIAS_HOJAS_CON_DATOS" for a in resultado.advertencias)


def test_deteccion_no_depende_del_nombre_del_archivo():
    resultado = inspeccionar_archivo("mercado_pago.csv", csv_bytes(ML))
    assert resultado.fuente_detectada == TipoFuente.MERCADO_LIBRE


def test_id_de_la_orden_nulo_no_invalida_mercado_pago():
    fila = ["dato"] * len(MP)
    fila[MP.index("ID DE LA ORDEN")] = ""
    contenido = xlsx_bytes({"Movimientos": [MP, fila]})
    resultado = inspeccionar_archivo("movimientos.xlsx", contenido)
    assert resultado.es_valido


def test_sku_nulo_no_invalida_mercado_libre():
    fila = ["dato"] * len(ML)
    fila[ML.index("Sku")] = ""
    resultado = inspeccionar_archivo("ventas.csv", csv_bytes(ML, fila))
    assert resultado.es_valido
