from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from kiki_control.domain.commercial_link import EstadoVinculacionComercial
from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.control_consolidado import ErrorControlConsolidado, EstadoControlConsolidado, ReporteControlConsolidado, ResultadoControlConsolidado, TipoMovimientoFinanciero
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.domain.reconciliation import EstadoConciliacion, MotivoConciliacion, ReporteConciliacion, ResultadoConciliacion
from kiki_control.linking import consolidar_control_financiero, vincular_ventas_oficiales_con_eccomapp

D = Decimal
NOW = datetime(2026, 1, 1, 12)


def venta(id_venta: str, fila: int = 1, total: Decimal = D("80"), ingresos: Decimal = D("100")):
    return VentaOficialMercadoLibre(
        fila_origen=fila, hash_importacion="hash-ml", id_venta=id_venta, fecha_venta=None,
        estado="Entregada", descripcion_estado=None, paquete_varios_productos=None, pertenece_kit=None,
        unidades=1, ingresos_productos=ingresos, cargo_venta_impuestos=D("-10"), ingresos_envio=D("5"),
        costos_envio=D("-3"), costo_envio_declarado=None, cargo_diferencias_envio=None,
        descuentos_bonificaciones=D("-2"), anulaciones_reembolsos=D("0"), total_informado_ml=total,
        sku="SKU", id_publicacion=None, canal_venta=None, titulo_publicacion=None, variante=None,
        precio_unitario=None, forma_entrega=None, reclamo_abierto=None, reclamo_cerrado=None, con_mediacion=None,
    )


def op(id_orden: str, carrito: str | None = None, fila: int = 1, venta_monto: Decimal = D("100"), costo: Decimal = D("40"), neto: Decimal = D("80"), utilidad: Decimal = D("30")):
    return OperacionComercial(
        fuente="ECCOMAPP_RENTABILIDAD", hash_importacion="hash-ec", numero_fila_origen=fila,
        id_orden=id_orden, id_carrito=carrito, sku="SKU", fecha_venta_original="2026-01-01",
        hora_venta_original="10:00", fecha_hora_venta=NOW, producto="Producto sintético", tipo_envio=None,
        provincia=None, cantidad=1, precio_unitario=venta_monto, monto_venta=venta_monto,
        costo_unitario_con_iva=None, costo_total_con_iva=costo, comision_mercado_libre_informada=None,
        costo_envio_bruto=None, costo_envio_vendedor=D("7"), costo_envio_prorrateado=None,
        bonificacion_envio=None, monto_neto_mercado_pago_informado=neto, impuestos_y_comisiones_informados=None,
        utilidad_neta_informada=utilidad, precio_equilibrio=None, tasa_iva=None, rentabilidad_precio_venta=None,
        rentabilidad_costo_producto=None, rentabilidad_suma_costos=None, tasa_comision_mercado_libre=None,
        tasa_costo_envio=None, parametros_calculo_original="{}", costo_incluye_alicuota=None,
        precio_incluye_alicuota=None, tasa_iibb_configurada=None,
    )


def fin(id_orden: str | None, fila: int = 1, neto: Decimal | None = D("80"), estado=EstadoConciliacion.CONCILIADA, revision=False, motivos=(MotivoConciliacion.COINCIDENCIA_NETA_EXACTA,), comercial_hashes=("hash-ec",), payout=False, **flags):
    return ResultadoConciliacion(id_orden, tuple(comercial_hashes), ("hash-mp",), (), (fila,), NOW, "ML_MP_ID_ORDER_NETO_V1", EstadoConciliacion.MOVIMIENTO_DE_FONDOS if payout else estado, motivos, ("explicación sintética",), revision, flags.get("pago_dividido", False), 0, 1, 1 if neto is not None else 0, None, neto, None, D("4") if flags.get("pago_envio", False) else D("0"), D("-5") if flags.get("devolucion", False) else D("0"), D("-6") if flags.get("reclamo", False) or flags.get("disputa", False) else D("0"), D("0"), neto or D("0"), None, D("0.50"), flags.get("devolucion", False), flags.get("reclamo", False), flags.get("disputa", False), flags.get("pago_envio", False), flags.get("desconocido", False), flags.get("pendiente", False), flags.get("duplicados", False))


def reporte(ventas, ops, fins, tolerancia=D("0.50")):
    return consolidar_control_financiero(vincular_ventas_oficiales_con_eccomapp(ventas, ops), ReporteConciliacion(tuple(fins), NOW, "ML_MP_ID_ORDER_NETO_V1", tolerancia, len(ops), len(fins)))


def unico(rep):
    assert len(rep.resultados) == 1
    return rep.resultados[0]


def test_venta_individual_completa_tres_fuentes_y_formulas():
    r = unico(reporte([venta("O1")], [op("O1")], [fin("O1")]))
    assert r.estado == EstadoControlConsolidado.COMPLETA
    assert (r.monto_venta_ml, r.cargo_venta_impuestos_ml, r.ingresos_envio_ml, r.costo_envio_ml, r.descuentos_bonificaciones_ml, r.anulaciones_reembolsos_ml, r.total_informado_ml) == (D("100"), D("-10"), D("5"), D("-3"), D("-2"), D("0"), D("80"))
    assert r.costo_productos_eccomapp == D("40")
    assert r.diferencia_venta_ml_eccomapp == D("0")
    assert r.diferencia_neto_ml_eccomapp == D("0")
    assert r.diferencia_ml_mp == D("0")
    assert r.utilidad_preliminar_control == D("40")


def test_carrito_varias_ordenes_y_varios_resultados_mp_usa_cabecera_sin_sumar_detalles():
    rep = reporte([venta("C1", 1, D("150"), D("200")), venta("O1", 2, D("999"), D("999")), venta("O2", 3, D("999"), D("999"))], [op("O1", "C1", 1, costo=D("30")), op("O2", "C1", 2, costo=D("50"))], [fin("O1", 1, D("70")), fin("O2", 2, D("80"))])
    r = unico(rep)
    assert r.total_informado_ml == D("150")
    assert r.monto_venta_ml == D("200")
    assert r.costo_productos_eccomapp == D("80")
    assert r.neto_aprobado_mp == D("150")


def test_total_ml_oficial_no_se_reconstruye():
    r = unico(reporte([venta("O1", total=D("77"), ingresos=D("100"))], [op("O1", neto=D("77"))], [fin("O1", neto=D("77"))]))
    assert r.total_informado_ml == D("77")
    assert r.utilidad_preliminar_control == D("37")


def test_diferencias_positiva_negativa_cero_y_tolerancia():
    assert unico(reporte([venta("O1")], [op("O1")], [fin("O1", neto=D("81"))])).diferencia_ml_mp == D("1")
    assert unico(reporte([venta("O1")], [op("O1")], [fin("O1", neto=D("79"))])).diferencia_ml_mp == D("-1")
    assert unico(reporte([venta("O1")], [op("O1")], [fin("O1", neto=D("80.25"))])).estado == EstadoControlConsolidado.COMPLETA
    assert unico(reporte([venta("O1")], [op("O1")], [fin("O1", neto=D("80.75"))])).estado == EstadoControlConsolidado.CON_DIFERENCIA


def test_utilidad_eccomapp_conservada_separada_y_costo_agregado():
    r = unico(reporte([venta("C1")], [op("O1", "C1", 1, costo=D("10"), utilidad=D("3")), op("O2", "C1", 2, costo=D("20"), utilidad=D("4"))], [fin("O1", 1, D("40")), fin("O2", 2, D("40"))]))
    assert r.costo_productos_eccomapp == D("30")
    assert r.utilidad_eccomapp_informada == D("7")
    assert r.utilidad_preliminar_control == D("50")


def test_solo_ml_sin_eccomapp_utilidad_none_y_sin_costo():
    r = unico(reporte([venta("ML1")], [], []))
    assert r.estado == EstadoControlConsolidado.SIN_COSTO_PRODUCTO
    assert r.utilidad_preliminar_control is None


def test_eccomapp_sin_venta_oficial_y_grupo_sin_mp():
    r = unico(reporte([], [op("O1")], []))
    assert r.estado == EstadoControlConsolidado.SIN_VENTA_OFICIAL
    assert r.tiene_eccomapp and not r.tiene_mercado_libre_oficial and not r.tiene_mercado_pago


def test_mp_sin_grupo_sin_orden_y_payout_movimiento_de_fondos():
    rep = reporte([], [], [fin("O9", comercial_hashes=()), fin(None, 2, comercial_hashes=()), fin(None, 3, comercial_hashes=(), payout=True, motivos=(MotivoConciliacion.PAYOUT_SIN_ORDEN,))])
    assert rep.total_solo_movimiento_financiero == 3
    payout = next(r for r in rep.resultados if r.tipo_movimiento_financiero == TipoMovimientoFinanciero.MOVIMIENTO_DE_FONDOS)
    assert payout.estado == EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO


def test_devolucion_reclamo_disputa_liquidacion_pendiente_e_indicadores():
    r = unico(reporte([venta("O1")], [op("O1")], [fin("O1", estado=EstadoConciliacion.EN_RECLAMO, revision=True, devolucion=True, reclamo=True, disputa=True, pendiente=True, pago_dividido=True, desconocido=True, duplicados=True)]))
    assert r.estado == EstadoControlConsolidado.EN_REVISION_FINANCIERA
    assert r.indicadores_financieros.tiene_devolucion
    assert r.indicadores_financieros.tiene_reclamo
    assert r.indicadores_financieros.tiene_disputa
    assert r.indicadores_financieros.tiene_liquidacion_pendiente
    assert r.indicadores_financieros.tiene_pago_dividido
    assert r.indicadores_financieros.tiene_movimiento_desconocido
    assert r.indicadores_financieros.tiene_duplicados


def test_id_order_comercial_ambiguo_no_asigna_mp_y_particion():
    rep = reporte([venta("O1", 1), venta("O1", 2)], [op("O1")], [fin("O1")])
    assert any(r.estado == EstadoControlConsolidado.DUPLICADA_O_AMBIGUA for r in rep.resultados)
    assert sum(len(r.claves_resultados_financieros) for r in rep.resultados) == 1
    assert next(r for r in rep.resultados if r.tiene_mercado_pago).claves_resultados_comerciales == ()


def test_particion_exacta_determinismo_e_inmutabilidad():
    ventas = [venta("O2", 2), venta("O1", 1)]
    ops = [op("O2", fila=2), op("O1", fila=1)]
    fins = [fin("O2", 2), fin("O1", 1)]
    rep1 = reporte(ventas, ops, fins)
    rep2 = reporte(list(reversed(ventas)), list(reversed(ops)), list(reversed(fins)))
    assert rep1 == rep2
    assert is_dataclass(ReporteControlConsolidado) and is_dataclass(ResultadoControlConsolidado)
    assert isinstance(rep1.resultados, tuple)
    assert sum(len(r.claves_resultados_comerciales) for r in rep1.resultados) == rep1.total_resultados_comerciales_recibidos
    assert sum(len(r.claves_resultados_financieros) for r in rep1.resultados) == rep1.total_resultados_financieros_recibidos
    with pytest.raises(FrozenInstanceError):
        rep1.resultados[0].clave_resultado = "x"


def test_todos_los_importes_decimal_o_none_sin_float_y_sin_dependencias_tabulares():
    r = unico(reporte([venta("O1")], [op("O1")], [fin("O1")]))
    for campo, valor in asdict(r).items():
        if campo.endswith(("ml", "mp")) or "eccomapp" in campo or campo.startswith(("diferencia", "utilidad", "tolerancia")):
            assert not isinstance(valor, float)
    tree = ast.parse(Path("src/kiki_control/linking/control_financiero.py").read_text())
    imports = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert {"pandas", "openpyxl", "streamlit"}.isdisjoint(imports)
    assert "DataFrame" not in Path("src/kiki_control/linking/control_financiero.py").read_text()


def test_sin_pii_en_modelos_repr_asdict_errores_y_explicaciones():
    r = unico(reporte([venta("O1")], [op("O1")], [fin("O1")]))
    texto = (repr(r) + repr(asdict(r)) + " ".join(r.explicaciones)).lower()
    for pii in ("comprador", "dni", "domicilio", "documento", "dirección"):
        assert pii not in texto


def test_hashes_incompatibles_generan_error_de_dominio():
    with pytest.raises(ErrorControlConsolidado, match="hashes comerciales"):
        reporte([venta("O1")], [op("O1")], [fin("O1", comercial_hashes=("otro-hash",))])
