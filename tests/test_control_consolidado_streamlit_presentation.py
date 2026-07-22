from decimal import Decimal

from kiki_control.presentation.control_consolidado_view import (
    FilaControlConsolidado,
    filtrar_filas_consolidadas,
    formato_importe,
    kpis_consolidados,
)
from kiki_control.ui.session_cycle import (
    construir_firma_procesamiento_tres_fuentes,
    invalidar_resultados_conocidos,
    limpiar_filtros_de_vista,
)


def test_firma_tres_fuentes_estable_y_sensible_a_cambios_o_retiros():
    base = construir_firma_procesamiento_tres_fuentes("ml", "eco", "mp", "UTC", Decimal("0.01"))
    assert base == construir_firma_procesamiento_tres_fuentes("ml", "eco", "mp", "UTC", Decimal("0.010"))
    assert base != construir_firma_procesamiento_tres_fuentes("ml2", "eco", "mp", "UTC", Decimal("0.01"))
    assert base != construir_firma_procesamiento_tres_fuentes("ml", None, "mp", "UTC", Decimal("0.01"))
    assert base != construir_firma_procesamiento_tres_fuentes("ml", "eco", "mp", "America/Argentina/Cordoba", Decimal("0.01"))
    assert base != construir_firma_procesamiento_tres_fuentes("ml", "eco", "mp", "UTC", Decimal("1"))


def test_invalidacion_completa_y_limpieza_de_filtros_sin_borrar_reportes():
    estado = {k: object() for k in ("normalizacion", "cobertura_consolidada", "reporte_comercial", "reporte_financiero", "reporte_consolidado", "firma_procesamiento", "filtro_estados", "detalle_operacion")}
    invalidar_resultados_conocidos(estado)
    assert not estado
    estado = {"reporte_consolidado": object(), "reporte_financiero": object(), "filtro_estados": ["x"], "detalle_operacion": "a"}
    limpiar_filtros_de_vista(estado)
    assert "reporte_consolidado" in estado and "reporte_financiero" in estado
    assert "filtro_estados" not in estado and "detalle_operacion" not in estado


def test_streamlit_no_duplica_formulas_financieras_y_usa_apis_existentes():
    source = open("src/kiki_control/ui/streamlit_app.py", encoding="utf-8").read()
    for api in ("normalizar_ventas_mercado_libre", "normalizar_mercado_libre", "normalizar_mercado_pago", "vincular_ventas_oficiales_con_eccomapp", "reconciliar", "consolidar_control_financiero"):
        assert api in source
    assert "Utilidad preliminar =" not in source
    assert "Diferencia =" not in source
    assert "Auditoría de conciliación Eccomapp–Mercado Pago" in source
    assert "Descargar reporte completo" in source


def test_presentacion_sin_float_y_negativos_con_signo():
    assert formato_importe(Decimal("-10.50")).startswith("$ -10,50")
    source = open("src/kiki_control/presentation/control_consolidado_view.py", encoding="utf-8").read()
    assert "float(" not in source


def test_filtros_estados_diferencias_faltantes_y_revision():
    filas = [
        FilaControlConsolidado("a", "ORD-1", "Completa", "COMPLETA", "ML oficial, Eccomapp, MP", "$ 1,00", "$ 0,00", "$ 0,00", "$ 1,00", "$ 1,00", "$ 1,00", "$ 1,00", "$ 0,00", "$ 0,00", "No", False, False),
        FilaControlConsolidado("b", "ORD-2", "Sin Mp", "SIN_MOVIMIENTO_FINANCIERO", "ML oficial, Eccomapp", "$ 1,00", "$ 0,00", "$ 0,00", "$ 1,00", "$ 1,00", "No calculado", "No calculado", "No calculado", "$ 0,00", "Sí", False, True),
        FilaControlConsolidado("c", "ORD-3", "Con Diferencia", "CON_DIFERENCIA", "ML oficial, Eccomapp, MP", "$ 1,00", "$ 0,00", "$ 0,00", "$ 1,00", "$ 1,00", "$ 2,00", "$ 2,00", "$ 1,00", "$ 0,00", "Sí", True, False),
    ]
    assert [f.clave for f in filtrar_filas_consolidadas(filas, {"SIN_MOVIMIENTO_FINANCIERO"}, "", False, False, False)] == ["b"]
    assert [f.clave for f in filtrar_filas_consolidadas(filas, set(), "ORD-3", False, True, False)] == ["c"]
    assert [f.clave for f in filtrar_filas_consolidadas(filas, set(), "", True, False, True)] == ["b"]


def test_kpis_comparables_utilidad_parcial_y_mp_sin_ml():
    from kiki_control.domain.control_consolidado import EstadoControlConsolidado, IndicadoresFinancieros, ReporteControlConsolidado, ResultadoControlConsolidado
    ind = IndicadoresFinancieros(False, False, False, False, False, False, False, False)
    def res(clave, ml, mp, costo, dif, utilidad, tiene_ml=True):
        return ResultadoControlConsolidado(clave, clave, (clave,), tiene_ml, costo is not None, mp is not None, None, ml, Decimal("-1") if ml is not None else None, None, None, None, None, ml, None, costo, None, None, None, mp, mp, None, None, None, None, None, None, dif, utilidad, Decimal("0.01"), EstadoControlConsolidado.COMPLETA, False, (), (), ind, "v", (), (), (), (), (), (), (), ())
    resultados = (res("a", Decimal("100"), Decimal("90"), Decimal("40"), Decimal("-10"), Decimal("60")), res("b", Decimal("50"), None, None, None, None), res("c", None, Decimal("30"), None, None, None, False))
    reporte = ReporteControlConsolidado(resultados, "v", Decimal("0.01"), 0, 0, 3, 0, 1, 0, 0, 1, 1, 1, 0, 0, Decimal("150"), Decimal("120"), Decimal("40"))
    bloques = kpis_consolidados(reporte)
    b = {k.nombre: k.valor for ks in bloques.values() for k in ks}
    assert b["Neto ML comparable"] == "$ 100,00"
    assert b["Neto MP comparable"] == "$ 90,00"
    assert b["Diferencia comparable ML–MP"] == "$ -10,00"
    assert b["Neto MP sin venta oficial asociada"] == "$ 30,00"
    assert b["Utilidad preliminar calculable"] == "$ 60,00"
    assert b["Cobertura de utilidad"] == "1 de 3 grupos con los datos necesarios"
