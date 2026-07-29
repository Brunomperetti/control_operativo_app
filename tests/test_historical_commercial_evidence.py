from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from kiki_control.domain.account_statement import (
    CategoriaEstadoCuentaMp, MovimientoEstadoCuentaMp, OrigenComercialOperacionMp,
    ResumenEstadoCuentaMp,
)
from kiki_control.linking.account_statement import (
    agrupar_settlement_por_operacion, construir_evidencias_comerciales_operaciones,
    controlar_estado_cuenta_mp,
)


def settlement(op="HIST", fila=10, orden="ORD-H", canal="Mercado Libre", plataforma="Checkout"):
    return SimpleNamespace(id_operacion_mercado_pago=op, numero_fila_origen=fila, id_orden=orden,
                           id_paquete=None, canal_venta=canal, plataforma_cobro=plataforma)


def resumen(tipo="Liquidación de dinero", importe="10", ref="HIST"):
    m = MovimientoEstadoCuentaMp(5, datetime(2026, 7, 20), tipo, ref, Decimal(importe), None, "h", "s")
    return ResumenEstadoCuentaMp(Decimal("100"), max(Decimal(importe), Decimal("0")),
                                 min(Decimal(importe), Decimal("0")), Decimal("100") + Decimal(importe),
                                 (m,), m.fecha_liberacion, m.fecha_liberacion)


@pytest.mark.parametrize("tipo", ["Devolución de dinero", "Dinero retenido", "Comisión", "Impuesto"])
def test_movimiento_ml_historico_negativo_sigue_siendo_ml(tipo):
    item = controlar_estado_cuenta_mp(resumen(tipo, "-10"), [settlement()]).movimientos[0]
    assert item.categoria == CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML
    assert item.subtipo == "Movimiento de operación Mercado Libre histórica"


def test_venta_ml_historica_positiva_fuera_de_b1():
    item = controlar_estado_cuenta_mp(resumen(), [settlement()]).movimientos[0]
    assert item.categoria == CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML
    assert item.id_grupo_ml is None


@pytest.mark.parametrize(("plataforma", "subtipo"), [("Código QR", "Venta por mostrador con Código QR"), ("Point Smart", "Venta con Point")])
def test_qr_y_point_no_se_confunden_con_ml(plataforma, subtipo):
    mov = settlement(canal="Mercado Pago", plataforma=plataforma)
    item = controlar_estado_cuenta_mp(resumen(), [mov]).movimientos[0]
    assert item.categoria == CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO
    assert item.subtipo == subtipo


def test_mezcla_ml_qr_es_ambigua():
    grupos = agrupar_settlement_por_operacion([settlement(), settlement(fila=11, canal="Mercado Pago", plataforma="Código QR")])
    evidencia = construir_evidencias_comerciales_operaciones(grupos)["HIST"]
    assert evidencia.origen_comercial == OrigenComercialOperacionMp.AMBIGUO
    assert evidencia.es_ambiguo


def test_operacion_b1_canonica_tiene_evidencia_prioritaria():
    control = controlar_estado_cuenta_mp(resumen(), [settlement()], {"HIST": ("GRUPO-B1",)})
    item = control.movimientos[0]
    assert item.categoria == CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML
    assert item.id_grupo_ml == "GRUPO-B1"
    evidencia = construir_evidencias_comerciales_operaciones(
        agrupar_settlement_por_operacion([settlement()], {"HIST": ("GRUPO-B1",)}))["HIST"]
    assert evidencia.origen_comercial == OrigenComercialOperacionMp.MERCADO_LIBRE_PERIODO_B1
