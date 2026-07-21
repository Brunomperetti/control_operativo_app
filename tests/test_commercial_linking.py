from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, is_dataclass
from datetime import datetime
from decimal import Decimal

import pytest

from kiki_control.domain.commercial_link import EstadoValidacionSku, EstadoVinculacionComercial, MetodoVinculacionComercial, ResultadoVinculacionComercial
from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.linking import vincular_ventas_oficiales_con_eccomapp


def venta(id_venta: str, sku: str | None = "SKU", fila: int = 1, total: Decimal = Decimal("10")) -> VentaOficialMercadoLibre:
    return VentaOficialMercadoLibre(
        fila_origen=fila,
        hash_importacion="hash-ml",
        id_venta=id_venta,
        fecha_venta=None,
        estado="Entregada",
        descripcion_estado=None,
        paquete_varios_productos=None,
        pertenece_kit=None,
        unidades=1,
        ingresos_productos=total,
        cargo_venta_impuestos=None,
        ingresos_envio=None,
        costos_envio=None,
        costo_envio_declarado=None,
        cargo_diferencias_envio=None,
        descuentos_bonificaciones=None,
        anulaciones_reembolsos=None,
        total_informado_ml=total,
        sku=sku,
        id_publicacion=None,
        canal_venta=None,
        titulo_publicacion=None,
        variante=None,
        precio_unitario=None,
        forma_entrega=None,
        reclamo_abierto=None,
        reclamo_cerrado=None,
        con_mediacion=None,
    )


def op(id_orden: str, carrito: str | None = None, sku: str | None = "SKU", fila: int = 1) -> OperacionComercial:
    return OperacionComercial(
        fuente="ECCOMAPP_RENTABILIDAD", hash_importacion="hash-ec", numero_fila_origen=fila,
        id_orden=id_orden, id_carrito=carrito, sku=sku, fecha_venta_original="2026-01-01",
        hora_venta_original="10:00", fecha_hora_venta=datetime(2026, 1, 1, 10),
        producto="Producto sintético", tipo_envio=None, provincia=None, cantidad=1,
        precio_unitario=Decimal("10"), monto_venta=Decimal("10"), costo_unitario_con_iva=None,
        costo_total_con_iva=Decimal("5"), comision_mercado_libre_informada=None,
        costo_envio_bruto=None, costo_envio_vendedor=None, costo_envio_prorrateado=None,
        bonificacion_envio=None, monto_neto_mercado_pago_informado=Decimal("9"),
        impuestos_y_comisiones_informados=None, utilidad_neta_informada=Decimal("4"),
        precio_equilibrio=None, tasa_iva=None, rentabilidad_precio_venta=None,
        rentabilidad_costo_producto=None, rentabilidad_suma_costos=None,
        tasa_comision_mercado_libre=None, tasa_costo_envio=None, parametros_calculo_original="{}",
        costo_incluye_alicuota=None, precio_incluye_alicuota=None, tasa_iibb_configurada=None,
    )

def unico(rep):
    assert len(rep.resultados) == 1
    return rep.resultados[0]


def test_venta_individual_por_id_order():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1")], [op("O1", None)]))
    assert r.estado == EstadoVinculacionComercial.VINCULADA
    assert r.metodos_vinculacion == (MetodoVinculacionComercial.ID_ORDER,)
    assert r.id_grupo_canonico == "O1"


def test_carrito_con_principal_y_detalles_sin_grupos_separados():
    rep = vincular_ventas_oficiales_con_eccomapp([venta("C1", None), venta("O1", "A", 2), venta("O2", "B", 3)], [op("O1", "C1", "A"), op("O2", "C1", "B", 2)])
    r = unico(rep)
    assert r.venta_principal_ml.id_venta == "C1"
    assert [v.id_venta for v in r.ventas_detalle_ml] == ["O1", "O2"]
    assert r.estado_validacion_sku == EstadoValidacionSku.COINCIDE


def test_sku_ausente_en_ambas_no_rompe_vinculo_ni_revision():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1", None)], [op("O1", None, None)]))
    assert r.estado_validacion_sku == EstadoValidacionSku.NO_DISPONIBLE_EN_AMBAS
    assert not r.requiere_revision


def test_sku_divergente_conserva_vinculo_con_observaciones():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1", "A")], [op("O1", None, "B")]))
    assert r.estado == EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES
    assert r.requiere_revision


def test_solo_mercado_libre_cancelada_total_cero_prudente():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("ML1", None, total=Decimal("0"))], []))
    assert r.estado == EstadoVinculacionComercial.SOLO_MERCADO_LIBRE
    assert not r.requiere_revision
    assert "puede ser cancelación" in r.explicaciones[0]


def test_solo_eccomapp_requiere_revision():
    r = unico(vincular_ventas_oficiales_con_eccomapp([], [op("O1")]))
    assert r.estado == EstadoVinculacionComercial.SOLO_ECCOMAPP
    assert r.requiere_revision


def test_colision_carrito_y_orden_otro_grupo_ambigua():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("X")], [op("O1", "X"), op("X", "C2", fila=2)]))
    assert r.estado == EstadoVinculacionComercial.AMBIGUA
    assert r.requiere_revision
    assert r.id_grupo_canonico is None


def test_id_order_duplicado_no_fuerza_vinculacion():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1")], [op("O1", "C1"), op("O1", "C2", fila=2)]))
    assert r.estado == EstadoVinculacionComercial.DUPLICADA
    assert r.requiere_revision


def test_venta_principal_faltante_conserva_detalles():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1", fila=2)], [op("O1", "C1"), op("O2", "C1", fila=2)]))
    assert r.estado == EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES
    assert r.venta_principal_ml is None
    assert r.requiere_revision


def test_determinismo_e_inmutabilidad_y_trazabilidad():
    ventas = [venta("O2", fila=2), venta("O1", fila=1)]
    ops = [op("O2", fila=2), op("O1", fila=1)]
    rep1 = vincular_ventas_oficiales_con_eccomapp(ventas, ops)
    rep2 = vincular_ventas_oficiales_con_eccomapp(reversed(ventas), reversed(ops))
    assert rep1 == rep2
    assert isinstance(rep1.resultados, tuple)
    assert rep1.hashes_importacion_ml == ("hash-ml",)
    assert rep1.hashes_importacion_eccomapp == ("hash-ec",)
    assert is_dataclass(ResultadoVinculacionComercial)
    with pytest.raises(FrozenInstanceError):
        rep1.resultados[0].clave_resultado = "x"


def test_independencia_de_dependencias_de_interfaz_y_tabulares():
    import ast
    from pathlib import Path
    tree = ast.parse(Path("src/kiki_control/linking/commercial.py").read_text())
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    imports |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert {"pandas", "openpyxl", "streamlit", "ui", "presentation"}.isdisjoint(imports)


def test_privacidad_en_resultado_no_incorpora_valores_personales():
    r = unico(vincular_ventas_oficiales_con_eccomapp([venta("O1")], [op("O1")]))
    serializado = repr(asdict(r)).lower()
    assert "comprador" not in serializado
    assert "dni" not in serializado
    assert "domicilio" not in serializado
