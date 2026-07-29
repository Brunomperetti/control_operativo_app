from datetime import datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook

from kiki_control.domain.account_statement import CategoriaEstadoCuentaMp, EstadoVinculacionEstadoCuentaMp
from kiki_control.exporting import generar_control_estado_cuenta_mp_excel
from kiki_control.linking.account_statement import controlar_estado_cuenta_mp
from kiki_control.normalization.account_statement import normalizar_estado_cuenta_mp, parsear_decimal_estado_cuenta


def archivo_estado():
    wb = Workbook(); ws = wb.active; ws.title = "ACCOUNT_STATEMENT"
    ws.append(["INITIAL_BALANCE", "CREDITS", "DEBITS", "FINAL_BALANCE"])
    ws.append(["1.000,00", "160,00", "-40,00", "1.120,00"]); ws.append([])
    ws.append(["RELEASE_DATE", "TRANSACTION_TYPE", "REFERENCE_ID", "TRANSACTION_NET_AMOUNT", "PARTIAL_BALANCE"])
    ws.append([datetime(2026, 7, 28), "Liquidación de dinero", "169679883346", "100,00", "1.100,00"])
    ws.append([datetime(2026, 7, 28), "Dinero retenido", "169679883346", "-40,00", None])
    ws.append([datetime(2026, 7, 28), "Rendimientos", None, "10,00", None])
    ws.append([datetime(2026, 7, 28), "Liquidación de dinero", "SIN-VINCULO", "50,00", "1.120,00"])
    out = BytesIO(); wb.save(out); return out.getvalue()


def settlement():
    return SimpleNamespace(id_operacion_mercado_pago="169679883346", numero_fila_origen=781, id_orden=None, canal_venta="Mercado Pago", plataforma_cobro="Código QR")


def test_parser_decimal_argentino_y_control_de_saldo():
    assert parsear_decimal_estado_cuenta("$ 26.316.618,06", "saldo") == Decimal("26316618.06")
    resumen = normalizar_estado_cuenta_mp("account_statement.xlsx", archivo_estado())
    assert len(resumen.movimientos) == 4
    assert resumen.variacion_neta == Decimal("120.00")
    assert resumen.saldo_final_calculado == resumen.saldo_final_informado
    assert resumen.movimientos[1].saldo_parcial is None
    assert resumen.movimientos[0].reference_id == "169679883346"


def test_vinculo_repetido_no_es_ambiguo_y_clasificacion_excluyente():
    control = controlar_estado_cuenta_mp(normalizar_estado_cuenta_mp("a.xlsx", archivo_estado()), [settlement()])
    assert [m.estado_vinculacion for m in control.movimientos[:2]] == [EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT] * 2
    assert control.lineas_vinculadas == 2
    assert control.operaciones_settlement_vinculadas == 1
    assert control.movimientos[0].categoria == CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO
    assert control.movimientos[0].subtipo == "Venta por mostrador con Código QR"
    assert control.movimientos[1].categoria == CategoriaEstadoCuentaMp.SALIDA_O_AJUSTE_IDENTIFICADO
    assert control.movimientos[2].categoria == CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO
    assert control.movimientos[3].categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE
    assert len(control.movimientos) == 4 and control.diferencia_cobertura == Decimal("0.00")


def test_excel_real_preserva_ids_fechas_y_no_contiene_formulas_rotas():
    control = controlar_estado_cuenta_mp(normalizar_estado_cuenta_mp("a.xlsx", archivo_estado()), [settlement()])
    wb = load_workbook(BytesIO(generar_control_estado_cuenta_mp_excel(control)), data_only=False)
    assert wb.sheetnames == ["MP — Control de saldo", "MP — Composición diaria", "MP — Otros ingresos", "MP — Salidas y ajustes", "MP — Asociados a ML", "MP — Sin asociación"]
    ws = wb["MP — Otros ingresos"]
    assert ws["A2"].value == "169679883346" and ws["A2"].number_format == "@"
    assert isinstance(ws["E2"].value, datetime)
    assert not any(isinstance(c.value, str) and c.value.startswith("#") for sheet in wb for row in sheet for c in row)


def _settlement(fila, operacion="OP-1", orden="ORD-1", canal="Mercado Libre", plataforma="Checkout"):
    return SimpleNamespace(id_operacion_mercado_pago=operacion, numero_fila_origen=fila, id_orden=orden, canal_venta=canal, plataforma_cobro=plataforma)


def test_varias_filas_settlement_coherentes_no_son_ambiguas():
    from kiki_control.linking.account_statement import agrupar_settlement_por_operacion
    grupo = agrupar_settlement_por_operacion([_settlement(10), _settlement(11)])["OP-1"]
    assert not grupo.es_ambiguo
    assert grupo.filas_origen == (10, 11)
    assert grupo.ids_orden == ("ORD-1",)
    assert len(grupo.movimientos) == 2


def test_filas_settlement_contradictorias_son_ambiguas():
    from kiki_control.linking.account_statement import agrupar_settlement_por_operacion
    grupo = agrupar_settlement_por_operacion([_settlement(10), _settlement(11, orden="ORD-2")])["OP-1"]
    assert grupo.es_ambiguo and "IDs de orden" in grupo.motivo_ambiguedad


def test_vinculo_canonico_se_construye_por_fila_no_comparando_ids():
    from kiki_control.linking.account_statement import construir_indice_operacion_mp_a_grupo_ml
    resultado = SimpleNamespace(id_grupo_canonico="PACK-CANONICO", tiene_mercado_libre_oficial=True, filas_origen_mp=(10, 11))
    reporte = SimpleNamespace(resultados=(resultado,))
    indice = construir_indice_operacion_mp_a_grupo_ml(reporte, [_settlement(10, orden="ORD-A"), _settlement(11, orden="ORD-B")])
    assert indice == {"OP-1": ("PACK-CANONICO",)}


def test_cobertura_se_calcula_y_detecta_faltantes_y_duplicados():
    from dataclasses import replace
    from kiki_control.domain.account_statement import ControlEstadoCuentaMp
    base = controlar_estado_cuenta_mp(normalizar_estado_cuenta_mp("a.xlsx", archivo_estado()), [settlement()])
    inconsistente = ControlEstadoCuentaMp(base.resumen, base.movimientos[:-1] + (base.movimientos[0],))
    assert inconsistente.cantidad_lineas_entrada == 4
    assert inconsistente.cantidad_lineas_clasificadas == 2
    assert inconsistente.cantidad_no_clasificadas == 1
    assert inconsistente.cantidad_clasificadas_mas_de_una_vez == 1
    assert not inconsistente.cobertura_completa
    assert inconsistente.diferencia_cobertura_monetaria != Decimal("0")


def archivo_productivo_anonimizado():
    wb = Workbook(); ws = wb.active; ws.title = "ACCOUNT_STATEMENT"
    ws.append(["INITIAL_BALANCE", "CREDITS", "DEBITS", "FINAL_BALANCE"])
    ws.append([Decimal("26316618.06"), Decimal("9222725.75"), Decimal("-16575362.17"), Decimal("18963981.64")]); ws.append([])
    ws.append(["RELEASE_DATE", "TRANSACTION_TYPE", "REFERENCE_ID", "TRANSACTION_NET_AMOUNT", "PARTIAL_BALANCE"])
    linked_ids = ["169679883346"] + [f"L-{i:03}" for i in range(1, 79)]
    for i in range(646):
        if i == 0:
            ref, tipo, importe = linked_ids[0], "Liquidación de dinero", Decimal("54875.24")
        elif i == 1:
            ref, tipo, importe = linked_ids[1], "Liquidación de dinero", Decimal("9167850.51")
        elif i == 2:
            ref, tipo, importe = linked_ids[2], "Transferencia enviada", Decimal("-16575362.17")
        elif i < 139:
            ref, tipo, importe = linked_ids[1 + (i - 1) % 78], "Liquidación de dinero", Decimal("0")
        else:
            ref, tipo, importe = f"U-{i:03}", "Liquidación de dinero", Decimal("0")
        ws.append([datetime(2026, 7, 28), tipo, ref, importe, None])
    out = BytesIO(); wb.save(out); return out.getvalue()


def test_regresion_anonimizada_cuatro_archivos_productivos():
    resumen = normalizar_estado_cuenta_mp("productivo_anonimizado.xlsx", archivo_productivo_anonimizado())
    linked_ids = ["169679883346"] + [f"L-{i:03}" for i in range(1, 79)]
    settlements = []
    for i in range(139):
        ref = linked_ids[0] if i == 0 else linked_ids[1 + (i - 1) % 78]
        if i == 0:
            settlements.append(_settlement(781, ref, None, "Mercado Pago", "Código QR"))
        else:
            settlements.append(_settlement(800 + i, ref, f"ORD-{i % 79:03}"))
    # Las múltiples filas de un ID pertenecen al mismo grupo canónico aunque sus
    # IDs de orden representen componentes diferentes de ese grupo.
    indice = {ref: (f"GRUPO-{n:03}",) for n, ref in enumerate(linked_ids[1:], 1)}
    control = controlar_estado_cuenta_mp(resumen, settlements, indice)
    assert (len(resumen.movimientos), resumen.saldo_inicial, resumen.creditos_informados, resumen.debitos_informados, resumen.saldo_final_informado) == (646, Decimal("26316618.06"), Decimal("9222725.75"), Decimal("-16575362.17"), Decimal("18963981.64"))
    assert resumen.diferencia_control == Decimal("0.00")
    assert control.lineas_vinculadas == 139
    assert control.operaciones_settlement_vinculadas == 79
    assert len(control.movimientos) - control.lineas_vinculadas == 507
    qr = next(m for m in control.movimientos if m.movimiento.reference_id == "169679883346")
    assert qr.fila_settlement == 781 and qr.movimiento.importe_neto == Decimal("54875.24")
    assert qr.categoria == CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO
    assert qr.subtipo == "Venta por mostrador con Código QR"
    assert control.cobertura_completa


def test_consolidado_agrega_hojas_solo_cuando_hay_account_statement():
    from kiki_control.exporting import generar_reporte_consolidado_excel
    from tests.test_control_consolidado_diagnostics import r, rep
    reporte = rep([r("grupo")])
    control = controlar_estado_cuenta_mp(normalizar_estado_cuenta_mp("a.xlsx", archivo_estado()), [settlement()])
    sin = load_workbook(BytesIO(generar_reporte_consolidado_excel(reporte)))
    con = load_workbook(BytesIO(generar_reporte_consolidado_excel(reporte, control_estado_cuenta=control)))
    hojas_mp = {"MP — Control de saldo", "MP — Composición diaria", "MP — Otros ingresos", "MP — Salidas y ajustes", "MP — Asociados a ML", "MP — Sin asociación"}
    assert not hojas_mp.intersection(sin.sheetnames)
    assert hojas_mp.issubset(con.sheetnames)


def test_vinculo_canonico_clasifica_ml_y_multiples_grupos_son_ambiguos():
    resumen = normalizar_estado_cuenta_mp("a.xlsx", archivo_estado())
    mov = _settlement(10, "169679883346", "ORD-DISTINTO", "Mercado Libre", "Checkout")
    control_ml = controlar_estado_cuenta_mp(resumen, [mov], {"169679883346": ("GRUPO-CANONICO",)})
    assert control_ml.movimientos[0].categoria == CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML
    assert control_ml.movimientos[0].id_grupo_ml == "GRUPO-CANONICO"
    control_ambiguo = controlar_estado_cuenta_mp(resumen, [mov], {"169679883346": ("GRUPO-A", "GRUPO-B")})
    assert control_ambiguo.movimientos[0].estado_vinculacion == EstadoVinculacionEstadoCuentaMp.ID_AMBIGUO
    assert control_ambiguo.movimientos[0].categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE
