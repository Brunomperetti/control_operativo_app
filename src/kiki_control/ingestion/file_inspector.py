"""Inspección estructural de archivos recibidos."""

from csv import reader
from io import BytesIO, TextIOWrapper
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from kiki_control.adapters.contracts import CONTRATOS, ContratoColumnas
from kiki_control.domain.enums import SeveridadValidacion, TipoFuente
from kiki_control.domain.models import MetadatosArchivo, ResultadoInspeccion
from kiki_control.ingestion.metadata import calcular_sha256, fecha_actual_utc, obtener_extension
from kiki_control.validation.results import ProblemaValidacion

EXTENSIONES_SOPORTADAS = {".csv", ".xlsx"}
NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def inspeccionar_archivo(nombre_archivo: str, contenido: bytes) -> ResultadoInspeccion:
    """Inspecciona un archivo CSV o XLSX sin guardar contenido en disco."""

    extension = obtener_extension(nombre_archivo)
    hash_archivo = calcular_sha256(contenido)
    if not contenido:
        return _resultado_error_temprano(nombre_archivo, extension, contenido, hash_archivo, "ARCHIVO_VACIO", "El archivo recibido está vacío.")
    if extension not in EXTENSIONES_SOPORTADAS:
        return _resultado_error_temprano(nombre_archivo, extension, contenido, hash_archivo, "EXTENSION_NO_SOPORTADA", "La extensión del archivo no está soportada. Use CSV o XLSX.")

    errores: list[ProblemaValidacion] = []
    advertencias: list[ProblemaValidacion] = []
    try:
        columnas, filas, nombre_hoja, hojas_con_datos = _leer_estructura(extension, contenido)
    except Exception:
        return _resultado_error_temprano(nombre_archivo, extension, contenido, hash_archivo, "ARCHIVO_NO_LEGIBLE", "No se pudo leer el archivo con el formato indicado.")

    if extension == ".xlsx" and hojas_con_datos > 1:
        advertencias.append(_advertencia("VARIAS_HOJAS_CON_DATOS", "El archivo XLSX contiene más de una hoja con información; se inspeccionó la primera hoja no vacía."))

    fuente, contrato = _detectar_fuente(columnas)
    errores.extend(_validar_obligatorias(columnas, contrato))
    advertencias.extend(_advertir_adicionales(columnas, contrato))

    metadatos = MetadatosArchivo(nombre_archivo, extension, len(contenido), hash_archivo, fecha_actual_utc(), fuente, nombre_hoja, filas, columnas)
    return ResultadoInspeccion(metadatos, fuente, not errores and fuente != TipoFuente.DESCONOCIDA, tuple(errores), tuple(advertencias))


def _leer_estructura(extension: str, contenido: bytes) -> tuple[tuple[str, ...], int, str | None, int]:
    if extension == ".csv":
        texto = TextIOWrapper(BytesIO(contenido), encoding="utf-8-sig", newline="")
        filas = list(reader(texto))
        columnas = tuple(filas[0]) if filas else tuple()
        return columnas, max(len(filas) - 1, 0), None, 1
    return _leer_xlsx(contenido)


def _leer_xlsx(contenido: bytes) -> tuple[tuple[str, ...], int, str | None, int]:
    with ZipFile(BytesIO(contenido)) as archivo:
        compartidos = _leer_textos_compartidos(archivo)
        hojas = _listar_hojas(archivo)
        hojas_no_vacias: list[tuple[str, tuple[str, ...], int]] = []
        for nombre, ruta in hojas:
            columnas, filas = _leer_hoja(archivo, ruta, compartidos)
            if columnas or filas > 0:
                hojas_no_vacias.append((nombre, columnas, filas))
    if not hojas_no_vacias:
        return tuple(), 0, None, 0
    nombre, columnas, filas = hojas_no_vacias[0]
    return columnas, filas, nombre, len(hojas_no_vacias)


def _leer_textos_compartidos(archivo: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archivo.namelist():
        return []
    raiz = ET.fromstring(archivo.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//main:t", NS)) for si in raiz.findall("main:si", NS)]


def _listar_hojas(archivo: ZipFile) -> list[tuple[str, str]]:
    libro = ET.fromstring(archivo.read("xl/workbook.xml"))
    relaciones = ET.fromstring(archivo.read("xl/_rels/workbook.xml.rels"))
    rutas = {rel.attrib["Id"]: "xl/" + rel.attrib["Target"] for rel in relaciones}
    return [(hoja.attrib["name"], rutas[hoja.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]) for hoja in libro.findall("main:sheets/main:sheet", NS)]


def _leer_hoja(archivo: ZipFile, ruta: str, compartidos: list[str]) -> tuple[tuple[str, ...], int]:
    raiz = ET.fromstring(archivo.read(ruta))
    filas = raiz.findall(".//main:sheetData/main:row", NS)
    valores = [[_valor_celda(celda, compartidos) for celda in fila.findall("main:c", NS)] for fila in filas]
    valores_no_vacios = [fila for fila in valores if any(valor != "" for valor in fila)]
    if not valores_no_vacios:
        return tuple(), 0
    return tuple(valores_no_vacios[0]), max(len(valores_no_vacios) - 1, 0)


def _valor_celda(celda: ET.Element, compartidos: list[str]) -> str:
    valor = celda.find("main:v", NS)
    if valor is None or valor.text is None:
        texto_inline = celda.find("main:is/main:t", NS)
        return texto_inline.text if texto_inline is not None and texto_inline.text is not None else ""
    if celda.attrib.get("t") == "s":
        return compartidos[int(valor.text)]
    return valor.text


def _detectar_fuente(columnas: tuple[str, ...]) -> tuple[TipoFuente, ContratoColumnas | None]:
    columnas_set = set(columnas)
    coincidencias, contrato = max(((len(columnas_set & contrato.obligatorias), contrato) for contrato in CONTRATOS), key=lambda item: item[0])
    if coincidencias == 0:
        return TipoFuente.DESCONOCIDA, None
    return contrato.tipo_fuente, contrato


def _validar_obligatorias(columnas: tuple[str, ...], contrato: ContratoColumnas | None) -> list[ProblemaValidacion]:
    if contrato is None:
        return [ProblemaValidacion("FUENTE_DESCONOCIDA", "No se reconoció una firma suficiente de columnas para Mercado Libre o Mercado Pago.", SeveridadValidacion.ERROR)]
    return [ProblemaValidacion("COLUMNA_OBLIGATORIA_FALTANTE", "Falta una columna obligatoria para la fuente detectada.", SeveridadValidacion.ERROR, columna=columna) for columna in sorted(contrato.obligatorias - set(columnas))]


def _advertir_adicionales(columnas: tuple[str, ...], contrato: ContratoColumnas | None) -> list[ProblemaValidacion]:
    if contrato is None:
        return []
    adicionales = sorted(set(columnas) - contrato.conocidas)
    if not adicionales:
        return []
    return [_advertencia("COLUMNAS_ADICIONALES", "El archivo contiene columnas adicionales no conocidas; se conservaron como parte de los metadatos.", detalle=", ".join(adicionales))]


def _resultado_error_temprano(nombre_archivo: str, extension: str, contenido: bytes, hash_archivo: str, codigo: str, mensaje: str) -> ResultadoInspeccion:
    error = ProblemaValidacion(codigo, mensaje, SeveridadValidacion.ERROR)
    metadatos = MetadatosArchivo(nombre_archivo, extension, len(contenido), hash_archivo, fecha_actual_utc(), TipoFuente.DESCONOCIDA, None, 0, tuple())
    return ResultadoInspeccion(metadatos, TipoFuente.DESCONOCIDA, False, (error,), tuple())


def _advertencia(codigo: str, mensaje: str, detalle: str | None = None) -> ProblemaValidacion:
    return ProblemaValidacion(codigo, mensaje, SeveridadValidacion.ADVERTENCIA, detalle=detalle)
