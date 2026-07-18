from csv import writer
from dataclasses import is_dataclass
from decimal import Decimal
from io import StringIO

from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from tests.test_file_inspector import MP, csv_bytes

ML = [
    "Fecha de venta", "Hora", "Producto", "Sku", "ID Order", "ID Carrito", "Cantidad",
    "Precio unitario ($)", "Monto de venta ($)", "Costo Unitario (Con IVA) ($)", "Costo Total (Con IVA) ($)",
    "Comisión MeLi  ($)", "Costo de envío (Bruto) ($)", "Costo de envío (Seller) ($)", "Costo de envío prorrateado ($)",
    "Bonificación envío ($)", "Monto neto (en MP) ($)", "Impuestos y comisiones ($)", "Utilidades netas ($)",
    "Precio de equilibrio ($)", "IVA", "Rentabilidad s/ precio venta", "Rentabilidad s/ costo producto", "Rentabilidad s/ suma costos",
    "% Comisión MeLi", "% Costo de envío", "Parámetros cálculo", "Tipo de envío", "Provincia",
]


def fila(**overrides):
    base = {
        "Fecha de venta": "2026-07-18", "Hora": "14:35:00", "Producto": "Producto sintético", "Sku": "SKU-1",
        "ID Order": "1234567890123456", "ID Carrito": "", "Cantidad": "2", "Precio unitario ($)": "47.239",
        "Monto de venta ($)": "7.478,66", "Costo Unitario (Con IVA) ($)": "1.000", "Costo Total (Con IVA) ($)": "193.971",
        "Comisión MeLi  ($)": "0,00", "Costo de envío (Bruto) ($)": "0,00", "Costo de envío (Seller) ($)": "0,00",
        "Costo de envío prorrateado ($)": "", "Bonificación envío ($)": "", "Monto neto (en MP) ($)": "7.478,66",
        "Impuestos y comisiones ($)": "", "Utilidades netas ($)": "-1.000,50", "Precio de equilibrio ($)": "",
        "IVA": "21%", "Rentabilidad s/ precio venta": "22.7%", "Rentabilidad s/ costo producto": "", "Rentabilidad s/ suma costos": "",
        "% Comisión MeLi": "", "% Costo de envío": "0.00%", "Parámetros cálculo": "Costo inc. alíc.: Sí | Precio inc. alíc.: Sí | IIBB: 0 (0%)",
        "Tipo de envío": "Flex", "Provincia": "Córdoba",
    }
    base.update(overrides)
    return [base[c] for c in ML]


def contenido(filas):
    salida = StringIO()
    w = writer(salida)
    w.writerow(ML)
    w.writerows(filas)
    return salida.getvalue().encode("utf-8")


def test_normaliza_operacion_comercial_completa():
    resultado = normalizar_mercado_libre("ventas.csv", contenido([fila(Sku="")]), zona_horaria="UTC")
    op = resultado.operaciones[0]
    assert resultado.cantidad_total_recibida == 1
    assert resultado.cantidad_normalizada == 1
    assert resultado.cantidad_rechazada == 0
    assert op.id_orden == "1234567890123456"
    assert op.id_carrito is None
    assert op.sku is None
    assert op.precio_unitario == Decimal("47239")
    assert op.monto_venta == Decimal("7478.66")
    assert op.costo_total_con_iva == Decimal("193971")
    assert op.comision_mercado_libre_informada == Decimal("0.00")
    assert op.precio_equilibrio is None
    assert op.utilidad_neta_informada == Decimal("-1000.50")
    assert op.cantidad == 2
    assert op.fecha_hora_venta.isoformat() == "2026-07-18T14:35:00+00:00"
    assert op.tasa_iva == Decimal("0.21")
    assert op.rentabilidad_precio_venta == Decimal("0.227")
    assert any(a.codigo == "SKU_VACIO" for a in resultado.advertencias)
    assert any(a.codigo == "PRECIO_EQUILIBRIO_VACIO" for a in resultado.advertencias)
    assert not hasattr(resultado, "dataframe")


def test_zona_horaria_predeterminada_y_hash_de_inspeccion():
    data = contenido([fila()])
    resultado = normalizar_mercado_libre("ventas.csv", data)
    assert resultado.operaciones[0].fecha_hora_venta.tzinfo.key == "America/Argentina/Cordoba"
    assert resultado.operaciones[0].hash_importacion == resultado.hash_importacion


def test_cantidad_cero_y_fecha_invalida_rechazan_fila():
    resultado = normalizar_mercado_libre("ventas.csv", contenido([fila(Cantidad="0"), fila(**{"Fecha de venta": "fecha mala"})]))
    assert resultado.cantidad_total_recibida == 2
    assert resultado.cantidad_rechazada == 2
    assert {e.codigo for e in resultado.errores} >= {"CANTIDAD_INVALIDA", "FECHA_HORA_INVALIDA"}


def test_importes_requeridos_invalidos_rechazan_fila():
    resultado = normalizar_mercado_libre("ventas.csv", contenido([fila(**{"Monto de venta ($)": "abc"})]))
    assert resultado.cantidad_rechazada == 1
    assert resultado.errores[0].codigo == "IMPORTE_INVALIDO"


def test_parametros_con_si_no_y_desconocidos():
    resultado = normalizar_mercado_libre("ventas.csv", contenido([
        fila(**{"Parámetros cálculo": "Costo inc. alíc.: Sí | Precio inc. alíc.: Sí | IIBB: 0 (0%)"}),
        fila(**{"Parámetros cálculo": "Costo inc. alíc.: No | Precio inc. alíc.: Sí | IIBB: 0 (0%)"}),
        fila(**{"Parámetros cálculo": "texto desconocido"}),
    ]))
    assert resultado.operaciones[0].costo_incluye_alicuota is True
    assert resultado.operaciones[1].costo_incluye_alicuota is False
    assert resultado.operaciones[2].parametros_calculo_original == "texto desconocido"
    assert any(a.codigo == "PARAMETROS_CALCULO_NO_RECONOCIDOS" for a in resultado.advertencias)


def test_csv_con_fila_valida_y_otra_invalida_totales_correctos():
    resultado = normalizar_mercado_libre("ventas.csv", contenido([fila(), fila(**{"Cantidad": "x"})]))
    assert resultado.cantidad_total_recibida == 2
    assert resultado.cantidad_normalizada == 1
    assert resultado.cantidad_rechazada == 1
    assert is_dataclass(resultado.operaciones[0])


def test_archivo_mercado_pago_no_se_procesa_como_mercado_libre():
    resultado = normalizar_mercado_libre("mp.csv", csv_bytes(MP))
    assert resultado.cantidad_normalizada == 0
    assert resultado.errores[0].codigo == "FUENTE_NO_COMPATIBLE"
