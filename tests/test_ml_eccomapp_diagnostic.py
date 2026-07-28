from dataclasses import replace
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from kiki_control.domain.ml_eccomapp_diagnostic import EstadoAptitudUtilidad as Apt, EstadoCruceMlEccomapp as Estado
from kiki_control.exporting.excel import generar_diagnostico_ml_eccomapp_excel
from kiki_control.linking.ml_eccomapp_diagnostic import diagnosticar_ml_eccomapp
from tests.test_commercial_linking import op, venta


def caso(ventas, ops):
    diag = diagnosticar_ml_eccomapp(ventas, ops)
    assert len(diag.casos) == 1
    return diag.casos[0]


def test_coincidencia_exacta_uno_a_uno_y_utilidad_calculable():
    c = caso([venta("123")], [op("123")])
    assert (c.estado, c.aptitud_utilidad) == (Estado.COINCIDENCIA_EXACTA, Apt.UTILIDAD_CALCULABLE)


def test_varias_filas_ml_y_eccomapp_forman_un_grupo_sin_perder_filas():
    c = caso([venta("C", "A", 1), venta("C", "B", 2)], [op("O1", "C", "A", 3), op("O2", "C", "B", 4)])
    assert c.estado == Estado.COINCIDENCIA_POR_GRUPO
    assert [v.fila_origen for v in c.ventas_ml] == [1, 2]
    assert [o.numero_fila_origen for o in c.operaciones_eccomapp] == [3, 4]


def test_solo_ml_y_solo_eccomapp_son_universos_independientes():
    d = diagnosticar_ml_eccomapp([venta("ML")], [op("EC")])
    assert (d.cantidad_solo_ml, d.cantidad_solo_eccomapp) == (1, 1)


def test_identificadores_faltantes_no_desaparecen():
    d = diagnosticar_ml_eccomapp([venta("")], [replace(op(""), id_carrito=None)])
    assert d.cantidad_identificador_incompleto == 2
    assert sum(len(c.ventas_ml) for c in d.casos) == 1
    assert sum(len(c.operaciones_eccomapp) for c in d.casos) == 1


def test_duplicado_ml_inesperado_y_composicion_valida_se_distinguen():
    assert caso([venta("X", "A", 1), venta("X", "A", 2)], []).estado == Estado.DUPLICADO_ML
    assert caso([venta("X", "A", 1), venta("X", "B", 2)], []).estado == Estado.SOLO_ML


def test_duplicado_eccomapp_inesperado():
    c = caso([venta("X")], [op("X", sku="A", fila=1), op("X", sku="A", fila=2)])
    assert c.estado == Estado.DUPLICADO_ECCOMAPP


def test_correspondencia_ambigua_no_elige_grupo():
    d = diagnosticar_ml_eccomapp([venta("X")], [op("O1", "X", fila=1), op("X", "C2", fila=2)])
    assert any(c.estado == Estado.IDENTIFICADOR_AMBIGUO for c in d.casos)


def test_sin_costo_sin_total_y_none_se_conservan_sin_convertir_a_cero():
    sin_costo = caso([venta("A")], [replace(op("A"), costo_total_con_iva=None)])
    sin_total = caso([venta("B", total=None)], [op("B")])
    assert (sin_costo.costo_eccomapp, sin_costo.aptitud_utilidad) == (None, Apt.SIN_COSTO)
    assert (sin_total.total_ml, sin_total.aptitud_utilidad) == (None, Apt.SIN_TOTAL_ML)


def test_coherencia_total_de_filas_grupos_y_categorias():
    d = diagnosticar_ml_eccomapp([venta("A"), venta("B", fila=2)], [op("A"), op("C", fila=2)])
    assert d.cantidad_filas_ml == 2 and d.cantidad_filas_eccomapp == 2
    assert sum((d.cantidad_coincidencias_exactas, d.cantidad_coincidencias_por_grupo, d.cantidad_solo_ml, d.cantidad_solo_eccomapp, d.cantidad_identificador_incompleto, d.cantidad_ambiguas, d.cantidad_duplicadas)) == len(d.casos)


def test_excel_cinco_hojas_ids_extensos_formulas_seguras_y_faltantes_vacios():
    long_id = "00000000000000012345"
    d = diagnosticar_ml_eccomapp([venta(long_id), venta("=CMD()", fila=2, total=None)], [op(long_id)])
    wb = load_workbook(BytesIO(generar_diagnostico_ml_eccomapp_excel(d)), data_only=False)
    assert wb.sheetnames == ["ML-Eccomapp — Resumen", "ML sin Eccomapp", "Eccomapp sin ML", "ML-Eccomapp — Coincidencias", "ML-Eccomapp — Ambiguos"]
    ws = wb["ML-Eccomapp — Coincidencias"]
    assert ws["A2"].value == long_id and ws["A2"].data_type == "s"
    missing = wb["ML sin Eccomapp"]
    assert missing["A2"].value == "'=CMD()" and missing["N2"].value is None
