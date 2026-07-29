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
