"""Generación pura en memoria de reportes Excel auditables."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Literal
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from kiki_control.domain.reconciliation import ReporteConciliacion, ResultadoConciliacion
from kiki_control.presentation.review_cases import caso_a_fila, clasificar_revisiones
from kiki_control.presentation.reconciliation_view import (
    CoberturaArchivosPresentacion,
    clave_resultado,
    conclusion_ejecutiva,
    es_excepcion_o_caso_especial,
    etiqueta_estado,
    resumen_kpis_tipado,
)

TIPO_COMPLETO = "Reporte completo"
TIPO_EXCEPCIONES = "Solo excepciones"
TIPO_REVISIONES = "Revisiones pendientes"
ACLARACION_UTILIDAD = "La utilidad es informada por Mercado Libre y no representa resultado contable definitivo."
ACLARACION_FONDOS = "Los movimientos de fondos se informan separados y no se consideran pérdidas comerciales."
ACLARACION_PRIVACIDAD = "El archivo se generó en memoria y excluye datos personales, metadatos sensibles, contenido crudo y nombres de archivos originales."
COLUMNAS_OPERACIONES = (
    "ID de orden",
    "Estado",
    "Neto informado ML",
    "Neto aprobado MP",
    "Diferencia",
    "Neto financiero total",
    "Utilidad informada ML",
    "Pago dividido",
    "Devolución",
    "Reclamo o disputa",
    "Pendiente de acreditación",
    "Requiere revisión",
    "Explicación",
    "Motivos técnicos",
    "Filas ML de origen",
    "Filas MP de origen",
    "Cantidad de pagos aprobados",
    "Cantidad de movimientos financieros",
    "Versión de regla",
    "Tolerancia aplicada",
)
_COLUMNAS_MONETARIAS = {"Neto informado ML", "Neto aprobado MP", "Diferencia", "Neto financiero total", "Utilidad informada ML", "Tolerancia aplicada"}
_KPIS_MONETARIOS = {"Utilidad informada ML", "Neto ML comparable", "Neto MP comparable", "Diferencia comparable", "Neto MP fuera del archivo ML"}
_CAMPOS_ENTEROS_RESUMEN = {"Movimientos sin fecha de liquidación", "Cantidad de filas incluidas en Todas las operaciones", "Cantidad de filas incluidas en Excepciones"}
_COLUMNAS_WRAP = {"Explicación", "Motivos técnicos"}
_FORMATO_MONEDA_ARS = '[$$-es-AR] #,##0.00;[Red]-[$$-es-AR] #,##0.00;[$$-es-AR] 0.00'
_FORMATO_FECHA = "dd/mm/yyyy hh:mm:ss"
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def generar_reporte_completo_excel(reporte: ReporteConciliacion, cobertura: CoberturaArchivosPresentacion | None, zona_horaria: str) -> bytes:
    """Devuelve bytes XLSX del reporte completo, sin escribir archivos."""

    resultados = _resultados_ordenados(reporte.resultados)
    excepciones = [r for r in resultados if es_excepcion_o_caso_especial(r)]
    return _generar_excel(reporte, cobertura, zona_horaria, TIPO_COMPLETO, resultados, excepciones, incluir_todas=True)


def generar_reporte_excepciones_excel(reporte: ReporteConciliacion, cobertura: CoberturaArchivosPresentacion | None, zona_horaria: str) -> bytes:
    """Devuelve bytes XLSX con solo excepciones, sin escribir archivos."""

    resultados = _resultados_ordenados(reporte.resultados)
    excepciones = [r for r in resultados if es_excepcion_o_caso_especial(r)]
    return _generar_excel(reporte, cobertura, zona_horaria, TIPO_EXCEPCIONES, resultados, excepciones, incluir_todas=False)


def generar_revisiones_pendientes_excel(reporte: ReporteConciliacion, cobertura: CoberturaArchivosPresentacion | None, zona_horaria: str) -> bytes:
    """Devuelve bytes XLSX con únicamente resultados que requieren revisión."""

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    casos = clasificar_revisiones(reporte.resultados)
    _escribir_resumen(ws, reporte, cobertura, zona_horaria, TIPO_REVISIONES, len(reporte.resultados), len(casos))
    _escribir_revisiones(wb.create_sheet("Revisiones pendientes"), casos)
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _generar_excel(reporte: ReporteConciliacion, cobertura: CoberturaArchivosPresentacion | None, zona_horaria: str, tipo: str, resultados: list[ResultadoConciliacion], excepciones: list[ResultadoConciliacion], incluir_todas: bool) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    _escribir_resumen(ws, reporte, cobertura, zona_horaria, tipo, len(resultados), len(excepciones))
    if incluir_todas:
        _escribir_operaciones(wb.create_sheet("Todas las operaciones"), resultados)
    _escribir_operaciones(wb.create_sheet("Excepciones"), excepciones)
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _escribir_resumen(ws: Worksheet, reporte: ReporteConciliacion, cobertura: CoberturaArchivosPresentacion | None, zona_horaria: str, tipo: str, filas_todas: int, filas_excepciones: int) -> None:
    ws.append(["Campo", "Valor"])
    conclusion, _ = conclusion_ejecutiva(reporte)
    filas: list[tuple[str, Any]] = [
        ("Nombre", "Kiki Control Financiero"),
        ("Tipo de reporte", tipo),
        ("Fecha y hora del procesamiento (zona operativa)", _fecha_operativa_sin_tz(reporte.fecha_procesamiento_utc, zona_horaria)),
        ("Zona horaria operativa", zona_horaria),
        ("Versión de la regla de conciliación", reporte.version_regla),
        ("Tolerancia aplicada", _decimal_o_vacio(reporte.tolerancia)),
        ("Cobertura de ventas ML", cobertura.periodo_ventas_ml.texto if cobertura else ""),
        ("Cobertura de origen MP", cobertura.periodo_origen_mp.texto if cobertura else ""),
        ("Cobertura de liquidaciones MP", cobertura.periodo_liquidacion_mp.texto if cobertura else ""),
        ("Movimientos sin fecha de liquidación", cobertura.movimientos_sin_fecha_liquidacion if cobertura else ""),
        ("Conclusión ejecutiva", conclusion),
    ]
    filas.extend((nombre, _decimal_o_vacio(valor) if nombre in _KPIS_MONETARIOS else valor) for nombre, valor in resumen_kpis_tipado(reporte).items())
    if tipo == TIPO_COMPLETO:
        filas.append(("Cantidad de filas incluidas en Todas las operaciones", filas_todas))
    filas.append(("Cantidad de filas incluidas en Excepciones", filas_excepciones))
    filas.extend([("Aclaración", ACLARACION_UTILIDAD), ("Aclaración", ACLARACION_FONDOS), ("Aclaración de privacidad", ACLARACION_PRIVACIDAD)])
    for fila in filas:
        ws.append(list(fila))
    _formatear_tabla(ws, moneda_columnas=set(), wrap_columnas={2}, freeze=False)
    for celda in ws[1]:
        _estilo_header(celda)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            _asegurar_celda(cell)
        etiqueta = row[0].value
        if etiqueta == "Fecha y hora del procesamiento (zona operativa)":
            row[1].number_format = _FORMATO_FECHA
        elif etiqueta == "Tolerancia aplicada" or etiqueta in _KPIS_MONETARIOS:
            if row[1].value != "":
                row[1].number_format = _FORMATO_MONEDA_ARS
        elif etiqueta in _CAMPOS_ENTEROS_RESUMEN or etiqueta in resumen_kpis_tipado(reporte):
            if isinstance(row[1].value, int):
                row[1].number_format = "0"
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 90


def _escribir_operaciones(ws: Worksheet, resultados: Iterable[ResultadoConciliacion]) -> None:
    ws.append(list(COLUMNAS_OPERACIONES))
    for resultado in resultados:
        ws.append(_fila_operacion(resultado))
    _formatear_tabla(ws, moneda_columnas={idx for idx, c in enumerate(COLUMNAS_OPERACIONES, start=1) if c in _COLUMNAS_MONETARIAS}, wrap_columnas={idx for idx, c in enumerate(COLUMNAS_OPERACIONES, start=1) if c in _COLUMNAS_WRAP}, freeze=True)


def _fila_operacion(r: ResultadoConciliacion) -> list[Any]:
    return [
        _texto_seguro(r.id_orden or clave_resultado(r)),
        _texto_seguro(etiqueta_estado(r.estado)),
        _decimal_o_vacio(r.neto_comercial_informado),
        _decimal_o_vacio(r.neto_pagos_aprobados),
        _decimal_o_vacio(r.diferencia_control),
        _decimal_o_vacio(r.neto_financiero_total),
        _decimal_o_vacio(r.utilidad_neta_informada),
        _si_no(r.es_pago_dividido),
        _si_no(r.tiene_devolucion),
        _si_no(r.tiene_reclamo or r.tiene_disputa),
        _si_no(r.tiene_liquidacion_pendiente),
        _si_no(r.requiere_revision),
        _texto_seguro(" | ".join(r.explicaciones)),
        _texto_seguro(", ".join(m.value for m in r.motivos)),
        _texto_seguro(", ".join(str(n) for n in r.numeros_fila_comercial)),
        _texto_seguro(", ".join(str(n) for n in r.numeros_fila_financiera)),
        r.cantidad_pagos_aprobados,
        r.cantidad_movimientos_financieros,
        _texto_seguro(r.version_regla),
        _decimal_o_vacio(r.tolerancia_aplicada),
    ]


def _resultados_ordenados(resultados: Iterable[ResultadoConciliacion]) -> list[ResultadoConciliacion]:
    return sorted(resultados, key=lambda r: (r.id_orden is None, r.id_orden or "", r.numeros_fila_financiera, r.estado.value))


def _fecha_operativa_sin_tz(fecha_utc: datetime, zona_horaria: str) -> datetime:
    return fecha_utc.astimezone(ZoneInfo(zona_horaria)).replace(tzinfo=None)


def _decimal_o_vacio(valor: Decimal | None) -> Decimal | Literal[""]:
    return "" if valor is None else valor


def _si_no(valor: bool) -> str:
    return "Sí" if valor else "No"


def _texto_seguro(valor: Any) -> str:
    texto = "" if valor is None else str(valor)
    if texto.startswith(_FORMULA_PREFIXES):
        return f"'{texto}"
    return texto


def _formatear_tabla(ws: Worksheet, moneda_columnas: set[int], wrap_columnas: set[int], freeze: bool) -> None:
    for celda in ws[1]:
        _estilo_header(celda)
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = ws.dimensions
    if freeze:
        ws.freeze_panes = "A2"
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            _asegurar_celda(cell)
            if cell.column in moneda_columnas and cell.value != "":
                cell.number_format = _FORMATO_MONEDA_ARS
            if cell.column in wrap_columnas:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    for idx, encabezado in enumerate((cell.value for cell in ws[1]), start=1):
        ancho = 18
        if encabezado in {"Explicación", "Motivos técnicos"}:
            ancho = 48
        elif encabezado in {"ID de orden", "Versión de regla"}:
            ancho = 26
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = ancho


def _estilo_header(celda: Cell) -> None:
    celda.font = Font(bold=True, color="FFFFFF")
    celda.fill = PatternFill("solid", fgColor="1F4E78")
    celda.alignment = Alignment(wrap_text=True)


def _asegurar_celda(celda: Cell) -> None:
    if isinstance(celda.value, str):
        celda.value = _texto_seguro(celda.value)


def _escribir_revisiones(ws: Worksheet, casos: Iterable[Any]) -> None:
    columnas = ("ID de orden o referencia", "Tipo de revisión", "Estado", "Motivo explicado", "Acción recomendada", "Neto ML", "Neto aprobado MP", "Neto financiero total", "Filas ML", "Filas MP", "Columnas de origen")
    ws.append(list(columnas))
    for caso in casos:
        r = caso.resultado
        fila_presentacion = caso_a_fila(caso)
        ws.append([
            _texto_seguro(fila_presentacion.id_orden_o_referencia),
            _texto_seguro(caso.nombre_visible),
            _texto_seguro(etiqueta_estado(r.estado)),
            _texto_seguro(caso.descripcion),
            _texto_seguro(caso.accion_recomendada),
            _decimal_o_vacio(r.neto_comercial_informado),
            _decimal_o_vacio(r.neto_pagos_aprobados),
            _decimal_o_vacio(r.neto_financiero_total),
            _texto_seguro(", ".join(str(n) for n in r.numeros_fila_comercial)),
            _texto_seguro(", ".join(str(n) for n in r.numeros_fila_financiera)),
            _texto_seguro(", ".join(caso.columnas_utilizadas)),
        ])
    _formatear_tabla(ws, moneda_columnas={6, 7, 8}, wrap_columnas={4, 5, 11}, freeze=True)
