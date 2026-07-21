from dataclasses import asdict, fields
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from kiki_control.adapters.mercado_libre_ventas import normalizar_ventas_mercado_libre
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

COLUMNAS = [
    "# de venta", "Fecha de venta", "Estado", "Descripción del estado", "Paquete de varios productos", "Pertenece a un kit", "Unidades",
    "Ingresos por productos (ARS)", "Cargo por venta e impuestos", "Ingresos por envío (ARS)", "Costos de envío (ARS)", "Costo de envío declarado",
    "Cargo por diferencias en costos de envío", "Descuentos y bonificaciones", "Anulaciones y reembolsos", "Total (ARS)", "SKU", "# de publicación",
    "Canal de venta", "Título de la publicación", "Variante", "Precio unitario", "Forma de entrega", "Reclamo abierto", "Estado del reclamo",
]


def xlsx_ventas(filas, hoja="Ventas AR", intro=True):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    if intro:
        ws.append(["Reporte sintético"])
        ws.append(["Generado para pruebas"])
    ws.append(COLUMNAS)
    for fila in filas:
        ws.append([fila.get(c) for c in COLUMNAS])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def fila(id_venta="12345678901234567890", estado="Entregado", total="100.50"):
    return {
        "# de venta": id_venta,
        "Fecha de venta": "2026-07-01 10:30:00",
        "Estado": estado,
        "Descripción del estado": "Estado operativo",
        "Paquete de varios productos": "No",
        "Pertenece a un kit": "Sí",
        "Unidades": 1,
        "Ingresos por productos (ARS)": "150.75",
        "Cargo por venta e impuestos": "-20.25",
        "Ingresos por envío (ARS)": "0",
        "Costos de envío (ARS)": "-10",
        "Costo de envío declarado": "0",
        "Cargo por diferencias en costos de envío": "0",
        "Descuentos y bonificaciones": "-20",
        "Anulaciones y reembolsos": "0",
        "Total (ARS)": total,
        "SKU": "SKU-SINTETICO-0001",
        "# de publicación": "98765432109876543210",
        "Canal de venta": "Mercado Libre",
        "Título de la publicación": "Producto sintético",
        "Variante": "Variante sintética",
        "Precio unitario": "150.75",
        "Forma de entrega": "Envío",
        "Reclamo abierto": "No",
        "Estado del reclamo": "Sin reclamo",
    }


def test_encabezado_despues_de_filas_introductorias_y_metadatos():
    contenido = xlsx_ventas([fila()])
    inspeccion = inspeccionar_archivo("nombre_irrelevante.bin.xlsx", contenido)
    assert inspeccion.es_valido
    assert inspeccion.fuente_detectada == TipoFuente.MERCADO_LIBRE_VENTAS
    assert inspeccion.metadatos.nombre_hoja == "Ventas AR"
    assert inspeccion.metadatos.cantidad_filas == 1
    assert inspeccion.metadatos.columnas_encontradas == tuple(COLUMNAS)

    resultado = normalizar_ventas_mercado_libre("otro_nombre.xlsx", contenido)
    venta = resultado.ventas[0]
    assert resultado.hash_importacion == inspeccion.metadatos.sha256
    assert resultado.hoja_procesada == "Ventas AR"
    assert venta.fila_origen == 4
    assert venta.hash_importacion == inspeccion.metadatos.sha256


def test_importes_decimal_ids_texto_y_estados_operativos():
    contenido = xlsx_ventas([fila(), fila("22222222222222222222", "Cancelada", "0"), fila("33333333333333333333", "Devuelta", "-25")])
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", contenido)
    assert resultado.cantidad_normalizada == 3
    assert [v.estado for v in resultado.ventas] == ["Entregado", "Cancelada", "Devuelta"]
    assert resultado.ventas[0].id_venta == "12345678901234567890"
    assert resultado.ventas[0].id_publicacion == "98765432109876543210"
    assert resultado.ventas[0].ingresos_productos == Decimal("150.75")
    assert resultado.ventas[0].cargo_venta_impuestos == Decimal("-20.25")
    assert resultado.ventas[1].total_informado_ml == Decimal("0")
    assert resultado.ventas[2].total_informado_ml == Decimal("-25")


def test_fila_informativa_sin_importes_conserva_trazabilidad_sin_inventar_valores():
    informativa = fila("44444444444444444444", "Informativa", None)
    for campo in ["Ingresos por productos (ARS)", "Cargo por venta e impuestos", "Unidades"]:
        informativa[campo] = None
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([informativa]))
    venta = resultado.ventas[0]
    assert venta.fila_origen == 4
    assert venta.unidades is None
    assert venta.ingresos_productos is None
    assert venta.total_informado_ml is None


def test_rechaza_xlsx_invalido_o_estructura_incorrecta():
    invalido = normalizar_ventas_mercado_libre("ventas.xlsx", b"no es xlsx")
    assert not invalido.ventas
    assert invalido.errores
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas AR"
    ws.append(["# de venta", "Fecha de venta", "Estado"])
    ws.append(["1", "2026-07-01", "Informativa"])
    salida = BytesIO()
    wb.save(salida)
    incorrecto = normalizar_ventas_mercado_libre("ventas.xlsx", salida.getvalue())
    assert not incorrecto.ventas
    assert incorrecto.errores


def test_modelo_publico_no_expone_campos_personales_en_asdict_ni_repr():
    nombres = {f.name for f in fields(VentaOficialMercadoLibre)}
    prohibidos = ["documento", "direccion", "domicilio", "comprador", "dni", "ciudad", "codigo_postal", "pais", "url", "seguimiento", "fiscal"]
    assert all(not any(p in nombre.lower() for p in prohibidos) for nombre in nombres)
    venta = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([fila()])).ventas[0]
    publico = str(asdict(venta)) + repr(venta)
    assert "comprador" not in publico.lower()
    assert "dni" not in publico.lower()
    assert "seguimiento" not in publico.lower()
