"""Normalización del XLSX financiero de Mercado Pago."""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from kiki_control.adapters.column_aliases import canonizar_fila
from kiki_control.domain.enums import SeveridadValidacion, TipoFuente
from kiki_control.domain.financial_movement import DetalleImpuesto, MovimientoFinanciero, TipoOperacionFinanciera
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.normalization.values import ErrorNormalizacion, es_vacio, normalizar_decimal, normalizar_identificador, normalizar_timestamp
from kiki_control.validation.results import ProblemaValidacion

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

ZONA_HORARIA_PREDETERMINADA = "America/Argentina/Cordoba"

MAPEO_TIPOS = {
    "Pago aprobado": TipoOperacionFinanciera.PAGO_APROBADO,
    "Pago de envío": TipoOperacionFinanciera.PAGO_ENVIO,
    "Devolución de dinero": TipoOperacionFinanciera.DEVOLUCION_DINERO,
    "DISPUTE_SHIPPING": TipoOperacionFinanciera.DISPUTA_ENVIO,
    "Reclamo": TipoOperacionFinanciera.RECLAMO,
    "Devolución de envío": TipoOperacionFinanciera.DEVOLUCION_ENVIO,
    "PAYOUTS": TipoOperacionFinanciera.PAYOUT,
    "Cashback": TipoOperacionFinanciera.CASHBACK,
}


@dataclass(frozen=True)
class FilaRechazadaMercadoPago:
    numero_fila_origen: int
    errores: tuple[ProblemaValidacion, ...]


@dataclass(frozen=True)
class ResultadoNormalizacionMercadoPago:
    movimientos: tuple[MovimientoFinanciero, ...]
    filas_rechazadas: tuple[FilaRechazadaMercadoPago, ...]
    errores: tuple[ProblemaValidacion, ...]
    advertencias: tuple[ProblemaValidacion, ...]
    cantidad_total_recibida: int
    cantidad_normalizada: int
    cantidad_rechazada: int
    hash_importacion: str
    hoja_procesada: str | None


def normalizar_mercado_pago(nombre_archivo: str, contenido: bytes, zona_horaria: str = ZONA_HORARIA_PREDETERMINADA) -> ResultadoNormalizacionMercadoPago:
    inspeccion = inspeccionar_archivo(nombre_archivo, contenido)
    if inspeccion.fuente_detectada != TipoFuente.MERCADO_PAGO:
        error = ProblemaValidacion("FUENTE_NO_COMPATIBLE", "El adaptador de Mercado Pago solo procesa archivos detectados como Mercado Pago.", SeveridadValidacion.ERROR)
        return _resultado_vacio(error, inspeccion)
    if not inspeccion.es_valido:
        return ResultadoNormalizacionMercadoPago(tuple(), tuple(), inspeccion.errores, inspeccion.advertencias, inspeccion.metadatos.cantidad_filas, 0, inspeccion.metadatos.cantidad_filas, inspeccion.metadatos.sha256, inspeccion.metadatos.nombre_hoja)
    if inspeccion.metadatos.extension != ".xlsx":
        error = ProblemaValidacion("FORMATO_NO_COMPATIBLE", "La normalización financiera de Mercado Pago recibe XLSX en esta versión inicial.", SeveridadValidacion.ERROR)
        return _resultado_vacio(error, inspeccion)
    try:
        zona = ZoneInfo(zona_horaria)
    except ZoneInfoNotFoundError:
        error = ProblemaValidacion("ZONA_HORARIA_INVALIDA", "La zona horaria configurada no existe en zoneinfo.", SeveridadValidacion.ERROR)
        return _resultado_vacio(error, inspeccion)

    filas = _leer_filas(contenido, inspeccion.metadatos.nombre_hoja)
    movimientos: list[MovimientoFinanciero] = []
    rechazadas: list[FilaRechazadaMercadoPago] = []
    errores_globales: list[ProblemaValidacion] = []
    advertencias = list(inspeccion.advertencias)
    for numero, fila in filas:
        fila_canonica = canonizar_fila(fila, TipoFuente.MERCADO_PAGO)
        mov, errores, avisos = _normalizar_fila(fila_canonica, numero, inspeccion.metadatos.sha256, inspeccion.metadatos.nombre_hoja or "", zona)
        advertencias.extend(avisos)
        if errores:
            rechazadas.append(FilaRechazadaMercadoPago(numero, tuple(errores)))
            errores_globales.extend(errores)
        elif mov is not None:
            movimientos.append(mov)
    return ResultadoNormalizacionMercadoPago(tuple(movimientos), tuple(rechazadas), tuple(errores_globales), tuple(advertencias), len(filas), len(movimientos), len(rechazadas), inspeccion.metadatos.sha256, inspeccion.metadatos.nombre_hoja)


def _resultado_vacio(error: ProblemaValidacion, inspeccion: Any) -> ResultadoNormalizacionMercadoPago:
    return ResultadoNormalizacionMercadoPago(tuple(), tuple(), (error,), inspeccion.advertencias, 0, 0, 0, inspeccion.metadatos.sha256, inspeccion.metadatos.nombre_hoja)


def _leer_filas(contenido: bytes, hoja: str | None) -> list[tuple[int, dict[str, object]]]:
    with ZipFile(BytesIO(contenido)) as archivo:
        compartidos = _leer_textos_compartidos(archivo)
        ruta = _ruta_hoja(archivo, hoja)
        raiz = ET.fromstring(archivo.read(ruta))
    rows_xml = raiz.findall(".//main:sheetData/main:row", NS)
    filas = [[_valor_celda(celda, compartidos) for celda in row.findall("main:c", NS)] for row in rows_xml]
    filas = [fila for fila in filas if any(not es_vacio(v) for v in fila)]
    if not filas:
        return []
    columnas = [str(c or "") for c in filas[0]]
    return [(idx, dict(zip(columnas, row, strict=False))) for idx, row in enumerate(filas[1:], start=2) if any(not es_vacio(v) for v in row)]


def _leer_textos_compartidos(archivo: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archivo.namelist():
        return []
    raiz = ET.fromstring(archivo.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//main:t", NS)) for si in raiz.findall("main:si", NS)]


def _ruta_hoja(archivo: ZipFile, hoja: str | None) -> str:
    libro = ET.fromstring(archivo.read("xl/workbook.xml"))
    relaciones = ET.fromstring(archivo.read("xl/_rels/workbook.xml.rels"))
    rutas = {rel.attrib["Id"]: "xl/" + rel.attrib["Target"] for rel in relaciones}
    primera = ""
    for sheet in libro.findall("main:sheets/main:sheet", NS):
        ruta = rutas[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
        if not primera:
            primera = ruta
        if hoja is None or sheet.attrib["name"] == hoja:
            return ruta
    return primera


def _valor_celda(celda: ET.Element, compartidos: list[str]) -> str:
    valor = celda.find("main:v", NS)
    if valor is None or valor.text is None:
        texto_inline = celda.find("main:is/main:t", NS)
        return texto_inline.text if texto_inline is not None and texto_inline.text is not None else ""
    if celda.attrib.get("t") == "s":
        return compartidos[int(valor.text)]
    return valor.text


def _normalizar_fila(fila: dict[str, object], numero: int, hash_importacion: str, hoja: str, zona: ZoneInfo) -> tuple[MovimientoFinanciero | None, list[ProblemaValidacion], list[ProblemaValidacion]]:
    errores: list[ProblemaValidacion] = []
    avisos: list[ProblemaValidacion] = []
    def celda(c: str) -> object: return fila.get(c)
    id_mp = _id(celda("ID DE OPERACIÓN EN MERCADO PAGO"), "ID DE OPERACIÓN EN MERCADO PAGO", numero, errores)
    tipo_original = _texto(celda("TIPO DE OPERACIÓN"), "TIPO DE OPERACIÓN", numero, errores)
    tipo = MAPEO_TIPOS.get(tipo_original or "", TipoOperacionFinanciera.DESCONOCIDA)
    if tipo_original and tipo == TipoOperacionFinanciera.DESCONOCIDA:
        avisos.append(_problema("TIPO_OPERACION_DESCONOCIDO", "Tipo de operación desconocido; se conserva el texto original.", numero, "TIPO DE OPERACIÓN", SeveridadValidacion.ADVERTENCIA))
    id_orden = _id(celda("ID DE LA ORDEN"), "ID DE LA ORDEN", numero, errores, opcional=True)
    canal = _opcional(celda("CANAL DE VENTA"), "CANAL_VENTA_AUSENTE", numero, avisos, "CANAL DE VENTA")
    sku = _opcional(celda("CÓDIGO DE PRODUCTO SKU"), "SKU_AUSENTE", numero, avisos, "CÓDIGO DE PRODUCTO SKU")
    if id_orden is None:
        codigo = "ID_ORDEN_AUSENTE_ALTA_RELEVANCIA" if tipo == TipoOperacionFinanciera.PAGO_APROBADO and canal == "Mercado Libre" else "ID_ORDEN_AUSENTE"
        avisos.append(_problema(codigo, "ID de orden ausente; el movimiento se conserva sin agrupar ni rechazar.", numero, "ID DE LA ORDEN", SeveridadValidacion.ADVERTENCIA))
    fecha_o = _ts(celda("FECHA DE ORIGEN"), "FECHA DE ORIGEN", numero, errores, zona)
    fecha_a = _ts(celda("FECHA DE APROBACIÓN"), "FECHA DE APROBACIÓN", numero, errores, zona)
    fecha_l = _ts(celda("FECHA DE LIQUIDACIÓN DEL DINERO"), "FECHA DE LIQUIDACIÓN DEL DINERO", numero, errores, zona, opcional=True)
    if fecha_l[0] is None:
        avisos.append(_problema("FECHA_LIQUIDACION_AUSENTE", "Fecha de liquidación ausente.", numero, "FECHA DE LIQUIDACIÓN DEL DINERO", SeveridadValidacion.ADVERTENCIA))
    moneda = _texto(celda("MONEDA"), "MONEDA", numero, errores)
    importes = {campo: _dec(celda(campo), campo, numero, errores) for campo in ["VALOR DE LA COMPRA", "COMISIONES + IVA", "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO", "COMISIÓN DE MERCADO LIBRE + IVA", "COMISIÓN POR OFRECER CUOTAS SIN INTERÉS", "COSTO DE ENVÍO", "IMPUESTOS COBRADOS POR RETENCIONES DE IIBB", "CUPÓN DE DESCUENTO"]}
    monto_split = _dec(celda("MONTO RECIBIDO POR SPLIT"), "MONTO RECIBIDO POR SPLIT", numero, errores, opcional=True)
    monto_operacion = _dec(celda("MONTO NETO DE LA OPERACIÓN"), "MONTO NETO DE LA OPERACIÓN", numero, errores, opcional=True)
    impuestos_original, impuestos = _impuestos(celda("IMPUESTOS DESAGREGADOS"), numero, avisos)
    datos_extra_original, refund_id = _datos_extra(celda("DATOS EXTRA"), numero, avisos, tipo)
    tags = _json_original(celda("OPERATION_TAGS"), numero, avisos, "OPERATION_TAGS")
    if errores or not (id_mp and tipo_original and moneda and fecha_o[1] and fecha_o[2] and fecha_a[1] and fecha_a[2]) or any(v is None for v in importes.values()):
        return None, errores, avisos
    return MovimientoFinanciero(TipoFuente.MERCADO_PAGO.value, hash_importacion, numero, hoja, _id(celda("NÚMERO DE IDENTIFICACIÓN"), "NÚMERO DE IDENTIFICACIÓN", numero, errores, opcional=True), id_mp, id_orden, _id(celda("ID DE ENVÍO"), "ID DE ENVÍO", numero, errores, opcional=True), _id(celda("ID DE PAQUETE"), "ID DE PAQUETE", numero, errores, opcional=True), _id(celda("ID DE INTENTO DE OPERACIÓN"), "ID DE INTENTO DE OPERACIÓN", numero, errores, opcional=True), sku, refund_id, tipo, tipo_original, canal, _opcional(celda("PLATAFORMA DE COBRO"), "CAMPO_OPCIONAL_VACIO", numero, avisos, "PLATAFORMA DE COBRO", avisar=False), _opcional(celda("TIPO DE MEDIO DE PAGO"), "CAMPO_OPCIONAL_VACIO", numero, avisos, "TIPO DE MEDIO DE PAGO", avisar=False), _opcional(celda("MEDIO DE PAGO"), "CAMPO_OPCIONAL_VACIO", numero, avisos, "MEDIO DE PAGO", avisar=False), _opcional(celda("MODO DE ENVÍO"), "CAMPO_OPCIONAL_VACIO", numero, avisos, "MODO DE ENVÍO", avisar=False), importes["VALOR DE LA COMPRA"], monto_split, importes["COMISIONES + IVA"], importes["MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO"], monto_operacion, importes["CUPÓN DE DESCUENTO"], importes["COMISIÓN DE MERCADO LIBRE + IVA"], importes["COMISIÓN POR OFRECER CUOTAS SIN INTERÉS"], importes["COSTO DE ENVÍO"], importes["IMPUESTOS COBRADOS POR RETENCIONES DE IIBB"], moneda, _opcional(celda("MONEDA DE LIQUIDACIÓN"), "CAMPO_OPCIONAL_VACIO", numero, avisos, "MONEDA DE LIQUIDACIÓN", avisar=False), fecha_o[0] or "", fecha_o[1], fecha_o[2], fecha_a[0] or "", fecha_a[1], fecha_a[2], fecha_l[0], fecha_l[1], fecha_l[2], impuestos_original, impuestos, datos_extra_original, tags), errores, avisos


def _id(v: object, campo: str, n: int, errores: list[ProblemaValidacion], opcional: bool=False) -> str | None:
    try: return normalizar_identificador(v, campo=campo, opcional=opcional)
    except ErrorNormalizacion as exc: errores.append(_problema("IDENTIFICADOR_INVALIDO", str(exc), n, campo)); return None

def _dec(v: object, campo: str, n: int, errores: list[ProblemaValidacion], opcional: bool=False):
    try: return normalizar_decimal(v, campo=campo, opcional=opcional)
    except ErrorNormalizacion as exc: errores.append(_problema("IMPORTE_INVALIDO", str(exc), n, campo)); return None

def _ts(v: object, campo: str, n: int, errores: list[ProblemaValidacion], zona: ZoneInfo, opcional: bool=False):
    try: return normalizar_timestamp(v, campo=campo, zona=zona, opcional=opcional)
    except ErrorNormalizacion as exc: errores.append(_problema("FECHA_INVALIDA", str(exc), n, campo)); return (None, None, None)

def _texto(v: object, campo: str, n: int, errores: list[ProblemaValidacion]) -> str | None:
    if es_vacio(v): errores.append(_problema("CAMPO_OBLIGATORIO_VACIO", f"El campo {campo} está vacío.", n, campo)); return None
    return str(v).strip()

def _opcional(v: object, codigo: str, n: int, avisos: list[ProblemaValidacion], campo: str, avisar: bool=True) -> str | None:
    if es_vacio(v):
        if avisar: avisos.append(_problema(codigo, "Campo opcional vacío.", n, campo, SeveridadValidacion.ADVERTENCIA))
        return None
    return str(v).strip()

def _json_original(v: object, n: int, avisos: list[ProblemaValidacion], campo: str) -> str | None:
    if es_vacio(v): return None
    texto = str(v).strip()
    try: json.loads(texto)
    except json.JSONDecodeError: avisos.append(_problema("JSON_COMPLEMENTARIO_INVALIDO", f"JSON inválido en {campo}; se conserva el texto original.", n, campo, SeveridadValidacion.ADVERTENCIA))
    return texto

def _impuestos(v: object, n: int, avisos: list[ProblemaValidacion]) -> tuple[str | None, tuple[DetalleImpuesto, ...]]:
    texto = _json_original(v, n, avisos, "IMPUESTOS DESAGREGADOS")
    if texto is None: return None, tuple()
    try: data = json.loads(texto)
    except json.JSONDecodeError: return texto, tuple()
    if not isinstance(data, list):
        avisos.append(_problema("JSON_COMPLEMENTARIO_INVALIDO", "IMPUESTOS DESAGREGADOS debe ser una lista JSON.", n, "IMPUESTOS DESAGREGADOS", SeveridadValidacion.ADVERTENCIA)); return texto, tuple()
    detalles = []
    for item in data:
        if isinstance(item, dict):
            try: importe = normalizar_decimal(item.get("amount"), campo="amount")
            except ErrorNormalizacion:
                avisos.append(_problema("JSON_COMPLEMENTARIO_INVALIDO", "Importe inválido en impuesto desagregado.", n, "IMPUESTOS DESAGREGADOS", SeveridadValidacion.ADVERTENCIA)); continue
            detalles.append(DetalleImpuesto(_maybe_text(item.get("financial_entity")), _maybe_text(item.get("detail")), importe))
    return texto, tuple(detalles)

def _datos_extra(v: object, n: int, avisos: list[ProblemaValidacion], tipo: TipoOperacionFinanciera) -> tuple[str | None, str | None]:
    texto = _json_original(v, n, avisos, "DATOS EXTRA")
    if texto is None:
        return None, None
    try: data = json.loads(texto)
    except json.JSONDecodeError: return texto, None
    refund = _buscar_refund(data)
    if refund is None and tipo in {TipoOperacionFinanciera.DEVOLUCION_DINERO, TipoOperacionFinanciera.DEVOLUCION_ENVIO}:
        avisos.append(_problema("REFUND_ID_NO_DISPONIBLE", "Refund ID no disponible para devolución.", n, "DATOS EXTRA", SeveridadValidacion.ADVERTENCIA))
    return texto, refund

def _buscar_refund(data: object) -> str | None:
    if isinstance(data, dict):
        if "refund_id" in data: return normalizar_identificador(data["refund_id"], campo="refund_id", opcional=True)
        for v in data.values():
            r = _buscar_refund(v)
            if r is not None: return r
    if isinstance(data, list):
        for v in data:
            r = _buscar_refund(v)
            if r is not None: return r
    return None

def _maybe_text(v: object) -> str | None:
    return None if es_vacio(v) else str(v)

def _problema(codigo: str, mensaje: str, numero: int, columna: str | None = None, severidad: SeveridadValidacion = SeveridadValidacion.ERROR) -> ProblemaValidacion:
    return ProblemaValidacion(codigo, mensaje, severidad, columna=columna, fila=numero)
