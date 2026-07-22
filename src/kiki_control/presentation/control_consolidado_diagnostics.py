"""Diagnósticos puros y auditables para el control consolidado.

Capa sin dependencias de UI ni procesamiento tabular externo; trabaja sobre modelos de dominio inmutables y Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping

from kiki_control.domain.control_consolidado import EstadoControlConsolidado, ReporteControlConsolidado, ResultadoControlConsolidado

_ZERO = Decimal("0")


@dataclass(frozen=True)
class ConteoImportesMp:
    cantidad: int
    neto_aprobado_mp: Decimal = _ZERO
    neto_financiero_total_mp: Decimal = _ZERO


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
class CoberturaMonetariaFuente:
    fuente: str
    universo: str
    cantidad_total: int
    importe_total: Decimal
    cantidad_usada: int
    importe_usado: Decimal
    cantidad_excluida: int
    importe_excluido: Decimal
    motivo_exclusion: str


@dataclass(frozen=True)
class ResidualMercadoLibre:
    nombre_visible: str
    formula: str
    universo: str
    columnas_utilizadas: tuple[str, ...]
    importe: Decimal
    grupos_universo_ml_oficial: int
    grupos_calculables: int
    grupos_excluidos: int
    suma_total_ars: Decimal
    suma_ingresos_productos: Decimal
    suma_cargo_venta_impuestos: Decimal
    suma_costos_envio: Decimal
    identidad_cierra_exactamente: bool
    motivos_exclusion: Mapping[str, int]


@dataclass(frozen=True)
class GrupoExcluidoPuente:
    grupo: str
    motivo: str
    neto_ml: Decimal | None
    neto_eccomapp: Decimal | None
    neto_aprobado_mp: Decimal | None
    aporte_diferencia_ml_mp: Decimal | None


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
    grupos_excluidos_universo_triple: tuple[GrupoExcluidoPuente, ...] = ()
    aporte_excluidos_a_diferencia_ml_mp: Decimal = _ZERO
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
    anteriores: ConteoImportesMp
    dentro: ConteoImportesMp
    posteriores: ConteoImportesMp
    sin_fecha: ConteoImportesMp
    fechas_mixtas: ConteoImportesMp
    total_solo_movimiento_financiero: int
    particion_cierra_exactamente: bool
    aclaracion: str = "Estar fuera del período de ventas cargado no demuestra que falte una venta. Puede corresponder a acreditaciones, devoluciones o movimientos originados en otro período y requiere revisar la cobertura de los archivos."


@dataclass(frozen=True)
class DiagnosticoControlConsolidado:
    particion: DiagnosticoParticionResultados
    diferencias: DiagnosticoDiferenciasFuentes
    puente: PuenteImportesFuentes
    utilidad: DiagnosticoCoberturaUtilidad
    revisiones: DiagnosticoRevisionesConsolidadas
    temporal_mp_sin_venta: DiagnosticoTemporalMp
    cobertura_monetaria: tuple[CoberturaMonetariaFuente, ...]
    residual_ml: ResidualMercadoLibre


def _sum(valores: Iterable[Decimal | None]) -> Decimal:
    total = _ZERO
    for valor in valores:
        if valor is not None:
            total += valor
    return total


def _grupo(r: ResultadoControlConsolidado) -> str:
    if r.id_grupo_canonico:
        return r.id_grupo_canonico
    if r.ids_orden:
        return ", ".join(r.ids_orden)
    if r.filas_origen_mp:
        return f"fila MP {','.join(map(str, r.filas_origen_mp))}"
    return r.clave_resultado


def motivos_datos_criticos_faltantes(r: ResultadoControlConsolidado) -> tuple[str, ...]:
    motivos: list[str] = []
    if r.tiene_mercado_libre_oficial and r.total_informado_ml is None:
        motivos.append("Total (ARS) ML ausente")
    if r.tiene_eccomapp and r.costo_productos_eccomapp is None:
        motivos.append("Costo de producto Eccomapp ausente")
    mp_no_comparable_legitimo = bool(
        r.neto_financiero_total_mp is not None
        or r.indicadores_financieros.tiene_devolucion
        or r.indicadores_financieros.tiene_reclamo
        or r.indicadores_financieros.tiene_disputa
        or (r.tipo_movimiento_financiero is not None and str(r.tipo_movimiento_financiero).endswith("MOVIMIENTO_DE_FONDOS"))
    )
    if r.tiene_mercado_libre_oficial and r.tiene_mercado_pago and r.neto_aprobado_mp is None and not mp_no_comparable_legitimo:
        motivos.append("Sin neto aprobado MP comparable")
    return tuple(motivos)


def tiene_datos_criticos_faltantes(r: ResultadoControlConsolidado) -> bool:
    return bool(motivos_datos_criticos_faltantes(r))


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
        sum(1 for r in diferencias if r.diferencia_ml_mp is not None and r.diferencia_ml_mp > 0),
        sum(1 for r in diferencias if r.diferencia_ml_mp is not None and r.diferencia_ml_mp < 0), suma_ml, suma_mp, suma_dif, cierra,
        None if cierra else "La suma de diferencias ML–MP no coincide exactamente con Neto MP comparable menos Neto ML comparable.",
    )


def diagnosticar_puente(reporte: ReporteControlConsolidado) -> PuenteImportesFuentes:
    venta = tuple(r for r in reporte.resultados if r.monto_venta_ml is not None and r.monto_venta_eccomapp_informado is not None)
    neto = tuple(r for r in reporte.resultados if r.total_informado_ml is not None and r.neto_mp_eccomapp_informado is not None and r.neto_aprobado_mp is not None)
    venta_ml = _sum(r.monto_venta_ml for r in venta); venta_ec = _sum(r.monto_venta_eccomapp_informado for r in venta)
    neto_ml = _sum(r.total_informado_ml for r in neto); neto_ec = _sum(r.neto_mp_eccomapp_informado for r in neto); neto_mp = _sum(r.neto_aprobado_mp for r in neto)
    ec_ml = neto_ec - neto_ml; mp_ec = neto_mp - neto_ec; mp_ml = neto_mp - neto_ml
    excluidos = tuple(_grupo_excluido_puente(r) for r in reporte.resultados if r not in neto)
    aporte = _sum(g.aporte_diferencia_ml_mp for g in excluidos)
    return PuenteImportesFuentes(len(venta), venta_ml, venta_ec, venta_ml - venta_ec, len(neto), neto_ml, neto_ec, neto_mp, ec_ml, mp_ec, mp_ml, mp_ml == mp_ec + ec_ml, excluidos, aporte)


def _grupo_excluido_puente(r: ResultadoControlConsolidado) -> GrupoExcluidoPuente:
    faltan = []
    if r.total_informado_ml is None: faltan.append("Neto ML")
    if r.neto_mp_eccomapp_informado is None: faltan.append("Neto Eccomapp")
    if r.neto_aprobado_mp is None: faltan.append("Neto aprobado MP")
    aporte = r.neto_aprobado_mp - r.total_informado_ml if r.neto_aprobado_mp is not None and r.total_informado_ml is not None else None
    return GrupoExcluidoPuente(_grupo(r), "Fuera del puente triple por faltar " + ", ".join(faltan), r.total_informado_ml, r.neto_mp_eccomapp_informado, r.neto_aprobado_mp, aporte)


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
        ("Datos críticos incompletos", tiene_datos_criticos_faltantes, "Completar campos críticos en la fuente correspondiente."),
        ("Diferencia pendiente de clasificación contable", lambda r: r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > r.tolerancia, "Revisar ML oficial, Eccomapp y MP sin asumir causa contable."),
        ("Venta oficial sin Total (ARS)", lambda r: r.tiene_mercado_libre_oficial and r.total_informado_ml is None, "Completar o revisar la columna Total (ARS) de Mercado Libre oficial antes del control monetario."),
        ("Fuente faltante", lambda r: not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago), "Confirmar si el archivo cargado cubre el universo esperado."),
        ("Revisión financiera", lambda r: r.estado == EstadoControlConsolidado.EN_REVISION_FINANCIERA or r.indicadores_financieros.tiene_devolucion or r.indicadores_financieros.tiene_reclamo or r.indicadores_financieros.tiene_disputa, "Revisar movimientos financieros asociados."),
    )
    items=[]
    for nombre, pred, accion in reglas:
        rs=tuple(r for r in reporte.resultados if r.requiere_revision and pred(r))
        if rs: items.append(DiagnosticoRevision(nombre, len(rs), _sum(r.neto_aprobado_mp for r in rs) if nombre != "Datos críticos incompletos" else None, accion, tuple(_grupo(r) for r in rs)))
    return DiagnosticoRevisionesConsolidadas(reporte.total_requieren_revision, tuple(items), "Conteos multietiqueta: no deben sumarse para obtener el total. Revisiones consolidadas: tres fuentes. Revisiones históricas: Eccomapp–Mercado Pago. Los contadores 206 y 122 pertenecen a universos diferentes y no son comparables directamente.")


def _as_date(v: date | datetime | None) -> date | None:
    if isinstance(v, datetime): return v.date()
    return v


def diagnosticar_temporal_mp_sin_venta(reporte: ReporteControlConsolidado, inicio_ml: date | datetime | None = None, fin_ml: date | datetime | None = None, fechas_mp_por_fila: Mapping[int, date | datetime | None] | None = None) -> DiagnosticoTemporalMp:
    inicio = _as_date(inicio_ml); fin = _as_date(fin_ml); fechas = fechas_mp_por_fila or {}
    buckets = {
        "anteriores": [0, _ZERO, _ZERO],
        "dentro": [0, _ZERO, _ZERO],
        "posteriores": [0, _ZERO, _ZERO],
        "sin_fecha": [0, _ZERO, _ZERO],
        "fechas_mixtas": [0, _ZERO, _ZERO],
    }
    total = 0
    for r in reporte.resultados:
        if r.estado != EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO: continue
        total += 1
        categorias = set()
        for fila in r.filas_origen_mp:
            fecha = _as_date(fechas.get(fila)) if fila in fechas else None
            if fecha is None or inicio is None or fin is None:
                categorias.add("sin_fecha")
            elif fecha < inicio:
                categorias.add("anteriores")
            elif fecha > fin:
                categorias.add("posteriores")
            else:
                categorias.add("dentro")
        if not categorias:
            categorias.add("sin_fecha")
        key = next(iter(categorias)) if len(categorias) == 1 else "fechas_mixtas"
        buckets[key][0] += 1
        if r.neto_aprobado_mp is not None:
            buckets[key][1] += r.neto_aprobado_mp
        if r.neto_financiero_total_mp is not None:
            buckets[key][2] += r.neto_financiero_total_mp
    conteos = tuple(ConteoImportesMp(v[0], v[1], v[2]) for v in buckets.values())
    return DiagnosticoTemporalMp(*conteos, total, sum(c.cantidad for c in conteos) == total)



def diagnosticar_cobertura_monetaria(reporte: ReporteControlConsolidado) -> tuple[CoberturaMonetariaFuente, ...]:
    resultados = reporte.resultados
    comun_ml_ec = tuple(r for r in resultados if r.total_informado_ml is not None and r.costo_productos_eccomapp is not None)
    comun_ml_mp = tuple(r for r in resultados if r.total_informado_ml is not None and r.neto_aprobado_mp is not None)
    comun_triple = tuple(r for r in resultados if r.total_informado_ml is not None and r.neto_mp_eccomapp_informado is not None and r.neto_aprobado_mp is not None)
    utilidad = comun_ml_ec
    def item(fuente, universo, total_rs, usado_rs, attr, motivo):
        return CoberturaMonetariaFuente(fuente, universo, len(total_rs), _sum(getattr(r, attr) for r in total_rs), len(usado_rs), _sum(getattr(r, attr) for r in usado_rs), len(total_rs)-len(usado_rs), _sum(getattr(r, attr) for r in total_rs if r not in usado_rs), motivo)
    ml_total=tuple(r for r in resultados if r.total_informado_ml is not None); ec_total=tuple(r for r in resultados if r.costo_productos_eccomapp is not None); mp_total=tuple(r for r in resultados if r.neto_aprobado_mp is not None)
    return (
        item("Mercado Libre oficial", "universo completo ML oficial", ml_total, ml_total, "total_informado_ml", "Sin exclusiones dentro del universo completo."),
        item("Eccomapp", "universo completo Eccomapp", ec_total, ec_total, "costo_productos_eccomapp", "Sin exclusiones dentro del universo completo."),
        item("Mercado Libre oficial", "universo ML–Eccomapp", ml_total, comun_ml_ec, "total_informado_ml", "Excluido cuando falta ML Total (ARS) o costo Eccomapp."),
        item("Eccomapp", "universo ML–Eccomapp", ec_total, comun_ml_ec, "costo_productos_eccomapp", "Excluido cuando falta ML Total (ARS) o costo Eccomapp."),
        item("Mercado Libre oficial", "universo ML–MP", ml_total, comun_ml_mp, "total_informado_ml", "Excluido cuando falta ML Total (ARS) o neto aprobado MP."),
        item("Mercado Pago", "universo ML–MP", mp_total, comun_ml_mp, "neto_aprobado_mp", "Excluido cuando falta ML Total (ARS) o neto aprobado MP."),
        item("Mercado Libre oficial", "universo ML–Eccomapp–MP", ml_total, comun_triple, "total_informado_ml", "Excluido cuando falta alguno de los tres netos del puente."),
        item("Eccomapp", "universo ML–Eccomapp–MP", tuple(r for r in resultados if r.neto_mp_eccomapp_informado is not None), comun_triple, "neto_mp_eccomapp_informado", "Excluido cuando falta alguno de los tres netos del puente."),
        item("Mercado Pago", "universo ML–Eccomapp–MP", mp_total, comun_triple, "neto_aprobado_mp", "Excluido cuando falta alguno de los tres netos del puente."),
        item("Mercado Libre oficial", "universo calculable de utilidad", ml_total, utilidad, "total_informado_ml", "Excluido cuando falta Total (ARS) ML o costo Eccomapp."),
        item("Eccomapp", "universo calculable de utilidad", ec_total, utilidad, "costo_productos_eccomapp", "Excluido cuando falta Total (ARS) ML o costo Eccomapp."),
    )


def diagnosticar_residual_ml(reporte: ReporteControlConsolidado) -> ResidualMercadoLibre:
    candidatos_ml = tuple(r for r in reporte.resultados if r.tiene_mercado_libre_oficial)
    calculables = tuple(
        r for r in candidatos_ml
        if r.total_informado_ml is not None
        and r.monto_venta_ml is not None
        and r.cargo_venta_impuestos_ml is not None
        and r.costo_envio_ml is not None
    )
    excluidos = tuple(r for r in candidatos_ml if r not in calculables)
    motivos = {
        "falta Total (ARS)": 0,
        "falta Ingresos por productos (ARS)": 0,
        "falta Cargo por venta e impuestos (ARS)": 0,
        "falta Costos de envío (ARS)": 0,
    }
    for r in excluidos:
        if r.total_informado_ml is None:
            motivos["falta Total (ARS)"] += 1
        if r.monto_venta_ml is None:
            motivos["falta Ingresos por productos (ARS)"] += 1
        if r.cargo_venta_impuestos_ml is None:
            motivos["falta Cargo por venta e impuestos (ARS)"] += 1
        if r.costo_envio_ml is None:
            motivos["falta Costos de envío (ARS)"] += 1
    suma_total = _sum(r.total_informado_ml for r in calculables)
    suma_ingresos = _sum(r.monto_venta_ml for r in calculables)
    suma_cargos = _sum(r.cargo_venta_impuestos_ml for r in calculables)
    suma_envios = _sum(r.costo_envio_ml for r in calculables)
    residual = suma_total - (suma_ingresos + suma_cargos + suma_envios)
    return ResidualMercadoLibre(
        "Otros conceptos y ajustes ML no desagregados en este resumen",
        "Total (ARS) - (Ingresos por productos (ARS) + Cargo por venta e impuestos (ARS) + Costos de envío (ARS))",
        "universo ML oficial con los cuatro importes presentes",
        ("Total (ARS)", "Ingresos por productos (ARS)", "Cargo por venta e impuestos (ARS)", "Costos de envío (ARS)"),
        residual,
        len(candidatos_ml),
        len(calculables),
        len(excluidos),
        suma_total,
        suma_ingresos,
        suma_cargos,
        suma_envios,
        suma_total == suma_ingresos + suma_cargos + suma_envios + residual,
        motivos,
    )

def diagnosticar_control_consolidado(reporte: ReporteControlConsolidado, inicio_ml: date | datetime | None = None, fin_ml: date | datetime | None = None, fechas_mp_por_fila: Mapping[int, date | datetime | None] | None = None) -> DiagnosticoControlConsolidado:
    return DiagnosticoControlConsolidado(diagnosticar_particion(reporte), diagnosticar_diferencias(reporte), diagnosticar_puente(reporte), diagnosticar_utilidad(reporte), diagnosticar_revisiones(reporte), diagnosticar_temporal_mp_sin_venta(reporte, inicio_ml, fin_ml, fechas_mp_por_fila), diagnosticar_cobertura_monetaria(reporte), diagnosticar_residual_ml(reporte))
