"""Transformaciones puras para presentar el control financiero consolidado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Any

from kiki_control.domain.control_consolidado import EstadoControlConsolidado, ReporteControlConsolidado, ResultadoControlConsolidado


@dataclass(frozen=True)
class Kpi:
    nombre: str
    valor: str
    ayuda: str


@dataclass(frozen=True)
class CoberturaFuente:
    nombre: str
    minimo: str
    maximo: str
    extra: str = ""


@dataclass(frozen=True)
class FilaControlConsolidado:
    clave: str
    grupo_orden: str
    estado: str
    estado_codigo: str
    fuentes_disponibles: str
    venta_ml_oficial: str
    cargos_impuestos_ml: str
    costo_envio_ml: str
    neto_esperado_ml: str
    costo_productos: str
    neto_aprobado_mp: str
    neto_financiero_total_mp: str
    diferencia_ml_mp: str
    utilidad_preliminar: str
    requiere_revision: str
    tiene_diferencia: bool
    tiene_datos_faltantes: bool


def formato_importe(valor: Decimal | None) -> str:
    if valor is None:
        return "No calculado"
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sumar(valores: Iterable[Decimal | None]) -> Decimal:
    total = Decimal("0")
    for valor in valores:
        if valor is not None:
            total += valor
    return total


def fuentes_disponibles(r: ResultadoControlConsolidado) -> str:
    fuentes = []
    if r.tiene_mercado_libre_oficial:
        fuentes.append("ML oficial")
    if r.tiene_eccomapp:
        fuentes.append("Eccomapp")
    if r.tiene_mercado_pago:
        fuentes.append("MP")
    return ", ".join(fuentes) if fuentes else "Sin fuente comercial asociada"


def conclusion_ejecutiva_consolidada(reporte: ReporteControlConsolidado) -> str:
    calculables = sum(1 for r in reporte.resultados if r.utilidad_preliminar_control is not None)
    return (
        f"Se consolidaron {reporte.total_resultados} grupos: {reporte.total_completa} completos, "
        f"{reporte.total_con_diferencia} con diferencia, {reporte.total_sin_venta_oficial} sin venta oficial, "
        f"{reporte.total_sin_costo_producto} sin costo de producto, {reporte.total_sin_movimiento_financiero} sin movimiento MP, "
        f"{reporte.total_solo_movimiento_financiero} solo movimientos financieros y {reporte.total_duplicada_o_ambigua} duplicados o ambiguos. "
        f"Requieren revisión {reporte.total_requieren_revision}; la utilidad preliminar de control pudo calcularse para {calculables}. "
        "Estos importes son informados por la fuente y no constituyen resultado contable o fiscal definitivo."
    )


def kpis_consolidados(reporte: ReporteControlConsolidado) -> dict[str, list[Kpi]]:
    resultados = reporte.resultados
    comparables = [r for r in resultados if r.total_informado_ml is not None and r.neto_aprobado_mp is not None]
    utilidad_calc = [r for r in resultados if r.utilidad_preliminar_control is not None]
    ayuda_limite = " Limitación: control operativo preliminar, no es resultado contable o fiscal definitivo."
    return {
        "Bloque A — Importes informados por ML oficial": [
            Kpi("Ventas ML oficial", formato_importe(_sumar(r.monto_venta_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: monto_venta_ml. Columna externa: Ingresos por productos (ARS). Universo: resultados consolidados con venta oficial." + ayuda_limite),
            Kpi("Cargos e impuestos ML", formato_importe(_sumar(r.cargo_venta_impuestos_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: cargo_venta_impuestos_ml. Columna externa: Cargo por venta e impuestos (ARS). Universo: resultados con venta oficial." + ayuda_limite),
            Kpi("Costo de envío ML", formato_importe(_sumar(r.costo_envio_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: costo_envio_ml. Columnas externas: Ingresos por envío (ARS), Costos de envío (ARS) y cargos de envío informados. Universo: resultados con venta oficial." + ayuda_limite),
            Kpi("Neto esperado ML", formato_importe(_sumar(r.total_informado_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: total_informado_ml. Columna externa: Total (ARS). Universo: resultados con venta oficial. Fórmula: no se reconstruye; se usa el total informado." + ayuda_limite),
        ],
        "Bloque B — Comparación financiera": [
            Kpi("Neto ML comparable", formato_importe(_sumar(r.total_informado_ml for r in comparables)), "Fuente: ML oficial. Campo: total_informado_ml. Universo: solo resultados donde también existe neto_aprobado_mp." + ayuda_limite),
            Kpi("Neto MP comparable", formato_importe(_sumar(r.neto_aprobado_mp for r in comparables)), "Fuente: Mercado Pago. Campo: neto_aprobado_mp. Columna: MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO. Universo: mismos resultados comparables con ML." + ayuda_limite),
            Kpi("Diferencia comparable ML–MP", formato_importe(_sumar(r.diferencia_ml_mp for r in comparables)), "Fórmula: suma de diferencia_ml_mp en resultados comparables; no mezcla movimientos MP sin ML ni PAYOUT." + ayuda_limite),
            Kpi("Neto MP sin venta oficial asociada", formato_importe(_sumar(r.neto_aprobado_mp for r in resultados if r.neto_aprobado_mp is not None and not r.tiene_mercado_libre_oficial)), "Fuente: Mercado Pago. Universo: movimientos no encontrados en el archivo de ventas oficiales cargado." + ayuda_limite),
        ],
        "Bloque C — Costos y utilidad": [
            Kpi("Costo de productos Eccomapp", formato_importe(_sumar(r.costo_productos_eccomapp for r in resultados)), "Fuente: Eccomapp. Campo: costo_productos_eccomapp. Columna: Costo Total (Con IVA) ($). Universo: resultados con Eccomapp." + ayuda_limite),
            Kpi("Utilidad preliminar calculable", formato_importe(_sumar(r.utilidad_preliminar_control for r in utilidad_calc)), "Fórmula: Total (ARS) ML oficial menos Costo Total (Con IVA) Eccomapp, solo donde ambos existen." + ayuda_limite),
            Kpi("Cobertura de utilidad", f"{len(utilidad_calc)} de {len(resultados)} grupos con los datos necesarios", "Universo: grupos consolidados. Requiere venta oficial ML y costo de producto Eccomapp." + ayuda_limite),
        ],
        "Bloque D — Calidad y pendientes": [
            Kpi("Resultados completos", str(reporte.total_completa), "Resultados con fuentes y comparaciones suficientes según el dominio."),
            Kpi("Requieren revisión", str(reporte.total_requieren_revision), "Resultados marcados por el dominio como requiere_revision."),
            Kpi("Sin costo", str(reporte.total_sin_costo_producto), "Resultados sin costo de producto Eccomapp encontrado."),
            Kpi("Sin MP", str(reporte.total_sin_movimiento_financiero), "Resultados sin movimiento Mercado Pago encontrado."),
            Kpi("Sin venta oficial", str(reporte.total_sin_venta_oficial), "Resultados sin venta oficial ML encontrada."),
            Kpi("Duplicados o ambiguos", str(reporte.total_duplicada_o_ambigua), "Resultados con ambigüedad o duplicados según reglas de dominio."),
        ],
    }


def cobertura_tres_fuentes(ventas_ml: Iterable[Any], operaciones: Iterable[Any], movimientos: Iterable[Any]) -> tuple[CoberturaFuente, ...]:
    def rango(objs, attr):
        fechas = [getattr(o, attr) for o in objs if getattr(o, attr, None) is not None]
        if not fechas: return ("Sin fechas", "Sin fechas")
        return (min(fechas).date().isoformat(), max(fechas).date().isoformat())
    movs = tuple(movimientos)
    sin_liq = sum(1 for m in movs if getattr(m, "fecha_liquidacion_local", None) is None)
    return (
        CoberturaFuente("Ventas oficiales ML", *rango(tuple(ventas_ml), "fecha_venta")),
        CoberturaFuente("Ventas/costos Eccomapp", *rango(tuple(operaciones), "fecha_hora_venta")),
        CoberturaFuente("Origen movimientos MP", *rango(movs, "fecha_origen_local")),
        CoberturaFuente("Liquidaciones MP", *rango(movs, "fecha_liquidacion_local"), f"Sin fecha de liquidación: {sin_liq}"),
    )


def advertir_periodos_distintos(cobertura: tuple[CoberturaFuente, ...]) -> bool:
    rangos = {(c.minimo, c.maximo) for c in cobertura if c.minimo != "Sin fechas"}
    return len(rangos) > 1


def filas_tabla_consolidada(resultados: Iterable[ResultadoControlConsolidado]) -> list[FilaControlConsolidado]:
    filas=[]
    for r in resultados:
        faltan = not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago)
        filas.append(FilaControlConsolidado(r.clave_resultado, r.id_grupo_canonico or ", ".join(r.ids_orden) or r.clave_resultado, r.estado.value.replace("_"," ").title(), r.estado.value, fuentes_disponibles(r), formato_importe(r.monto_venta_ml), formato_importe(r.cargo_venta_impuestos_ml), formato_importe(r.costo_envio_ml), formato_importe(r.total_informado_ml), formato_importe(r.costo_productos_eccomapp), formato_importe(r.neto_aprobado_mp), formato_importe(r.neto_financiero_total_mp), formato_importe(r.diferencia_ml_mp), formato_importe(r.utilidad_preliminar_control), "Sí" if r.requiere_revision else "No", r.diferencia_ml_mp not in (None, Decimal("0")), faltan))
    return filas


def filtrar_filas_consolidadas(filas, estados:set[str], busqueda:str, solo_revision:bool, solo_diferencia:bool, solo_faltantes:bool):
    q=(busqueda or "").strip().lower()
    out=[]
    for f in filas:
        if estados and f.estado_codigo not in estados: continue
        if q and q not in f.grupo_orden.lower(): continue
        if solo_revision and f.requiere_revision != "Sí": continue
        if solo_diferencia and not f.tiene_diferencia: continue
        if solo_faltantes and not f.tiene_datos_faltantes: continue
        out.append(f)
    return out


def tabla_consolidada(filas):
    return [f.__dict__ | {"Grupo u orden": f.grupo_orden, "Estado": f.estado, "Fuentes disponibles": f.fuentes_disponibles, "Venta ML oficial": f.venta_ml_oficial, "Cargos e impuestos ML": f.cargos_impuestos_ml, "Costo envío ML": f.costo_envio_ml, "Neto esperado ML": f.neto_esperado_ml, "Costo productos": f.costo_productos, "Neto aprobado MP": f.neto_aprobado_mp, "Neto financiero total MP": f.neto_financiero_total_mp, "Diferencia ML–MP": f.diferencia_ml_mp, "Utilidad preliminar": f.utilidad_preliminar, "Requiere revisión": f.requiere_revision} for f in filas]


def detalle_control(r: ResultadoControlConsolidado) -> dict[str, str]:
    return {"Grupo": r.id_grupo_canonico or "No informado", "Órdenes": ", ".join(r.ids_orden) or "No informado", "Estado": r.estado.value, "Fuentes presentes": fuentes_disponibles(r), "Venta ML oficial": formato_importe(r.total_informado_ml), "Costo productos": formato_importe(r.costo_productos_eccomapp), "Neto aprobado MP": formato_importe(r.neto_aprobado_mp), "Diferencia ML–MP": formato_importe(r.diferencia_ml_mp), "Utilidad preliminar": formato_importe(r.utilidad_preliminar_control), "Requiere revisión": "Sí" if r.requiere_revision else "No", "Explicación": "; ".join(r.explicaciones) or "Resultado informado por las fuentes cargadas; requiere revisión si hay datos faltantes o diferencias."}


def explicacion_resultado(r: ResultadoControlConsolidado) -> list[dict[str,str]]:
    falta_utilidad=[]
    if r.total_informado_ml is None: falta_utilidad.append("Total (ARS) ML oficial")
    if r.costo_productos_eccomapp is None: falta_utilidad.append("Costo Total (Con IVA) Eccomapp")
    return [
        {"Concepto":"Utilidad preliminar de control", "Valor": formato_importe(r.utilidad_preliminar_control), "Archivo de origen":"ML oficial + Eccomapp", "Columna utilizada":"Total (ARS); Costo Total (Con IVA) ($)", "Cálculo":"Utilidad preliminar = Total (ARS) ML oficial menos Costo Total (Con IVA) Eccomapp" if not falta_utilidad else "No calculada: falta " + ", ".join(falta_utilidad), "Filas de origen": f"ML {r.filas_origen_ml or '—'} · Eccomapp {r.filas_origen_eccomapp or '—'}"},
        {"Concepto":"Diferencia ML–MP", "Valor": formato_importe(r.diferencia_ml_mp), "Archivo de origen":"ML oficial + Mercado Pago", "Columna utilizada":"Total (ARS); MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO", "Cálculo":"Diferencia = Neto aprobado MP menos Total (ARS) ML oficial", "Filas de origen": f"ML {r.filas_origen_ml or '—'} · MP {r.filas_origen_mp or '—'}"},
    ]


def trazabilidad_tecnica(r: ResultadoControlConsolidado, tolerancia: Decimal, hashes: dict[str,str]) -> dict[str,str]:
    return {"Versión de regla": r.version_regla, "Motivos internos": "; ".join(r.motivos) or "—", "Hashes truncados": ", ".join(f"{k}:{v[:12]}" for k,v in hashes.items() if v), "Filas de origen": f"ML {r.filas_origen_ml}; Eccomapp {r.filas_origen_eccomapp}; MP {r.filas_origen_mp}", "Claves consumidas": f"Comercial {r.claves_resultados_comerciales}; Financiero {r.claves_resultados_financieros}", "Tolerancia": str(tolerancia)}
