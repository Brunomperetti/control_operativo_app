"""Pruebas para Bloque B — Conciliación ML–MP.

Cubre los 20 casos obligatorios del requisito.
No utiliza archivos reales ni hardcodea valores de los archivos de producción.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from kiki_control.domain.control_consolidado import (
    EstadoControlConsolidado as E,
    IndicadoresFinancieros,
    ReporteControlConsolidado,
    ResultadoControlConsolidado,
    TipoMovimientoFinanciero,
)
from kiki_control.exporting.excel import (
    generar_bloque_b_mp_sin_venta_excel,
    generar_reporte_consolidado_excel,
)
from kiki_control.presentation.bloque_b_diagnostics import (
    DiagnosticoBloqueB,
    EstadoExplicacionDiferencia,
    categoria_temporal_mp,
    clasificar_diferencia,
    diagnosticar_bloque_b,
)
from kiki_control.presentation.control_consolidado_view import (
    TITULO_BLOQUE_B,
    texto_universo_comparable,
)

D = Decimal
IND = IndicadoresFinancieros(False, False, False, False, False, False, False, False)
IND_DEV = IndicadoresFinancieros(False, True, False, False, False, False, False, False)
IND_REC = IndicadoresFinancieros(False, False, True, False, False, False, False, False)
IND_ENV = IndicadoresFinancieros(False, False, False, False, False, False, False, True)


# ---------------------------------------------------------------------------
# Helpers sintéticos
# ---------------------------------------------------------------------------

def _r(
    clave: str,
    estado: E = E.COMPLETA,
    ml: Decimal | None = D("100"),
    mp: Decimal | None = D("100"),
    dif: Decimal | None = D("0"),
    neto_fin: Decimal | None = None,
    tiene_ml: bool = True,
    tiene_mp: bool = True,
    filas_mp: tuple[int, ...] = (1,),
    filas_ml: tuple[int, ...] = (1,),
    ind: IndicadoresFinancieros = IND,
    tipo: TipoMovimientoFinanciero | None = None,
    imp_dev: Decimal = D("0"),
    imp_rec: Decimal = D("0"),
    imp_env: Decimal = D("0"),
    imp_otros: Decimal = D("0"),
    tolerancia: Decimal = D("0.01"),
) -> ResultadoControlConsolidado:
    return ResultadoControlConsolidado(
        clave_resultado=clave,
        id_grupo_canonico=clave if not clave.startswith("fin:") else None,
        ids_orden=(clave,) if not clave.startswith("fin:") else (),
        tiene_mercado_libre_oficial=tiene_ml,
        tiene_eccomapp=True,
        tiene_mercado_pago=tiene_mp,
        tipo_movimiento_financiero=tipo,
        monto_venta_ml=D("120") if tiene_ml else None,
        cargo_venta_impuestos_ml=None,
        ingresos_envio_ml=None,
        costo_envio_ml=None,
        descuentos_bonificaciones_ml=None,
        anulaciones_reembolsos_ml=None,
        total_informado_ml=ml if tiene_ml else None,
        monto_venta_eccomapp_informado=None,
        costo_productos_eccomapp=D("40"),
        costo_envio_seller_eccomapp_informado=None,
        neto_mp_eccomapp_informado=None,
        utilidad_eccomapp_informada=None,
        neto_aprobado_mp=mp if tiene_mp else None,
        neto_financiero_total_mp=neto_fin if neto_fin is not None else mp,
        impacto_pagos_envio_mp=imp_env,
        impacto_devoluciones_mp=imp_dev,
        impacto_reclamos_disputas_mp=imp_rec,
        impacto_otros_mp=imp_otros,
        diferencia_venta_ml_eccomapp=None,
        diferencia_neto_ml_eccomapp=None,
        diferencia_ml_mp=dif,
        utilidad_preliminar_control=None,
        tolerancia=tolerancia,
        estado=estado,
        requiere_revision=estado != E.COMPLETA,
        motivos=(),
        explicaciones=(),
        indicadores_financieros=ind,
        version_regla="v",
        hashes_importacion_ml=(),
        hashes_importacion_eccomapp=(),
        hashes_importacion_mp=(),
        filas_origen_ml=filas_ml,
        filas_origen_eccomapp=(),
        filas_origen_mp=filas_mp,
        claves_resultados_comerciales=(),
        claves_resultados_financieros=(),
    )


def _rep(resultados: list[ResultadoControlConsolidado], tolerancia: Decimal = D("0.01")) -> ReporteControlConsolidado:
    return ReporteControlConsolidado(
        resultados=tuple(resultados),
        version_regla="v",
        tolerancia=tolerancia,
        total_resultados_comerciales_recibidos=0,
        total_resultados_financieros_recibidos=0,
        total_resultados=len(resultados),
        total_requieren_revision=sum(r.requiere_revision for r in resultados),
        total_completa=sum(r.estado == E.COMPLETA for r in resultados),
        total_con_diferencia=sum(r.estado == E.CON_DIFERENCIA for r in resultados),
        total_sin_movimiento_financiero=sum(r.estado == E.SIN_MOVIMIENTO_FINANCIERO for r in resultados),
        total_solo_movimiento_financiero=sum(r.estado == E.SOLO_MOVIMIENTO_FINANCIERO for r in resultados),
        total_sin_venta_oficial=sum(r.estado == E.SIN_VENTA_OFICIAL for r in resultados),
        total_sin_costo_producto=sum(r.estado == E.SIN_COSTO_PRODUCTO for r in resultados),
        total_en_revision_financiera=sum(r.estado == E.EN_REVISION_FINANCIERA for r in resultados),
        total_duplicada_o_ambigua=sum(r.estado == E.DUPLICADA_O_AMBIGUA for r in resultados),
        suma_total_informado_ml=D("0"),
        suma_neto_aprobado_mp=D("0"),
        suma_costo_productos_eccomapp=D("0"),
        total_total_ml_ausente=0,
    )


# ---------------------------------------------------------------------------
# Test 1 — Grupo ML–MP que coincide dentro de tolerancia
# ---------------------------------------------------------------------------

def test_grupo_ml_mp_coincide_dentro_tolerancia():
    r = _r("ok", ml=D("100"), mp=D("100.005"), dif=D("0.005"))
    reporte = _rep([r])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.comparables_totales == 1
    assert diag.resumen.coincidencias == 1
    assert diag.resumen.con_diferencia == 0
    assert len(diag.grupos_con_diferencia) == 0


# ---------------------------------------------------------------------------
# Test 2 — Grupo con diferencia positiva (MP > ML)
# ---------------------------------------------------------------------------

def test_grupo_con_diferencia_positiva():
    r = _r("pos", ml=D("100"), mp=D("110"), dif=D("10"))
    reporte = _rep([r])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.con_diferencia == 1
    assert len(diag.grupos_con_diferencia) == 1
    assert diag.grupos_con_diferencia[0].diferencia_ml_mp == D("10")
    assert diag.resumen.diferencia_operaciones_fuera_tolerancia == D("10")


# ---------------------------------------------------------------------------
# Test 3 — Grupo con diferencia negativa (MP < ML)
# ---------------------------------------------------------------------------

def test_grupo_con_diferencia_negativa():
    r = _r("neg", ml=D("100"), mp=D("85"), dif=D("-15"))
    reporte = _rep([r])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.con_diferencia == 1
    assert diag.grupos_con_diferencia[0].diferencia_ml_mp == D("-15")
    assert diag.resumen.diferencia_operaciones_fuera_tolerancia == D("-15")


# ---------------------------------------------------------------------------
# Test 4 — Dos grupos cuya suma coincide con la diferencia total
# ---------------------------------------------------------------------------

def test_suma_diferencias_individuales_igual_total():
    r1 = _r("g1", ml=D("100"), mp=D("115"), dif=D("15"))
    r2 = _r("g2", ml=D("200"), mp=D("190"), dif=D("-10"))
    reporte = _rep([r1, r2])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.con_diferencia == 2
    suma_ind = diag.grupos_con_diferencia[0].diferencia_ml_mp + diag.grupos_con_diferencia[1].diferencia_ml_mp
    assert suma_ind == diag.resumen.diferencia_operaciones_fuera_tolerancia
    assert diag.coherencia_suma_diferencias


# ---------------------------------------------------------------------------
# Test 5 — Diferencia explicada por movimientos financieros identificados
# ---------------------------------------------------------------------------

def test_diferencia_explicada_por_movimientos_financieros():
    # diferencia = 5, impacto_dev = 5 → EXPLICADA dentro de tolerancia
    r = _r("exp", ml=D("100"), mp=D("105"), dif=D("5"), imp_dev=D("5"), ind=IND_DEV)
    estado, motivo, _ = clasificar_diferencia(r)
    assert estado == EstadoExplicacionDiferencia.EXPLICADA
    assert "explicada" in motivo.lower()


# ---------------------------------------------------------------------------
# Test 6 — Temporalidad genera indicio pero no explica monetariamente
# ---------------------------------------------------------------------------

def test_indicio_temporal_no_explica_importe():
    # liquidación posterior a venta pero sin impactos que igualen la diferencia
    r = _r("temp", ml=D("100"), mp=D("108"), dif=D("8"))
    fecha_venta = date(2026, 7, 10)
    fecha_liq = date(2026, 7, 25)
    estado, motivo, secundarios = clasificar_diferencia(r, fecha_venta_ml=fecha_venta, fecha_min_liquidacion=fecha_liq)
    assert estado == EstadoExplicacionDiferencia.INDICIO_TEMPORAL
    assert "Liquidación posterior" in " ".join(secundarios)


# ---------------------------------------------------------------------------
# Test 7 — Diferencia pendiente de clasificación
# ---------------------------------------------------------------------------

def test_diferencia_pendiente_de_clasificacion():
    r = _r("pend", ml=D("100"), mp=D("112"), dif=D("12"))
    estado, motivo, _ = clasificar_diferencia(r)
    assert estado == EstadoExplicacionDiferencia.PENDIENTE_DE_CLASIFICACION


# ---------------------------------------------------------------------------
# Test 8 — Movimiento MP anterior al período ML
# ---------------------------------------------------------------------------

def test_movimiento_mp_anterior_al_periodo_ml():
    r = _r("fin:ant:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("50"), tiene_ml=False, filas_mp=(1,))
    reporte = _rep([r])
    fechas = {1: date(2026, 6, 15)}
    diag = diagnosticar_bloque_b(reporte, inicio_ml=date(2026, 7, 1), fin_ml=date(2026, 7, 31), fechas_origen_mp_por_fila=fechas)
    assert diag.movimientos_mp_sin_venta[0].categoria_temporal == "Anterior al período ML"


# ---------------------------------------------------------------------------
# Test 9 — Movimiento MP dentro del período ML
# ---------------------------------------------------------------------------

def test_movimiento_mp_dentro_del_periodo_ml():
    r = _r("fin:den:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("50"), tiene_ml=False, filas_mp=(1,))
    reporte = _rep([r])
    fechas = {1: date(2026, 7, 15)}
    diag = diagnosticar_bloque_b(reporte, inicio_ml=date(2026, 7, 1), fin_ml=date(2026, 7, 31), fechas_origen_mp_por_fila=fechas)
    assert diag.movimientos_mp_sin_venta[0].categoria_temporal == "Dentro del período ML"


# ---------------------------------------------------------------------------
# Test 10 — Movimiento MP con liquidación posterior
# ---------------------------------------------------------------------------

def test_movimiento_mp_con_liquidacion_posterior():
    # Un grupo comparable (no SOLO_MOVIMIENTO_FINANCIERO) con liquidación futura
    r = _r("liq-post", ml=D("100"), mp=D("102"), dif=D("2"))
    fecha_venta = date(2026, 7, 10)
    fecha_liq = date(2026, 8, 5)
    estado, _, secundarios = clasificar_diferencia(r, fecha_venta_ml=fecha_venta, fecha_min_liquidacion=fecha_liq)
    assert "Liquidación posterior" in " ".join(secundarios)


# ---------------------------------------------------------------------------
# Test 11 — Movimiento sin fecha
# ---------------------------------------------------------------------------

def test_movimiento_mp_sin_fecha():
    r = _r("fin:sf:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("30"), tiene_ml=False, filas_mp=(5,))
    reporte = _rep([r])
    diag = diagnosticar_bloque_b(reporte, inicio_ml=date(2026, 7, 1), fin_ml=date(2026, 7, 31), fechas_origen_mp_por_fila={})
    assert diag.movimientos_mp_sin_venta[0].categoria_temporal == "Sin fecha"
    assert diag.movimientos_mp_sin_venta[0].fecha_min_origen == "Sin fecha"


# ---------------------------------------------------------------------------
# Test 12 — Grupo con fechas mixtas
# ---------------------------------------------------------------------------

def test_grupo_con_fechas_mixtas():
    filas_mp = (1, 2)
    r = _r("fin:mix:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("30"), tiene_ml=False, filas_mp=filas_mp)
    reporte = _rep([r])
    fechas = {1: date(2026, 6, 20), 2: date(2026, 7, 15)}
    diag = diagnosticar_bloque_b(
        reporte,
        inicio_ml=date(2026, 7, 1),
        fin_ml=date(2026, 7, 31),
        fechas_origen_mp_por_fila=fechas,
    )
    assert diag.movimientos_mp_sin_venta[0].categoria_temporal == "Fechas mixtas"


# ---------------------------------------------------------------------------
# Test 13 — Payout separado de ventas faltantes
# ---------------------------------------------------------------------------

def test_payout_separado_de_ventas_faltantes():
    r = _r(
        "fin:pay:h:1",
        E.SOLO_MOVIMIENTO_FINANCIERO,
        ml=None,
        mp=D("200"),
        tiene_ml=False,
        tipo=TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS,
    )
    reporte = _rep([r])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.cantidad_mp_sin_venta == 0
    assert diag.neto_aprobado_mp_sin_venta == D("0")
    assert diag.cantidad_movimientos_fondos == 1
    mov = diag.movimientos_fondos[0]
    assert "Payout" in mov.motivo_sin_venta or "movimiento de fondos" in mov.motivo_sin_venta.lower()


# ---------------------------------------------------------------------------
# Test 14 — Listado MP sin venta ML
# ---------------------------------------------------------------------------

def test_listado_mp_sin_venta_ml():
    r1 = _r("fin:a:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("50"), tiene_ml=False, filas_mp=(1,))
    r2 = _r("fin:b:h:2", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("70"), tiene_ml=False, filas_mp=(2,))
    r3 = _r("con-ml", ml=D("100"), mp=D("100"), dif=D("0"))
    reporte = _rep([r1, r2, r3])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.cantidad_mp_sin_venta == 2
    assert diag.neto_aprobado_mp_sin_venta == D("120")
    assert len(diag.movimientos_mp_sin_venta) == 2


# ---------------------------------------------------------------------------
# Test 15 — Exportación Excel de diferencias
# ---------------------------------------------------------------------------

def test_exportacion_excel_diferencias():
    r = _r("dif-excel", ml=D("100"), mp=D("125"), dif=D("25"))
    reporte = _rep([r])
    diag_b = diagnosticar_bloque_b(reporte)
    bytes_xlsx = generar_reporte_consolidado_excel(reporte, diag_bloque_b=diag_b)
    assert bytes_xlsx.startswith(b"PK")
    wb = load_workbook(BytesIO(bytes_xlsx))
    assert "Bloque B — Diferencias" in wb.sheetnames
    assert "Bloque B — Resumen" in wb.sheetnames
    ws_dif = wb["Bloque B — Diferencias"]
    # Header row + 1 data row
    assert ws_dif.max_row == 2


# ---------------------------------------------------------------------------
# Test 16 — Exportación Excel de MP sin venta ML
# ---------------------------------------------------------------------------

def test_exportacion_excel_mp_sin_venta():
    r1 = _r("fin:z:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("80"), tiene_ml=False, filas_mp=(1,))
    r2 = _r("fin:y:h:2", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("30"), tiene_ml=False, filas_mp=(2,))
    reporte = _rep([r1, r2])
    diag_b = diagnosticar_bloque_b(reporte)
    bytes_xlsx = generar_bloque_b_mp_sin_venta_excel(diag_b)
    assert bytes_xlsx.startswith(b"PK")
    wb = load_workbook(BytesIO(bytes_xlsx))
    assert "MP sin venta ML" in wb.sheetnames
    ws = wb["MP sin venta ML"]
    assert ws.max_row == 3  # header + 2 data rows


# ---------------------------------------------------------------------------
# Test 17 — Coherencia de conteos: comparables = coincidentes + con diferencia
# ---------------------------------------------------------------------------

def test_coherencia_conteos_comparables():
    r_ok = _r("ok", ml=D("100"), mp=D("100"), dif=D("0"))
    r_dif = _r("dif", ml=D("100"), mp=D("120"), dif=D("20"))
    reporte = _rep([r_ok, r_dif])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.comparables_totales == diag.resumen.coincidencias + diag.resumen.con_diferencia
    assert diag.resumen.comparables_totales == 2
    assert diag.resumen.coincidencias == 1
    assert diag.resumen.con_diferencia == 1


# ---------------------------------------------------------------------------
# Test 18 — Suma individual de diferencias = diferencia total
# ---------------------------------------------------------------------------

def test_suma_individual_igual_diferencia_total():
    r1 = _r("x1", ml=D("100"), mp=D("118"), dif=D("18"))
    r2 = _r("x2", ml=D("200"), mp=D("192"), dif=D("-8"))
    reporte = _rep([r1, r2])
    diag = diagnosticar_bloque_b(reporte)
    assert abs(diag.suma_diferencias_individuales - diag.resumen.diferencia_operaciones_fuera_tolerancia) <= D("0.01")
    assert diag.coherencia_suma_diferencias


# ---------------------------------------------------------------------------
# Test 19 — La UI no muestra "Identidad cierra: Sí" sin identificar el universo
# ---------------------------------------------------------------------------

def test_texto_universo_comparable_no_dice_identidad_cierra_sin_contexto():
    r_ok = _r("ok", ml=D("100"), mp=D("100"), dif=D("0"))
    r_dif = _r("dif", ml=D("100"), mp=D("124"), dif=D("24"))
    reporte = _rep([r_ok, r_dif])
    diag = diagnosticar_bloque_b(reporte)
    texto = texto_universo_comparable(diag)
    # El texto debe mencionar la cantidad de operaciones pendientes y el importe
    assert "1 operaciones por analizar" in texto or "1 operación" in texto or "quedan" in texto.lower()
    # No debe solo decir "Identidad cierra: Sí"
    assert "identidad cierra: sí" not in texto.lower()
    # Debe identificar el universo
    assert "1" in texto  # al menos menciona que hay operaciones


# ---------------------------------------------------------------------------
# Test 20 — Bloque A no se modifica
# ---------------------------------------------------------------------------

def test_bloque_a_no_modificado():
    """El diagnóstico de Bloque B no afecta los resultados del Bloque A."""
    from kiki_control.presentation.control_consolidado_diagnostics import diagnosticar_control_consolidado

    r1 = _r("a", ml=D("100"), mp=D("100"), dif=D("0"))
    r2 = _r("b", ml=D("200"), mp=D("220"), dif=D("20"))
    reporte = _rep([r1, r2])

    diag_consolidado = diagnosticar_control_consolidado(reporte)
    diag_b = diagnosticar_bloque_b(reporte)

    # Bloque A residual no cambia
    assert diag_consolidado.residual_ml.suma_total_ars == D("300")  # 100 + 200

    # Bloque B no interfiere con partición de Bloque A
    assert diag_consolidado.particion.total_resultados == 2
    assert diag_b.resumen.comparables_totales == 2  # independiente


# ---------------------------------------------------------------------------
# Test adicional — INDICIO_FINANCIERO cuando hay reclamos/devoluciones
# ---------------------------------------------------------------------------

def test_indicio_financiero_con_reclamo():
    r = _r("rec", ml=D("100"), mp=D("107"), dif=D("7"), ind=IND_REC)
    estado, motivo, secundarios = clasificar_diferencia(r)
    assert estado == EstadoExplicacionDiferencia.INDICIO_FINANCIERO
    assert "Reclamo detectado" in secundarios


def test_indicio_financiero_con_devolucion():
    # devolucion presente pero importe no iguala diferencia → INDICIO_FINANCIERO
    r = _r("dev-ind", ml=D("100"), mp=D("107"), dif=D("7"), imp_dev=D("3"), ind=IND_DEV)
    estado, _, _ = clasificar_diferencia(r)
    assert estado == EstadoExplicacionDiferencia.INDICIO_FINANCIERO


def test_categoria_temporal_funcion_directa():
    filas = (1, 2, 3)
    fechas = {
        1: date(2026, 7, 15),
        2: date(2026, 7, 20),
        3: date(2026, 7, 25),
    }
    cat = categoria_temporal_mp(filas, fechas, inicio_ml=date(2026, 7, 1), fin_ml=date(2026, 7, 31))
    assert cat == "Dentro del período ML"


def test_categoria_temporal_posterior():
    filas = (1,)
    fechas = {1: date(2026, 8, 5)}
    cat = categoria_temporal_mp(filas, fechas, inicio_ml=date(2026, 7, 1), fin_ml=date(2026, 7, 31))
    assert cat == "Posterior al período ML"


def test_bloque_b_sin_enriquecimiento_funciona_sin_error():
    """Con datos mínimos (sin enriquecimiento) el diagnóstico no falla."""
    r1 = _r("ok", ml=D("100"), mp=D("100"), dif=D("0"))
    r2 = _r("fin:x:h:1", E.SOLO_MOVIMIENTO_FINANCIERO, ml=None, mp=D("50"), tiene_ml=False)
    reporte = _rep([r1, r2])
    diag = diagnosticar_bloque_b(reporte)
    assert diag.resumen.comparables_totales == 1
    assert diag.cantidad_mp_sin_venta == 1
    assert diag.movimientos_mp_sin_venta[0].fecha_min_origen == "Sin fecha"


def test_titulo_bloque_b():
    assert "Bloque B" in TITULO_BLOQUE_B
    assert "Conciliación" in TITULO_BLOQUE_B


def test_exportacion_sin_diferencias_no_crea_hoja_con_datos():
    """Si no hay diferencias, la hoja de diferencias tiene solo el header."""
    r = _r("ok", ml=D("100"), mp=D("100"), dif=D("0"))
    reporte = _rep([r])
    diag_b = diagnosticar_bloque_b(reporte)
    bytes_xlsx = generar_reporte_consolidado_excel(reporte, diag_bloque_b=diag_b)
    wb = load_workbook(BytesIO(bytes_xlsx))
    ws = wb["Bloque B — Diferencias"]
    assert ws.max_row == 1  # solo el header


def test_no_float_en_bloque_b_diagnostics():
    """Verificar que bloque_b_diagnostics.py no usa float."""
    source = open("src/kiki_control/presentation/bloque_b_diagnostics.py", encoding="utf-8").read()
    assert "float(" not in source


def test_tres_diferencias_corresponden_a_sus_universos():
    dentro = _r("dentro", ml=D("100"), mp=D("100.005"), dif=D("0.005"))
    fuera = _r("fuera", ml=D("100"), mp=D("110"), dif=D("10"))
    diag = diagnosticar_bloque_b(_rep([dentro, fuera]))
    assert diag.resumen.diferencia_universo_comparable == D("10.005")
    assert diag.resumen.diferencia_operaciones_fuera_tolerancia == D("10")
    assert diag.resumen.diferencia_subuniverso_conciliado == D("0.005")


def test_detalle_movimientos_y_hojas_separadas():
    r = _r("dif-detalle", ml=D("100"), mp=D("110"), dif=D("10"), filas_mp=(7, 8))
    diag = diagnosticar_bloque_b(
        _rep([r]),
        ids_operacion_mp_por_fila={7: "mov-7", 8: "mov-8"},
        ids_orden_mp_por_fila={7: "orden", 8: "orden"},
        tipos_movimiento_mp_por_fila={7: "PAGO", 8: "DEVOLUCION"},
        estados_mp_por_fila={7: "APROBADO", 8: "APROBADO"},
        fechas_origen_mp_por_fila={7: date(2026, 7, 1)},
        fechas_aprobacion_mp_por_fila={7: date(2026, 7, 2), 8: date(2026, 7, 3)},
        fechas_liquidacion_mp_por_fila={7: date(2026, 7, 4), 8: None},
        montos_neto_mp_por_fila={7: D("120"), 8: D("-10")},
    )
    movimientos = diag.grupos_con_diferencia[0].movimientos_asociados
    assert len(movimientos) == 2
    assert movimientos[0].fecha_origen == "01/07/2026"
    assert movimientos[1].fecha_origen == "Sin fecha"
    wb = load_workbook(BytesIO(generar_reporte_consolidado_excel(_rep([r]), diag_bloque_b=diag)))
    assert {"Bloque B — Movimientos", "Bloque B — Fondos y payouts"}.issubset(wb.sheetnames)
    assert wb["Bloque B — Movimientos"].max_row == 3
