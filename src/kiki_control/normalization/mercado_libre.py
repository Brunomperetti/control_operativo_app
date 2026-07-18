"""Normalización del CSV comercial de Mercado Libre."""

from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from re import search
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.enums import SeveridadValidacion, TipoFuente
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.normalization.locale_ar import ErrorNormalizacion, parsear_importe, parsear_porcentaje
from kiki_control.validation.results import ProblemaValidacion

ZONA_HORARIA_PREDETERMINADA = "America/Argentina/Cordoba"


@dataclass(frozen=True)
class FilaRechazada:
    numero_fila_origen: int
    datos: dict[str, str]
    errores: tuple[ProblemaValidacion, ...]


@dataclass(frozen=True)
class ResultadoNormalizacion:
    operaciones: tuple[OperacionComercial, ...]
    filas_rechazadas: tuple[FilaRechazada, ...]
    errores: tuple[ProblemaValidacion, ...]
    advertencias: tuple[ProblemaValidacion, ...]
    cantidad_total_recibida: int
    cantidad_normalizada: int
    cantidad_rechazada: int
    hash_importacion: str


def normalizar_mercado_libre(nombre_archivo: str, contenido: bytes, zona_horaria: str = ZONA_HORARIA_PREDETERMINADA) -> ResultadoNormalizacion:
    """Normaliza un CSV comercial de Mercado Libre validado por el inspector."""

    inspeccion = inspeccionar_archivo(nombre_archivo, contenido)
    if inspeccion.fuente_detectada != TipoFuente.MERCADO_LIBRE:
        error = ProblemaValidacion("FUENTE_NO_COMPATIBLE", "El adaptador de Mercado Libre solo procesa archivos detectados como Mercado Libre.", SeveridadValidacion.ERROR)
        return ResultadoNormalizacion(tuple(), tuple(), (error,), inspeccion.advertencias, 0, 0, 0, inspeccion.metadatos.sha256)
    if not inspeccion.es_valido:
        return ResultadoNormalizacion(tuple(), tuple(), inspeccion.errores, inspeccion.advertencias, inspeccion.metadatos.cantidad_filas, 0, inspeccion.metadatos.cantidad_filas, inspeccion.metadatos.sha256)
    if inspeccion.metadatos.extension != ".csv":
        error = ProblemaValidacion("FORMATO_NO_COMPATIBLE", "La normalización comercial de Mercado Libre recibe CSV en esta versión inicial.", SeveridadValidacion.ERROR)
        return ResultadoNormalizacion(tuple(), tuple(), (error,), inspeccion.advertencias, inspeccion.metadatos.cantidad_filas, 0, inspeccion.metadatos.cantidad_filas, inspeccion.metadatos.sha256)

    try:
        zona = ZoneInfo(zona_horaria)
    except ZoneInfoNotFoundError:
        error = ProblemaValidacion("ZONA_HORARIA_INVALIDA", "La zona horaria configurada no existe en zoneinfo.", SeveridadValidacion.ERROR)
        return ResultadoNormalizacion(tuple(), tuple(), (error,), inspeccion.advertencias, inspeccion.metadatos.cantidad_filas, 0, inspeccion.metadatos.cantidad_filas, inspeccion.metadatos.sha256)

    texto = contenido.decode("utf-8-sig")
    filas = list(DictReader(StringIO(texto)))
    operaciones: list[OperacionComercial] = []
    rechazadas: list[FilaRechazada] = []
    errores_globales: list[ProblemaValidacion] = []
    advertencias = list(inspeccion.advertencias)
    for indice, fila in enumerate(filas, start=2):
        operacion, errores, avisos = _normalizar_fila(fila, indice, inspeccion.metadatos.sha256, zona)
        advertencias.extend(avisos)
        if errores:
            rechazadas.append(FilaRechazada(indice, dict(fila), tuple(errores)))
            errores_globales.extend(errores)
        elif operacion is not None:
            operaciones.append(operacion)
    return ResultadoNormalizacion(tuple(operaciones), tuple(rechazadas), tuple(errores_globales), tuple(advertencias), len(filas), len(operaciones), len(rechazadas), inspeccion.metadatos.sha256)


def _normalizar_fila(fila: dict[str, str], numero: int, hash_importacion: str, zona: ZoneInfo) -> tuple[OperacionComercial | None, list[ProblemaValidacion], list[ProblemaValidacion]]:
    errores: list[ProblemaValidacion] = []
    avisos: list[ProblemaValidacion] = []

    def celda(nombre: str) -> str:
        return (fila.get(nombre) or "").strip()

    id_orden = celda("ID Order")
    if not id_orden:
        errores.append(_problema("ID_ORDER_AUSENTE", "ID Order ausente.", numero))
    id_carrito = _opcional_texto(celda("ID Carrito"), "ID_CARRITO_VACIO", "ID Carrito vacío.", numero, avisos)
    sku = _opcional_texto(celda("Sku"), "SKU_VACIO", "SKU vacío.", numero, avisos)
    cantidad = _cantidad(celda("Cantidad"), numero, errores)
    fecha_hora = _fecha_hora(celda("Fecha de venta"), celda("Hora"), zona, numero, errores)
    params = _parametros(celda("Parámetros cálculo"), numero, avisos)

    monto_venta = _monto_requerido(fila, "Monto de venta ($)", numero, errores)
    costo_total = _monto_requerido(fila, "Costo Total (Con IVA) ($)", numero, errores)
    monto_neto = _monto_requerido(fila, "Monto neto (en MP) ($)", numero, errores)
    utilidad = _monto_requerido(fila, "Utilidades netas ($)", numero, errores)
    precio_unitario = _monto_opcional(fila, "Precio unitario ($)", numero, errores)
    costo_unitario = _monto_opcional(fila, "Costo Unitario (Con IVA) ($)", numero, errores)
    comision_meli = _monto_opcional(fila, "Comisión MeLi  ($)", numero, errores)
    costo_envio_bruto = _monto_opcional(fila, "Costo de envío (Bruto) ($)", numero, errores)
    costo_envio_vendedor = _monto_opcional(fila, "Costo de envío (Seller) ($)", numero, errores)
    costo_envio_prorrateado = _monto_opcional(fila, "Costo de envío prorrateado ($)", numero, errores)
    bonificacion_envio = _monto_opcional(fila, "Bonificación envío ($)", numero, errores)
    impuestos_comisiones = _monto_opcional(fila, "Impuestos y comisiones ($)", numero, errores)
    precio_equilibrio = _precio_equilibrio(fila, numero, errores, avisos)
    tasa_iva = _porcentaje_opcional(fila, "IVA", numero, errores)
    rentabilidad_precio_venta = _porcentaje_opcional(fila, "Rentabilidad s/ precio venta", numero, errores)
    rentabilidad_costo_producto = _porcentaje_opcional(fila, "Rentabilidad s/ costo producto", numero, errores)
    rentabilidad_suma_costos = _porcentaje_opcional(fila, "Rentabilidad s/ suma costos", numero, errores)
    tasa_comision_meli = _porcentaje_opcional(fila, "% Comisión MeLi", numero, errores)
    tasa_costo_envio = _porcentaje_opcional(fila, "% Costo de envío", numero, errores)

    if errores or cantidad is None or fecha_hora is None or monto_venta is None or costo_total is None or monto_neto is None or utilidad is None:
        return None, errores, avisos

    return OperacionComercial(
        fuente=TipoFuente.MERCADO_LIBRE.value, hash_importacion=hash_importacion, numero_fila_origen=numero,
        id_orden=id_orden, id_carrito=id_carrito, sku=sku, fecha_venta_original=celda("Fecha de venta"), hora_venta_original=celda("Hora"), fecha_hora_venta=fecha_hora,
        producto=celda("Producto"), tipo_envio=_opcional_texto(celda("Tipo de envío"), "CAMPO_OPCIONAL_VACIO", "Campo opcional vacío.", numero, avisos, avisar=False), provincia=_opcional_texto(celda("Provincia"), "CAMPO_OPCIONAL_VACIO", "Campo opcional vacío.", numero, avisos, avisar=False), cantidad=cantidad,
        precio_unitario=precio_unitario, monto_venta=monto_venta, costo_unitario_con_iva=costo_unitario, costo_total_con_iva=costo_total,
        comision_mercado_libre_informada=comision_meli, costo_envio_bruto=costo_envio_bruto, costo_envio_vendedor=costo_envio_vendedor, costo_envio_prorrateado=costo_envio_prorrateado, bonificacion_envio=bonificacion_envio, monto_neto_mercado_pago_informado=monto_neto, impuestos_y_comisiones_informados=impuestos_comisiones, utilidad_neta_informada=utilidad, precio_equilibrio=precio_equilibrio,
        tasa_iva=tasa_iva, rentabilidad_precio_venta=rentabilidad_precio_venta, rentabilidad_costo_producto=rentabilidad_costo_producto, rentabilidad_suma_costos=rentabilidad_suma_costos, tasa_comision_mercado_libre=tasa_comision_meli, tasa_costo_envio=tasa_costo_envio,
        parametros_calculo_original=celda("Parámetros cálculo"), costo_incluye_alicuota=params[0], precio_incluye_alicuota=params[1], tasa_iibb_configurada=params[2]
    ), errores, avisos


def _monto_requerido(fila: dict[str, str], campo: str, numero: int, errores: list[ProblemaValidacion]) -> Decimal | None:
    try: return parsear_importe(fila.get(campo, ""), campo=campo)
    except ErrorNormalizacion as exc: errores.append(_problema("IMPORTE_INVALIDO", str(exc), numero, campo)); return None

def _monto_opcional(fila: dict[str, str], campo: str, numero: int, errores: list[ProblemaValidacion]) -> Decimal | None:
    try: return parsear_importe(fila.get(campo, ""), campo=campo, opcional=True)
    except ErrorNormalizacion as exc: errores.append(_problema("IMPORTE_INVALIDO", str(exc), numero, campo)); return None

def _porcentaje_opcional(fila: dict[str, str], campo: str, numero: int, errores: list[ProblemaValidacion]) -> Decimal | None:
    try: return parsear_porcentaje(fila.get(campo, ""), campo=campo, opcional=True)
    except ErrorNormalizacion as exc: errores.append(_problema("PORCENTAJE_INVALIDO", str(exc), numero, campo)); return None

def _cantidad(valor: str, numero: int, errores: list[ProblemaValidacion]) -> int | None:
    try: cantidad = int(valor)
    except ValueError: errores.append(_problema("CANTIDAD_INVALIDA", "Cantidad ausente o no entera.", numero, "Cantidad")); return None
    if cantidad < 1:
        errores.append(_problema("CANTIDAD_INVALIDA", "Cantidad menor que 1.", numero, "Cantidad")); return None
    return cantidad

def _fecha_hora(fecha: str, hora: str, zona: ZoneInfo, numero: int, errores: list[ProblemaValidacion]) -> datetime | None:
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(f"{fecha} {hora}", formato).replace(tzinfo=zona)
        except ValueError: pass
    errores.append(_problema("FECHA_HORA_INVALIDA", "Fecha u hora inválida.", numero)); return None

def _parametros(valor: str, numero: int, avisos: list[ProblemaValidacion]) -> tuple[bool | None, bool | None, Decimal | None]:
    costo = _si_no(search(r"Costo inc\. alíc\.:\s*(Sí|Si|No)", valor, flags=0))
    precio = _si_no(search(r"Precio inc\. alíc\.:\s*(Sí|Si|No)", valor, flags=0))
    iibb_match = search(r"IIBB:\s*[-+]?\d+(?:[.,]\d+)?\s*\(([-+]?\d+(?:[.,]\d+)?)%\)", valor)
    tasa = None
    if iibb_match:
        try: tasa = Decimal(iibb_match.group(1).replace(",", ".")) / Decimal("100")
        except InvalidOperation: tasa = None
    if valor and (costo is None or precio is None or tasa is None):
        avisos.append(_problema("PARAMETROS_CALCULO_NO_RECONOCIDOS", "Parámetros de cálculo con formato no reconocido; se conserva el texto original.", numero, "Parámetros cálculo", SeveridadValidacion.ADVERTENCIA))
    return costo, precio, tasa

def _si_no(match: object) -> bool | None:
    if not match: return None
    valor = match.group(1)  # type: ignore[attr-defined]
    return valor in {"Sí", "Si"}

def _precio_equilibrio(fila: dict[str, str], numero: int, errores: list[ProblemaValidacion], avisos: list[ProblemaValidacion]) -> Decimal | None:
    if not (fila.get("Precio de equilibrio ($)") or "").strip():
        avisos.append(_problema("PRECIO_EQUILIBRIO_VACIO", "Precio de equilibrio vacío.", numero, "Precio de equilibrio ($)", SeveridadValidacion.ADVERTENCIA))
    return _monto_opcional(fila, "Precio de equilibrio ($)", numero, errores)

def _opcional_texto(valor: str, codigo: str, mensaje: str, numero: int, avisos: list[ProblemaValidacion], *, avisar: bool = True) -> str | None:
    if valor: return valor
    if avisar: avisos.append(_problema(codigo, mensaje, numero, severidad=SeveridadValidacion.ADVERTENCIA))
    return None

def _problema(codigo: str, mensaje: str, numero: int, columna: str | None = None, severidad: SeveridadValidacion = SeveridadValidacion.ERROR) -> ProblemaValidacion:
    return ProblemaValidacion(codigo, mensaje, severidad, columna=columna, fila=numero)
