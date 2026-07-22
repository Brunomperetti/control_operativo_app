"""Diagnósticos puros y auditables para el control consolidado.

No usa Streamlit ni pandas. Trabaja sobre modelos de dominio inmutables y Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping

from kiki_control.domain.control_consolidado import EstadoControlConsolidado, ReporteControlConsolidado, ResultadoControlConsolidado

_ZERO = Decimal("0")


@dataclass(frozen=True)
class ConteoImporte:
    cantidad: int
    importe: Decimal = _ZERO


@dataclass(frozen=True)
class DiagnosticoParticionResultados:
    total_resultados: int
    por_estado_principal: Mapping[EstadoControlConsolidado, int]
    cierra_exactamente: bool
    diferencia_con_total: int


@dataclass(frozen=True)
class DiagnosticoDiferenciasFuentes:
    comparables_totales: int
    con_diferencia_ml_mp: int
    coincidencias_dentro_tolerancia: int
    no_comparables: int
    diferencias_positivas: int
    diferencias_negativas: int
    suma_neto_ml_comparable: Decimal
    suma_neto_mp_comparable: Decimal
    suma_diferencia_ml_mp: Decimal
    identidad_cierra_exactamente: bool
    error_consistencia: str | None


@dataclass(frozen=True)
class PuenteImportesFuentes:
    universo_venta_comercial: int
    venta_oficial_ml: Decimal
    venta_informada_eccomapp: Decimal
    diferencia_ml_oficial_eccomapp: Decimal
    universo_neto_esperado: int
    neto_oficial_ml: Decimal
    neto_informado_eccomapp: Decimal
    neto_aprobado_mp: Decimal
    eccomapp_menos_ml: Decimal
    mp_menos_eccomapp: Decimal
    mp_menos_ml: Decimal
    identidad_cierra_exactamente: bool
    clasificacion_pendiente: str = "Diferencia pendiente de clasificación contable"


@dataclass(frozen=True)
class DiagnosticoCoberturaUtilidad:
    grupos_totales: int
    grupos_calculables: int
    grupos_excluidos: int
    neto_ml_universo_utilidad: Decimal
    costo_productos_universo_utilidad: Decimal
    utilidad_preliminar: Decimal
    costo_eccomapp_fuera_universo_calculable: Decimal
    motivos_exclusion: Mapping[str, int]
    motivos_cierran_exactamente: bool
    identidad_cierra_exactamente: bool


@dataclass(frozen=True)
class DiagnosticoRevision:
    motivo_visible: str
    cantidad: int
    importe_afectado: Decimal | None
    accion_recomendada: str
    grupos_involucrados: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosticoRevisionesConsolidadas:
    total_primario_requiere_revision: int
    revisiones_multietiqueta: tuple[DiagnosticoRevision, ...]
    aclaracion: str


@dataclass(frozen=True)
class DiagnosticoTemporalMp:
    anteriores: ConteoImporte
    dentro: ConteoImporte
    posteriores: ConteoImporte
    sin_fecha: ConteoImporte
    aclaracion: str = "Un movimiento fuera del período de ventas cargado no implica necesariamente una venta faltante."


@dataclass(frozen=True)
class DiagnosticoControlConsolidado:
    particion: DiagnosticoParticionResultados
    diferencias: DiagnosticoDiferenciasFuentes
    puente: PuenteImportesFuentes
    utilidad: DiagnosticoCoberturaUtilidad
    revisiones: DiagnosticoRevisionesConsolidadas
    temporal_mp_sin_venta: DiagnosticoTemporalMp


def _sum(valores: Iterable[Decimal | None]) -> Decimal:
    total = _ZERO
    for valor in valores:
        if valor is not None:
            total += valor
    return total


def _grupo(r: ResultadoControlConsolidado) -> str:
    return r.id_grupo_canonico or ", ".join(r.ids_orden) or f"fila MP {','.join(map(str, r.filas_origen_mp))}" or r.clave_resultado


def diagnosticar_particion(reporte: ReporteControlConsolidado) -> DiagnosticoParticionResultados:
    estados = tuple(EstadoControlConsolidado)
    por_estado = {estado: sum(1 for r in reporte.resultados if r.estado == estado) for estado in estados}
    suma = sum(por_estado.values())
    return DiagnosticoParticionResultados(reporte.total_resultados, por_estado, suma == reporte.total_resultados, suma - reporte.total_resultados)


def diagnosticar_diferencias(reporte: ReporteControlConsolidado) -> DiagnosticoDiferenciasFuentes:
    comparables = tuple(r for r in reporte.resultados if r.total_informado_ml is not None and r.neto_aprobado_mp is not None)
    diferencias = tuple(r for r in comparables if r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > reporte.tolerancia)
    suma_ml = _sum(r.total_informado_ml for r in comparables)
    suma_mp = _sum(r.neto_aprobado_mp for r in comparables)
    suma_dif = _sum(r.diferencia_ml_mp for r in comparables)
    cierra = suma_dif == (suma_mp - suma_ml)
    return DiagnosticoDiferenciasFuentes(
        len(comparables), len(diferencias), len(comparables) - len(diferencias), reporte.total_resultados - len(comparables),
        sum(1 for r in diferencias if r.diferencia_ml_mp and r.diferencia_ml_mp > 0),
        sum(1 for r in diferencias if r.diferencia_ml_mp and r.diferencia_ml_mp < 0), suma_ml, suma_mp, suma_dif, cierra,
        None if cierra else "La suma de diferencias ML–MP no coincide exactamente con Neto MP comparable menos Neto ML comparable.",
    )


def diagnosticar_puente(reporte: ReporteControlConsolidado) -> PuenteImportesFuentes:
    venta = tuple(r for r in reporte.resultados if r.monto_venta_ml is not None and r.monto_venta_eccomapp_informado is not None)
    neto = tuple(r for r in reporte.resultados if r.total_informado_ml is not None and r.neto_mp_eccomapp_informado is not None and r.neto_aprobado_mp is not None)
    venta_ml = _sum(r.monto_venta_ml for r in venta); venta_ec = _sum(r.monto_venta_eccomapp_informado for r in venta)
    neto_ml = _sum(r.total_informado_ml for r in neto); neto_ec = _sum(r.neto_mp_eccomapp_informado for r in neto); neto_mp = _sum(r.neto_aprobado_mp for r in neto)
    ec_ml = neto_ec - neto_ml; mp_ec = neto_mp - neto_ec; mp_ml = neto_mp - neto_ml
    return PuenteImportesFuentes(len(venta), venta_ml, venta_ec, venta_ml - venta_ec, len(neto), neto_ml, neto_ec, neto_mp, ec_ml, mp_ec, mp_ml, mp_ml == mp_ec + ec_ml)


def diagnosticar_utilidad(reporte: ReporteControlConsolidado) -> DiagnosticoCoberturaUtilidad:
    calc = tuple(r for r in reporte.resultados if r.total_informado_ml is not None and r.costo_productos_eccomapp is not None)
    excl = tuple(r for r in reporte.resultados if r not in calc)
    motivos = {"sin venta oficial":0,"con venta oficial pero sin Total (ARS)":0,"sin Eccomapp":0,"con Eccomapp pero sin costo de producto":0,"faltan ambas entradas":0,"otro caso no clasificado":0}
    for r in excl:
        if not r.tiene_mercado_libre_oficial and not r.tiene_eccomapp: motivos["faltan ambas entradas"] += 1
        elif not r.tiene_mercado_libre_oficial: motivos["sin venta oficial"] += 1
        elif r.tiene_mercado_libre_oficial and r.total_informado_ml is None: motivos["con venta oficial pero sin Total (ARS)"] += 1
        elif not r.tiene_eccomapp: motivos["sin Eccomapp"] += 1
        elif r.tiene_eccomapp and r.costo_productos_eccomapp is None: motivos["con Eccomapp pero sin costo de producto"] += 1
        else: motivos["otro caso no clasificado"] += 1
    neto = _sum(r.total_informado_ml for r in calc); costo = _sum(r.costo_productos_eccomapp for r in calc); utilidad = _sum(r.utilidad_preliminar_control for r in calc)
    return DiagnosticoCoberturaUtilidad(reporte.total_resultados, len(calc), len(excl), neto, costo, utilidad, _sum(r.costo_productos_eccomapp for r in excl), motivos, sum(motivos.values()) == len(excl), utilidad == neto - costo)


def diagnosticar_revisiones(reporte: ReporteControlConsolidado) -> DiagnosticoRevisionesConsolidadas:
    reglas = (
        ("Datos críticos incompletos", lambda r: any((r.tiene_mercado_libre_oficial and r.total_informado_ml is None, r.tiene_eccomapp and r.costo_productos_eccomapp is None, r.tiene_mercado_pago and r.neto_aprobado_mp is None)), "Completar campos críticos en la fuente correspondiente."),
        ("Diferencia pendiente de clasificación contable", lambda r: r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > r.tolerancia, "Revisar ML oficial, Eccomapp y MP sin asumir causa contable."),
        ("Fuente faltante", lambda r: not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago), "Confirmar si el archivo cargado cubre el universo esperado."),
        ("Revisión financiera", lambda r: r.estado == EstadoControlConsolidado.EN_REVISION_FINANCIERA or r.indicadores_financieros.tiene_devolucion or r.indicadores_financieros.tiene_reclamo or r.indicadores_financieros.tiene_disputa, "Revisar movimientos financieros asociados."),
    )
    items=[]
    for nombre, pred, accion in reglas:
        rs=tuple(r for r in reporte.resultados if pred(r))
        if rs: items.append(DiagnosticoRevision(nombre, len(rs), _sum(r.neto_aprobado_mp for r in rs) if nombre != "Datos críticos incompletos" else None, accion, tuple(_grupo(r) for r in rs)))
    return DiagnosticoRevisionesConsolidadas(reporte.total_requieren_revision, tuple(items), "Conteos multietiqueta: no deben sumarse para obtener el total. Revisiones consolidadas: tres fuentes. Revisiones históricas: Eccomapp–Mercado Pago. Los contadores 206 y 122 pertenecen a universos diferentes y no son comparables directamente.")


def _as_date(v: date | datetime | None) -> date | None:
    if isinstance(v, datetime): return v.date()
    return v


def diagnosticar_temporal_mp_sin_venta(reporte: ReporteControlConsolidado, inicio_ml: date | datetime | None = None, fin_ml: date | datetime | None = None, fechas_mp_por_fila: Mapping[int, date | datetime | None] | None = None) -> DiagnosticoTemporalMp:
    inicio = _as_date(inicio_ml); fin = _as_date(fin_ml); fechas = fechas_mp_por_fila or {}
    buckets = {"anteriores": [0,_ZERO], "dentro": [0,_ZERO], "posteriores": [0,_ZERO], "sin_fecha": [0,_ZERO]}
    for r in reporte.resultados:
        if r.estado != EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO: continue
        fecha = next((_as_date(fechas.get(n)) for n in r.filas_origen_mp if fechas.get(n) is not None), None)
        key = "sin_fecha" if fecha is None or inicio is None or fin is None else ("anteriores" if fecha < inicio else "posteriores" if fecha > fin else "dentro")
        buckets[key][0] += 1; buckets[key][1] += r.neto_financiero_total_mp or r.neto_aprobado_mp or _ZERO
    return DiagnosticoTemporalMp(*(ConteoImporte(v[0], v[1]) for v in buckets.values()))


def diagnosticar_control_consolidado(reporte: ReporteControlConsolidado, inicio_ml: date | datetime | None = None, fin_ml: date | datetime | None = None, fechas_mp_por_fila: Mapping[int, date | datetime | None] | None = None) -> DiagnosticoControlConsolidado:
    return DiagnosticoControlConsolidado(diagnosticar_particion(reporte), diagnosticar_diferencias(reporte), diagnosticar_puente(reporte), diagnosticar_utilidad(reporte), diagnosticar_revisiones(reporte), diagnosticar_temporal_mp_sin_venta(reporte, inicio_ml, fin_ml, fechas_mp_por_fila))
