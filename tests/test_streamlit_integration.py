from csv import DictWriter
from io import StringIO
from decimal import Decimal

from tests.test_mercado_pago_normalization import fila as fila_mp, xlsx as crear_xlsx_mp
from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.presentation.reconciliation_view import filas_presentacion
from kiki_control.reconciliation import reconciliar

ML_COLS = ["Fecha de venta","Hora","Producto","Sku","ID Order","Cantidad","Monto de venta ($)","Costo Total (Con IVA) ($)","Comisión MeLi  ($)","Costo de envío (Seller) ($)","Monto neto (en MP) ($)","Utilidades netas ($)","Parámetros cálculo"]


def _csv_ml():
    out = StringIO()
    writer = DictWriter(out, fieldnames=ML_COLS)
    writer.writeheader()
    for oid, neto in [("100", "100,00"), ("200", "100,00"), ("300", "100,00")]:
        writer.writerow({"Fecha de venta":"2026-07-18","Hora":"10:00:00","Producto":"Producto sintético","Sku":"SKU","ID Order":oid,"Cantidad":"1","Monto de venta ($)":"150,00","Costo Total (Con IVA) ($)":"40,00","Comisión MeLi  ($)":"10,00","Costo de envío (Seller) ($)":"0,00","Monto neto (en MP) ($)":neto,"Utilidades netas ($)":"20,00","Parámetros cálculo":"Costo inc. alíc.: Sí | Precio inc. alíc.: Sí | IIBB: 0 (0%)"})
    return out.getvalue().encode("utf-8")


def _xlsx_mp():
    return crear_xlsx_mp([
        fila_mp(**{"ID DE OPERACIÓN EN MERCADO PAGO": "mp-100", "ID DE LA ORDEN": "100", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "100.00"}),
        fila_mp(**{"ID DE OPERACIÓN EN MERCADO PAGO": "mp-200-a", "ID DE LA ORDEN": "200", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "40.00"}),
        fila_mp(**{"ID DE OPERACIÓN EN MERCADO PAGO": "mp-200-b", "ID DE LA ORDEN": "200", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "60.00"}),
        fila_mp(**{"ID DE OPERACIÓN EN MERCADO PAGO": "mp-300", "ID DE LA ORDEN": "300", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "90.00"}),
        fila_mp(**{"ID DE OPERACIÓN EN MERCADO PAGO": "mp-payout", "TIPO DE OPERACIÓN": "PAYOUTS", "ID DE LA ORDEN": "", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO": "-25.00"}),
    ])


def test_integral_sintetica_inspeccion_normalizacion_conciliacion_presentacion():
    csv = _csv_ml(); xlsx = _xlsx_mp()
    insp_ml = inspeccionar_archivo("ventas.csv", csv)
    insp_mp = inspeccionar_archivo("movimientos.xlsx", xlsx)
    assert insp_ml.fuente_detectada == TipoFuente.MERCADO_LIBRE and insp_ml.es_valido
    assert insp_mp.fuente_detectada == TipoFuente.MERCADO_PAGO and insp_mp.es_valido
    norm_ml = normalizar_mercado_libre("ventas.csv", csv)
    norm_mp = normalizar_mercado_pago("movimientos.xlsx", xlsx)
    assert norm_ml.cantidad_normalizada == 3
    assert norm_mp.cantidad_normalizada == 5
    reporte = reconciliar(norm_ml.operaciones, norm_mp.movimientos, Decimal("0.01"))
    estados = {r.id_orden: r.estado for r in reporte.resultados if r.id_orden}
    assert estados["100"] == EstadoConciliacion.CONCILIADA
    assert next(r for r in reporte.resultados if r.id_orden == "200").es_pago_dividido
    assert estados["300"] == EstadoConciliacion.CONCILIADA_CON_DIFERENCIA
    assert any(r.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS for r in reporte.resultados)
    filas = filas_presentacion(reporte.resultados)
    assert any(f.id_orden == "200" and f.pago_dividido == "Sí" for f in filas)
