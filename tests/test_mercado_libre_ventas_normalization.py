from dataclasses import asdict, fields
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from kiki_control.adapters.contracts import COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS
from kiki_control.adapters.mercado_libre_ventas import normalizar_ventas_mercado_libre
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from tests.test_reconciliation_engine import mov, op, único
from kiki_control.reconciliation import reconciliar
from kiki_control.domain.reconciliation import EstadoConciliacion, MotivoConciliacion



def _desambiguar(encabezados):
    vistos = {}
    resultado = []
    for encabezado in encabezados:
        cantidad = vistos.get(encabezado, 0)
        resultado.append(encabezado if cantidad == 0 else f"{encabezado}.{cantidad}")
        vistos[encabezado] = cantidad + 1
    return tuple(resultado)


COLUMNAS_DESAMBIGUADAS = _desambiguar(COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS)

PII_SENTINELS = (
    "PII_DATOS_PERSONALES_EMPRESA_SENTINELA",
    "PII_TIPO_NUMERO_DOCUMENTO_SENTINELA",
    "PII_DIRECCION_SENTINELA",
    "PII_CONDICION_FISCAL_SENTINELA",
    "PII_NUMERO_IIBB_SENTINELA",
    "PII_COMPRADOR_SENTINELA",
    "PII_NEGOCIO_SENTINELA",
    "PII_DNI_SENTINELA",
    "PII_DOMICILIO_SENTINELA",
    "PII_CIUDAD_SENTINELA",
    "PII_ESTADO_GEOGRAFICO_SENTINELA",
    "PII_CODIGO_POSTAL_SENTINELA",
    "PII_PAIS_SENTINELA",
    "PII_SEGUIMIENTO_SENTINELA",
    "https://pii-seguimiento.example.invalid/sentinel",
)


def xlsx_ventas(filas, hoja="Ventas AR", intro=True):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    if intro:
        ws.append(["Reporte sintético sin datos reales"])
        ws.append(["Fila introductoria sintética"])
    ws.append(list(COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS))
    for fila in filas:
        ws.append([fila.get(c) for c in COLUMNAS_DESAMBIGUADAS])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def fila(id_venta="12345678901234567890", estado="Entregado", total="100.50"):
    valores = {columna: None for columna in COLUMNAS_DESAMBIGUADAS}
    valores.update(
        {
            "# de venta": id_venta,
            "Fecha de venta": "2026-07-01 10:30:00",
            "Estado": estado,
            "Descripción del estado": "Estado operativo sintético",
            "Paquete de varios productos": "No",
            "Pertenece a un kit": "Sí",
            "Unidades": 1,
            "Unidades.1": 99,
            "Unidades.2": 88,
            "Ingresos por productos (ARS)": "150.75",
            "Cargo por venta e impuestos (ARS)": "-20.25",
            "Ingresos por envío (ARS)": "0",
            "Costos de envío (ARS)": "-10",
            "Costo de envío basado en medidas y peso declarados": "12.34",
            "Cargo por diferencias en medidas y peso del paquete": "-1.23",
            "Descuentos y bonificaciones": "-20",
            "Anulaciones y reembolsos (ARS)": "-5.50",
            "Total (ARS)": total,
            "SKU": "SKU-SINTETICO-0001",
            "# de publicación": "98765432109876543210",
            "Canal de venta": "Mercado Libre",
            "Título de la publicación": "Producto sintético",
            "Variante": "Variante sintética",
            "Precio unitario de venta de la publicación (ARS)": "150.75",
            "Forma de entrega": "Entrega comercial sintética",
            "Forma de entrega.1": "Entrega logística que no debe sobrescribir",
            "Estado.1": PII_SENTINELS[10],
            "Fecha en camino": "2026-07-01",
            "Fecha en camino.1": "2026-07-02",
            "Fecha entregado": "2026-07-03",
            "Fecha entregado.1": "2026-07-04",
            "Transportista": "Transportista operativo sintético",
            "Transportista.1": "Transportista duplicado sintético",
            "Reclamo abierto": "Sí",
            "Reclamo cerrado": "No",
            "Con mediación": "Sí",
            "Datos personales o de empresa": PII_SENTINELS[0],
            "Tipo y número de documento": PII_SENTINELS[1],
            "Dirección": PII_SENTINELS[2],
            "Condición fiscal (IVA)": PII_SENTINELS[3],
            "Número IIBB": PII_SENTINELS[4],
            "Comprador": PII_SENTINELS[5],
            "Negocio": PII_SENTINELS[6],
            "DNI": PII_SENTINELS[7],
            "Domicilio": PII_SENTINELS[8],
            "Ciudad": PII_SENTINELS[9],
            "Código postal": PII_SENTINELS[11],
            "País": PII_SENTINELS[12],
            "Número de seguimiento": PII_SENTINELS[13],
            "Número de seguimiento.1": PII_SENTINELS[13],
            "URL de seguimiento": PII_SENTINELS[14],
            "URL de seguimiento.1": PII_SENTINELS[14],
        }
    )
    return valores


def test_fixture_usa_las_64_columnas_reales_confirmadas_y_desambiguacion_logistica():
    assert len(COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS) == 64
    assert COLUMNAS_DESAMBIGUADAS[2] == "Estado"
    assert COLUMNAS_DESAMBIGUADAS[38] == "Estado.1"
    assert [c for c in COLUMNAS_DESAMBIGUADAS if c.startswith("Unidades")] == ["Unidades", "Unidades.1", "Unidades.2"]
    assert [c for c in COLUMNAS_DESAMBIGUADAS if c.startswith("Forma de entrega")] == ["Forma de entrega", "Forma de entrega.1"]
    assert [c for c in COLUMNAS_DESAMBIGUADAS if c.startswith("Número de seguimiento")] == ["Número de seguimiento", "Número de seguimiento.1"]
    assert [c for c in COLUMNAS_DESAMBIGUADAS if c.startswith("URL de seguimiento")] == ["URL de seguimiento", "URL de seguimiento.1"]


def test_detecta_mercado_libre_ventas_sin_columnas_adicionales_y_metadatos():
    contenido = xlsx_ventas([fila()])
    inspeccion = inspeccionar_archivo("nombre_irrelevante.bin.xlsx", contenido)
    assert inspeccion.es_valido
    assert inspeccion.fuente_detectada == TipoFuente.MERCADO_LIBRE_VENTAS
    assert inspeccion.metadatos.nombre_hoja == "Ventas AR"
    assert inspeccion.metadatos.cantidad_filas == 1
    assert inspeccion.metadatos.columnas_encontradas == COLUMNAS_MERCADO_LIBRE_VENTAS_CONFIRMADAS
    assert not any(a.codigo == "COLUMNAS_ADICIONALES" for a in inspeccion.advertencias)

    resultado = normalizar_ventas_mercado_libre("otro_nombre.xlsx", contenido)
    venta = resultado.ventas[0]
    assert resultado.hash_importacion == inspeccion.metadatos.sha256
    assert resultado.hoja_procesada == "Ventas AR"
    assert venta.fila_origen == 4
    assert venta.hash_importacion == inspeccion.metadatos.sha256


def test_lee_encabezados_exactos_importes_y_no_sobrescribe_duplicados():
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([fila()]))
    venta = resultado.ventas[0]
    assert venta.estado == "Entregado"
    assert venta.unidades == 1
    assert venta.forma_entrega == "Entrega comercial sintética"
    assert venta.cargo_venta_impuestos == Decimal("-20.25")
    assert venta.costo_envio_declarado == Decimal("12.34")
    assert venta.cargo_diferencias_envio == Decimal("-1.23")
    assert venta.anulaciones_reembolsos == Decimal("-5.50")
    assert venta.precio_unitario == Decimal("150.75")
    assert venta.ingresos_envio == Decimal("0")
    assert venta.id_venta == "12345678901234567890"
    assert venta.id_publicacion == "98765432109876543210"


def test_interpreta_reclamos_desde_tres_columnas_operativas():
    base = fila()
    base["Reclamo abierto"] = "No"
    base["Reclamo cerrado"] = "Sí"
    base["Con mediación"] = "No"
    venta = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([base])).ventas[0]
    assert venta.reclamo_abierto is False
    assert venta.reclamo_cerrado is True
    assert venta.con_mediacion is False


def test_importes_fechas_e_identificadores_no_vacios_invalidos_generan_validacion_sin_valor_crudo():
    invalida = fila()
    invalida["Cargo por venta e impuestos (ARS)"] = "IMPORTE_INVALIDO_SENTINELA"
    invalida["Fecha de venta"] = "FECHA_INVALIDA_SENTINELA"
    invalida["# de publicación"] = "123.45"
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([invalida]))
    assert not resultado.ventas
    assert {e.codigo for e in resultado.errores} >= {"IMPORTE_INVALIDO", "FECHA_INVALIDA", "IDENTIFICADOR_INVALIDO"}
    assert {e.columna for e in resultado.errores} >= {"Cargo por venta e impuestos (ARS)", "Fecha de venta", "# de publicación"}
    texto_problemas = repr(resultado.errores) + repr(resultado.advertencias)
    assert "IMPORTE_INVALIDO_SENTINELA" not in texto_problemas
    assert "FECHA_INVALIDA_SENTINELA" not in texto_problemas


def test_ventas_normales_canceladas_devueltas_e_informativas_se_conservan_sin_inventar_valores():
    informativa = fila("44444444444444444444", "Informativa", None)
    for campo in ["Ingresos por productos (ARS)", "Cargo por venta e impuestos (ARS)", "Unidades"]:
        informativa[campo] = None
    contenido = xlsx_ventas([
        fila(),
        fila("22222222222222222222", "Cancelada", "0"),
        fila("33333333333333333333", "Devuelta", "-25"),
        informativa,
    ])
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", contenido)
    assert resultado.cantidad_normalizada == 4
    assert [v.estado for v in resultado.ventas] == ["Entregado", "Cancelada", "Devuelta", "Informativa"]
    assert resultado.ventas[1].total_informado_ml == Decimal("0")
    assert resultado.ventas[2].total_informado_ml == Decimal("-25")
    assert resultado.ventas[3].unidades is None
    assert resultado.ventas[3].ingresos_productos is None
    assert resultado.ventas[3].total_informado_ml is None


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


def test_sentinelas_personales_no_aparecen_en_modelo_asdict_repr_errores_ni_advertencias():
    nombres = {f.name for f in fields(VentaOficialMercadoLibre)}
    prohibidos = ["documento", "direccion", "domicilio", "comprador", "dni", "ciudad", "codigo_postal", "pais", "url", "seguimiento", "fiscal", "negocio", "iibb"]
    assert all(not any(p in nombre.lower() for p in prohibidos) for nombre in nombres)
    resultado = normalizar_ventas_mercado_libre("ventas.xlsx", xlsx_ventas([fila()]))
    venta = resultado.ventas[0]
    publico = str(asdict(venta)) + repr(venta) + repr(resultado.errores) + repr(resultado.advertencias)
    for sentinel in PII_SENTINELS:
        assert sentinel not in publico


def test_conciliacion_existente_conserva_comportamiento():
    r = único(reconciliar([op(hash_="hash-c", fila=7)], [mov(hash_="hash-f", fila=8)]))
    assert r.estado == EstadoConciliacion.CONCILIADA
    assert r.motivos == (MotivoConciliacion.COINCIDENCIA_NETA_EXACTA,)
    assert r.diferencia_control == Decimal("0")
    assert r.hashes_importacion_comercial == ("hash-c",)
    assert r.hashes_importacion_financiera == ("hash-f",)
    assert r.numeros_fila_comercial == (7,)
    assert r.numeros_fila_financiera == (8,)
