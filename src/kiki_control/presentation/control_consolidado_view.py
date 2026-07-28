"""Transformaciones puras para presentar el control financiero consolidado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Any

from kiki_control.domain.control_consolidado import EstadoControlConsolidado, ReporteControlConsolidado, ResultadoControlConsolidado
from kiki_control.presentation.control_consolidado_diagnostics import DiagnosticoControlConsolidado, diagnosticar_control_consolidado, motivos_datos_criticos_faltantes, tiene_datos_criticos_faltantes
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.bloque_b_diagnostics import (
    DetalleMovimientoMp,
    DiagnosticoBloqueB,
    EstadoExplicacionDiferencia,
    ESTADOS_EXPLICACION_VISIBLES,
    GrupoConDiferencia,
    MovimientoMpSinVentaML,
)
from kiki_control.domain.financial_movement import TratamientoNetoComparable


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


TITULO_BLOQUE_A = "Bloque A — Formación del neto informado por Mercado Libre"
TITULO_BLOQUE_B = "Bloque B — Conciliación entre el neto ML y Mercado Pago"


def texto_rango_cobertura(minimo: str, maximo: str) -> str:
    """Devuelve una cobertura legible sin repetir la misma fecha."""
    if minimo == maximo:
        return minimo
    return f"{minimo} a {maximo}"


def filas_cobertura_presentacion(cobertura: Iterable[CoberturaFuente]) -> list[dict[str, str]]:
    """Transforma cobertura temporal en filas compactas para Streamlit."""
    return [
        {"Fuente": c.nombre, "Desde": c.minimo, "Hasta": c.maximo, "Observación": c.extra or "—"}
        for c in cobertura
    ]


def nombre_archivo_descarga(prefijo: str, fecha: str) -> str:
    """Construye nombres de descarga diferenciados y testeables."""
    return f"{prefijo}{fecha}.xlsx" if prefijo.endswith("_") else f"{prefijo}_{fecha}.xlsx"


def filas_bloque_a(reporte: ReporteControlConsolidado, diagnostico: DiagnosticoControlConsolidado | None = None) -> list[dict[str, str]]:
    diag = diagnostico or diagnosticar_control_consolidado(reporte)
    return [
        {
            "Concepto": componente.concepto,
            "Importe": formato_importe(componente.importe),
            "Origen": f"{componente.origen} · {componente.columna_origen}",
            "Método": componente.metodo,
        }
        for componente in diag.residual_ml.componentes
    ]


def auditoria_bloque_a(reporte: ReporteControlConsolidado, diagnostico: DiagnosticoControlConsolidado | None = None) -> list[dict[str, str]]:
    diag = diagnostico or diagnosticar_control_consolidado(reporte)
    return [
        {
            "Concepto": componente.concepto,
            "Importe": formato_importe(componente.importe),
            "Columna de origen": componente.columna_origen,
            "Método": componente.metodo,
            "Filas utilizadas": str(componente.filas_utilizadas),
            "Tolerancia": formato_importe(reporte.tolerancia),
            "Diferencia final": formato_importe(diag.residual_ml.diferencia_final),
        }
        for componente in diag.residual_ml.componentes
    ]


def mensaje_conciliacion_bloque_a(reporte: ReporteControlConsolidado, diagnostico: DiagnosticoControlConsolidado | None = None) -> str:
    diag = diagnostico or diagnosticar_control_consolidado(reporte)
    if abs(diag.residual_ml.diferencia_final) <= reporte.tolerancia:
        return "La conciliación cierra"
    return f"Queda una diferencia pendiente de clasificación de {formato_importe(diag.residual_ml.diferencia_final)}"


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
    motivo_principal: str = ""
    que_revisar: str = ""
    ids_orden: tuple[str, ...] = ()
    filas_origen_mp: tuple[int, ...] = ()



_ESTADOS_VISIBLES = {
    EstadoControlConsolidado.COMPLETA: "Completo",
    EstadoControlConsolidado.CON_DIFERENCIA: "Con diferencia",
    EstadoControlConsolidado.SIN_VENTA_OFICIAL: "Sin venta oficial",
    EstadoControlConsolidado.TOTAL_ML_AUSENTE: "Venta oficial sin Total (ARS)",
    EstadoControlConsolidado.SIN_COSTO_PRODUCTO: "Sin costo de producto",
    EstadoControlConsolidado.SIN_MOVIMIENTO_FINANCIERO: "Sin movimiento de Mercado Pago",
    EstadoControlConsolidado.SOLO_MOVIMIENTO_FINANCIERO: "Solo movimiento de Mercado Pago",
    EstadoControlConsolidado.EN_REVISION_FINANCIERA: "En revisión financiera",
    EstadoControlConsolidado.DUPLICADA_O_AMBIGUA: "Duplicado o ambiguo",
}

def estado_visible(estado: EstadoControlConsolidado | str) -> str:
    try:
        return _ESTADOS_VISIBLES[EstadoControlConsolidado(estado)]
    except Exception:
        return str(estado).replace("_", " ").capitalize()

def etiqueta_selector_detalle(f: FilaControlConsolidado) -> str:
    if f.ids_orden:
        return f"Orden {', '.join(f.ids_orden)} — {f.estado}"
    fila = f.filas_origen_mp[0] if f.filas_origen_mp else grupo_mp_visible_desde_clave(f.clave)
    return f"Movimiento MP sin orden — fila {fila}"

def grupo_mp_visible_desde_clave(clave: str) -> str:
    import re
    m = re.search(r"fila:?(\d+)|:(\d+)$", clave)
    return next((g for g in (m.groups() if m else ()) if g), "sin identificar")

def motivo_principal_visible(r: ResultadoControlConsolidado) -> str:
    motivos_criticos = motivos_datos_criticos_faltantes(r)
    if motivos_criticos:
        return "; ".join(motivos_criticos)
    if r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > r.tolerancia:
        return "Diferencia pendiente de clasificación contable"
    if not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago):
        return "Fuente faltante"
    if r.requiere_revision:
        return "Revisión del control consolidado"
    return "Sin motivo de revisión"

def que_revisar_visible(r: ResultadoControlConsolidado) -> str:
    motivo = motivo_principal_visible(r)
    if "Total (ARS)" in motivo or "Costo de producto" in motivo or "Sin neto aprobado" in motivo:
        return "Completar o revisar el dato crítico indicado sin mezclarlo con devoluciones, reclamos o movimientos de fondos."
    if motivo == "Diferencia pendiente de clasificación contable":
        return "Comparar Neto oficial ML, neto Eccomapp y neto aprobado MP sin asumir causa."
    if motivo == "Fuente faltante":
        return "Verificar cobertura de archivos y si el grupo pertenece al período cargado."
    if motivo == "Revisión del control consolidado":
        return "Revisar indicadores financieros y trazabilidad técnica."
    return "No requiere acción visible."

def formato_importe(valor: Decimal | None) -> str:
    if valor is None:
        return "No calculado"
    return formato_pesos_argentino(valor).replace("-$ ", "$ -")

def formato_fecha(valor: Any) -> str:
    if valor is None:
        return "Sin fecha"
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


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


def conclusion_ejecutiva_consolidada(reporte: ReporteControlConsolidado, diagnostico: Any | None = None) -> str:
    """Conclusión principal breve, sin recalcular valores del dominio."""
    diag = diagnostico or diagnosticar_control_consolidado(reporte)
    diferencias = diag.diferencias
    extra_total_ml = (
        f" {reporte.total_total_ml_ausente} venta oficial sin Total (ARS) requiere revisión monetaria."
        if reporte.total_total_ml_ausente
        else ""
    )
    return (
        f"{diferencias.coincidencias_dentro_tolerancia} de {diferencias.comparables_totales} grupos comparables coinciden dentro de la tolerancia. "
        f"{diferencias.con_diferencia_ml_mp} presentan diferencias por un total de {formato_importe(diferencias.suma_diferencia_ml_mp)}."
        f"{extra_total_ml}"
    )


def textos_secundarios_conclusion(reporte: ReporteControlConsolidado) -> tuple[str, ...]:
    calculables = sum(1 for r in reporte.resultados if r.utilidad_preliminar_control is not None)
    return (
        f"{reporte.total_resultados} grupos consolidados.",
        f"{reporte.total_requieren_revision} requieren revisión.",
        f"{reporte.total_total_ml_ausente} con venta oficial sin Total (ARS).",
        f"Utilidad preliminar calculable para {calculables} de {reporte.total_resultados} grupos.",
        "El resultado es operativo y no contable o fiscal definitivo.",
    )


def alcance_completo_consolidado(reporte: ReporteControlConsolidado, diagnostico: Any | None = None) -> str:
    diag = diagnostico or diagnosticar_control_consolidado(reporte)
    diferencias = diag.diferencias
    return (
        f"Se consolidaron {reporte.total_resultados} grupos. Estados principales: {reporte.total_completa} completos, "
        f"{reporte.total_con_diferencia} con estado principal con diferencia, {reporte.total_sin_venta_oficial} sin venta oficial, "
        f"{reporte.total_total_ml_ausente} venta oficial sin Total (ARS), {reporte.total_sin_costo_producto} sin costo de producto, "
        f"{reporte.total_sin_movimiento_financiero} sin movimiento MP, {reporte.total_solo_movimiento_financiero} solo movimientos financieros, "
        f"{reporte.total_en_revision_financiera} en revisión financiera y {reporte.total_duplicada_o_ambigua} duplicados o ambiguos. "
        f"En el universo ML–MP existen {diferencias.comparables_totales} grupos comparables: {diferencias.coincidencias_dentro_tolerancia} coinciden dentro de tolerancia y "
        f"{diferencias.con_diferencia_ml_mp} presentan diferencias por {formato_importe(diferencias.suma_diferencia_ml_mp)}. "
        "Los estados de cobertura y fuentes faltantes se informan por separado, sin sumar contadores de universos diferentes ni atribuir causas contables a la diferencia. "
        "Estos importes son informados por la fuente y no constituyen resultado contable o fiscal definitivo."
    )


def kpis_consolidados(reporte: ReporteControlConsolidado) -> dict[str, list[Kpi]]:
    resultados = reporte.resultados
    comparables = [r for r in resultados if r.total_informado_ml is not None and r.neto_financiero_total_mp is not None]
    utilidad_calc = [r for r in resultados if r.utilidad_preliminar_control is not None]
    ayuda_limite = " Limitación: control operativo preliminar, no es resultado contable o fiscal definitivo."
    return {
        "Bloque A — Importes informados por ML oficial": [
            Kpi("Ventas ML oficial", formato_importe(_sumar(r.monto_venta_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: monto_venta_ml. Columna externa: Ingresos por productos (ARS). Universo: resultados consolidados con venta oficial." + ayuda_limite),
            Kpi("Cargos e impuestos ML", formato_importe(_sumar(r.cargo_venta_impuestos_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: cargo_venta_impuestos_ml. Columna externa: Cargo por venta e impuestos (ARS). Universo: resultados con venta oficial." + ayuda_limite),
            Kpi("Costo de envío ML", formato_importe(_sumar(r.costo_envio_ml for r in resultados)), "Fuente: archivo oficial de Mercado Libre. Campo interno: costo_envio_ml. Columna utilizada: Costos de envío (ARS). Universo: resultados con venta oficial. Informado directamente por la fuente." + ayuda_limite),
            Kpi("Neto esperado ML", formato_importe(_sumar(r.total_informado_ml for r in resultados)), "Fuente: Mercado Libre oficial. Campo interno: total_informado_ml. Columna externa: Total (ARS). Universo: resultados con venta oficial. Fórmula: no se reconstruye; se usa el total informado." + ayuda_limite),
        ],
        "Bloque B — Comparación financiera": [
            Kpi("Neto ML comparable", formato_importe(_sumar(r.total_informado_ml for r in comparables)), "Fuente: Mercado Libre oficial. Campo interno: total_informado_ml. Columna utilizada: Total (ARS). Universo: solo resultados donde también existe neto_aprobado_mp. Informado directamente por la fuente." + ayuda_limite),
            Kpi("Neto financiero total MP comparable", formato_importe(_sumar(r.neto_financiero_total_mp for r in comparables)), "Fuente: Mercado Pago. Campo: neto_financiero_total_mp. Suma algebraicamente pagos, reclamos, devoluciones, envíos y otros impactos. Universo: mismos resultados comparables con ML." + ayuda_limite),
            Kpi("Grupos con diferencia", str(diagnosticar_control_consolidado(reporte).diferencias.con_diferencia_ml_mp), "Cuenta resultados comparables donde Total (ARS) ML y neto financiero total MP existen y abs(diferencia_ml_mp) supera la tolerancia. No usa total_con_diferencia porque ese es un estado principal." + ayuda_limite),
            Kpi("Diferencia total", formato_importe(diagnosticar_control_consolidado(reporte).diferencias.suma_diferencia_ml_mp), "Identidad validada: suma_diferencia_ml_mp = suma_neto_mp_comparable - suma_neto_ml_comparable." + ayuda_limite),
            Kpi("Neto MP sin venta ML", formato_importe(_sumar(r.neto_aprobado_mp for r in resultados if r.neto_aprobado_mp is not None and not r.tiene_mercado_libre_oficial)), "Fuente: Mercado Pago. Universo: movimientos no encontrados en el archivo de ventas oficiales cargado." + ayuda_limite),
        ],
        "Bloque C — Costos y utilidad": [
            Kpi("Costo de productos Eccomapp", formato_importe(_sumar(r.costo_productos_eccomapp for r in resultados)), "Fuente: Eccomapp. Campo: costo_productos_eccomapp. Columna: Costo Total (Con IVA) ($). Universo: resultados con Eccomapp." + ayuda_limite),
            Kpi("Utilidad preliminar calculable", formato_importe(_sumar(r.utilidad_preliminar_control for r in utilidad_calc)), "Fórmula: Total (ARS) ML oficial menos Costo Total (Con IVA) Eccomapp, solo donde ambos existen." + ayuda_limite),
            Kpi("Cobertura de utilidad", f"{len(utilidad_calc)} de {len(resultados)}", "Universo: grupos consolidados. Requiere Total (ARS) válido de ML oficial y Costo Total (Con IVA) ($) de Eccomapp; la sola presencia de ambas fuentes no alcanza." + ayuda_limite),
        ],
        "Bloque D — Calidad y pendientes": [
            Kpi("Resultados completos", str(reporte.total_completa), "Resultados con fuentes y comparaciones suficientes según el dominio."),
            Kpi("Requieren revisión", str(reporte.total_requieren_revision), "Resultados marcados por el dominio como requiere_revision."),
            Kpi("Venta oficial sin Total (ARS)", str(reporte.total_total_ml_ausente), "Resultados con venta oficial ML presente pero sin Total (ARS), por lo que no se calculan diferencia ML–MP ni utilidad preliminar."),
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
        minimo = min(fechas)
        maximo = max(fechas)
        if hasattr(minimo, "date"):
            minimo = minimo.date()
        if hasattr(maximo, "date"):
            maximo = maximo.date()
        return (formato_fecha(minimo), formato_fecha(maximo))
    movs = tuple(movimientos)
    sin_liq = sum(1 for m in movs if getattr(m, "fecha_liquidacion_local", None) is None)
    return (
        CoberturaFuente("Ventas oficiales ML", *rango(tuple(ventas_ml), "fecha_venta")),
        CoberturaFuente("Ventas/costos Eccomapp", *rango(tuple(operaciones), "fecha_hora_venta")),
        CoberturaFuente("Origen de movimientos MP", *rango(movs, "fecha_origen_local")),
        CoberturaFuente("Liquidaciones MP", *rango(movs, "fecha_liquidacion_local"), f"{sin_liq} movimientos sin fecha de liquidación"),
    )


def advertir_periodos_distintos(cobertura: tuple[CoberturaFuente, ...]) -> bool:
    """Compara solo períodos de origen: ML oficial, Eccomapp y origen MP.

    Las liquidaciones MP pueden ocurrir más tarde y no deben disparar esta advertencia por sí solas.
    """
    nombres_origen = {"Ventas oficiales ML", "Ventas/costos Eccomapp", "Origen de movimientos MP"}
    rangos = {(c.minimo, c.maximo) for c in cobertura if c.nombre in nombres_origen and c.minimo != "Sin fechas"}
    return len(rangos) > 1


def grupo_visible(r: ResultadoControlConsolidado) -> str:
    if r.id_grupo_canonico:
        return r.id_grupo_canonico
    if r.ids_orden:
        return ", ".join(r.ids_orden)
    if r.filas_origen_mp:
        return f"fila MP {', '.join(str(n) for n in r.filas_origen_mp)}"
    return r.clave_resultado


def filas_tabla_consolidada(resultados: Iterable[ResultadoControlConsolidado]) -> list[FilaControlConsolidado]:
    filas=[]
    for r in resultados:
        faltan = not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago)
        filas.append(FilaControlConsolidado(
            r.clave_resultado,
            grupo_visible(r),
            estado_visible(r.estado),
            r.estado.value,
            fuentes_disponibles(r),
            formato_importe(r.monto_venta_ml),
            formato_importe(r.cargo_venta_impuestos_ml),
            formato_importe(r.costo_envio_ml),
            formato_importe(r.total_informado_ml),
            formato_importe(r.costo_productos_eccomapp),
            formato_importe(r.neto_aprobado_mp),
            formato_importe(r.neto_financiero_total_mp),
            formato_importe(r.diferencia_ml_mp),
            formato_importe(r.utilidad_preliminar_control),
            "Sí" if r.requiere_revision else "No",
            r.diferencia_ml_mp is not None and abs(r.diferencia_ml_mp) > r.tolerancia,
            faltan or tiene_datos_criticos_faltantes(r),
            motivo_principal_visible(r),
            que_revisar_visible(r),
            r.ids_orden,
            r.filas_origen_mp,
        ))
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
    return [f.__dict__ | {"Grupo u orden": f.grupo_orden, "Estado": f.estado, "Fuentes disponibles": f.fuentes_disponibles, "Venta ML oficial": f.venta_ml_oficial, "Cargos e impuestos ML": f.cargos_impuestos_ml, "Costo envío ML": f.costo_envio_ml, "Neto esperado ML": f.neto_esperado_ml, "Costo productos": f.costo_productos, "Neto aprobado MP": f.neto_aprobado_mp, "Neto financiero total MP": f.neto_financiero_total_mp, "Diferencia ML–MP": f.diferencia_ml_mp, "Utilidad preliminar": f.utilidad_preliminar, "Requiere revisión": f.requiere_revision, "Motivo principal": f.motivo_principal, "Qué revisar": f.que_revisar} for f in filas]



def motivos_disponibles(valores: Iterable[Any]) -> tuple[str, ...]:
    """Devuelve motivos visibles únicos en orden determinista para filtros de presentación."""
    return tuple(sorted({str(getattr(v, "motivo", getattr(v, "motivo_visible", v))) for v in valores if str(getattr(v, "motivo", getattr(v, "motivo_visible", v))).strip()}))


def contar_mostrando(visibles: Iterable[Any], total: Iterable[Any] | int) -> str:
    cantidad_visible = len(tuple(visibles))
    cantidad_total = total if isinstance(total, int) else len(tuple(total))
    return f"Mostrando {cantidad_visible} de {cantidad_total} grupos"


def filtrar_grupos_excluidos(grupos: Iterable[Any], busqueda_grupo: str = "", motivo: str = "") -> tuple[Any, ...]:
    q = (busqueda_grupo or "").strip().lower()
    m = (motivo or "").strip()
    salida = []
    for grupo in grupos:
        grupo_visible_valor = str(getattr(grupo, "grupo", ""))
        motivo_valor = str(getattr(grupo, "motivo", ""))
        if q and q not in grupo_visible_valor.lower():
            continue
        if m and motivo_valor != m:
            continue
        salida.append(grupo)
    return tuple(salida)


def filas_grupos_excluidos(grupos: Iterable[Any]) -> list[dict[str, str]]:
    return [{
        "Grupo": g.grupo,
        "Motivo": g.motivo,
        "Neto ML": formato_importe(g.neto_ml),
        "Neto Eccomapp": formato_importe(g.neto_eccomapp),
        "Neto aprobado MP": formato_importe(g.neto_aprobado_mp),
        "Aporte MP–ML": formato_importe(g.aporte_diferencia_ml_mp),
    } for g in grupos]


def filas_resumen_revisiones(revisiones: Iterable[Any]) -> list[dict[str, str | int]]:
    return [{
        "Motivo visible": r.motivo_visible,
        "Cantidad": r.cantidad,
        "Importe afectado": formato_importe(r.importe_afectado),
        "Acción recomendada": r.accion_recomendada,
    } for r in revisiones]


def filtrar_grupos_involucrados_por_motivo(revisiones: Iterable[Any], motivo: str, busqueda_grupo: str = "") -> tuple[str, ...]:
    q = (busqueda_grupo or "").strip().lower()
    grupos: tuple[str, ...] = ()
    for revision in revisiones:
        if revision.motivo_visible == motivo:
            grupos = revision.grupos_involucrados
            break
    return tuple(g for g in grupos if not q or q in g.lower())


def filas_grupos_involucrados(grupos: Iterable[str]) -> list[dict[str, str]]:
    return [{"Grupo": grupo} for grupo in grupos]

def detalle_control(r: ResultadoControlConsolidado) -> dict[str, str]:
    return {
        "Grupo": grupo_visible(r),
        "Órdenes": ", ".join(r.ids_orden) or "No informado",
        "Estado": estado_visible(r.estado),
        "Fuentes presentes": fuentes_disponibles(r),
        "Venta ML oficial": formato_importe(r.monto_venta_ml),
        "Cargos e impuestos ML": formato_importe(r.cargo_venta_impuestos_ml),
        "Costo de envío ML": formato_importe(r.costo_envio_ml),
        "Neto esperado ML": formato_importe(r.total_informado_ml),
        "Costo productos": formato_importe(r.costo_productos_eccomapp),
        "Neto aprobado MP": formato_importe(r.neto_aprobado_mp),
        "Neto financiero total MP": formato_importe(r.neto_financiero_total_mp),
        "Diferencia ML–MP": formato_importe(r.diferencia_ml_mp),
        "Utilidad preliminar": formato_importe(r.utilidad_preliminar_control),
        "Requiere revisión": "Sí" if r.requiere_revision else "No",
        "Explicación": "; ".join(r.explicaciones) or "Resultado informado por las fuentes cargadas; requiere revisión si hay datos faltantes o diferencias.",
    }


def _filas(*grupos: tuple[int, ...]) -> str:
    partes = []
    for nombre, valores in grupos:
        partes.append(f"{nombre} {valores or '—'}")
    return " · ".join(partes)


def _motivo_no_calculado(valor: Decimal | None, faltantes: tuple[str, ...] = ()) -> str:
    if valor is not None:
        return ""
    return "No calculado: falta " + (", ".join(faltantes) if faltantes else "fuente o campo requerido")


def explicacion_resultado(r: ResultadoControlConsolidado) -> list[dict[str, str]]:
    prudencia = "Control operativo preliminar; no es resultado contable o fiscal definitivo."
    return [
        {
            "Concepto": "Venta ML oficial",
            "Valor": formato_importe(r.monto_venta_ml),
            "Archivo de origen": "Ventas oficiales de Mercado Libre",
            "Columna utilizada": "Ingresos por productos (ARS)",
            "Regla aplicada": "Importe informado directamente por la fuente." if r.monto_venta_ml is not None else _motivo_no_calculado(r.monto_venta_ml, ("Mercado Libre oficial / Ingresos por productos (ARS)",)),
            "Filas de origen": _filas(("ML", r.filas_origen_ml)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Cargos e impuestos ML",
            "Valor": formato_importe(r.cargo_venta_impuestos_ml),
            "Archivo de origen": "Ventas oficiales de Mercado Libre",
            "Columna utilizada": "Cargo por venta e impuestos (ARS)",
            "Regla aplicada": "Importe informado directamente por la fuente." if r.cargo_venta_impuestos_ml is not None else _motivo_no_calculado(r.cargo_venta_impuestos_ml, ("Mercado Libre oficial / Cargo por venta e impuestos (ARS)",)),
            "Filas de origen": _filas(("ML", r.filas_origen_ml)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Costo de envío ML",
            "Valor": formato_importe(r.costo_envio_ml),
            "Archivo de origen": "Ventas oficiales de Mercado Libre",
            "Columna utilizada": "Costos de envío (ARS)",
            "Regla aplicada": "Importe informado directamente por la fuente." if r.costo_envio_ml is not None else _motivo_no_calculado(r.costo_envio_ml, ("Mercado Libre oficial / Costos de envío (ARS)",)),
            "Filas de origen": _filas(("ML", r.filas_origen_ml)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Neto esperado ML",
            "Valor": formato_importe(r.total_informado_ml),
            "Archivo de origen": "Ventas oficiales de Mercado Libre",
            "Columna utilizada": "Total (ARS)",
            "Regla aplicada": "Usado tal como lo informa la fuente; no se reconstruye en presentación." if r.total_informado_ml is not None else _motivo_no_calculado(r.total_informado_ml, ("Mercado Libre oficial / Total (ARS)",)),
            "Filas de origen": _filas(("ML", r.filas_origen_ml)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Costo de productos",
            "Valor": formato_importe(r.costo_productos_eccomapp),
            "Archivo de origen": "Eccomapp",
            "Columna utilizada": "Costo Total (Con IVA) ($)",
            "Regla aplicada": "Importe informado por Eccomapp y consumido por el dominio." if r.costo_productos_eccomapp is not None else _motivo_no_calculado(r.costo_productos_eccomapp, ("Eccomapp / Costo Total (Con IVA) ($)",)),
            "Filas de origen": _filas(("Eccomapp", r.filas_origen_eccomapp)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Neto aprobado MP",
            "Valor": formato_importe(r.neto_aprobado_mp),
            "Archivo de origen": "Mercado Pago",
            "Columna utilizada": "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
            "Regla aplicada": "Agrupado según las reglas del motor de conciliación." if r.neto_aprobado_mp is not None else _motivo_no_calculado(r.neto_aprobado_mp, ("Mercado Pago / movimiento aprobado",)),
            "Filas de origen": _filas(("MP", r.filas_origen_mp)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Diferencia ML–MP",
            "Valor": formato_importe(r.diferencia_ml_mp),
            "Archivo de origen": "Mercado Libre oficial + Mercado Pago",
            "Columna utilizada": "Total (ARS); MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO",
            "Regla aplicada": "neto_financiero_total_mp - total_informado_ml" if r.diferencia_ml_mp is not None else _motivo_no_calculado(r.diferencia_ml_mp, ("neto_financiero_total_mp", "total_informado_ml")),
            "Filas de origen": _filas(("ML", r.filas_origen_ml), ("MP", r.filas_origen_mp)),
            "Limitación": prudencia,
        },
        {
            "Concepto": "Utilidad preliminar",
            "Valor": formato_importe(r.utilidad_preliminar_control),
            "Archivo de origen": "Mercado Libre oficial + Eccomapp",
            "Columna utilizada": "Total (ARS); Costo Total (Con IVA) ($)",
            "Regla aplicada": "total_informado_ml - costo_productos_eccomapp" if r.utilidad_preliminar_control is not None else _motivo_no_calculado(r.utilidad_preliminar_control, ("total_informado_ml", "costo_productos_eccomapp")),
            "Filas de origen": _filas(("ML", r.filas_origen_ml), ("Eccomapp", r.filas_origen_eccomapp)),
            "Limitación": prudencia,
        },
    ]

def trazabilidad_tecnica(r: ResultadoControlConsolidado, tolerancia: Decimal, hashes: dict[str,str]) -> dict[str,str]:
    return {"Versión de regla": r.version_regla, "Motivos internos": "; ".join(r.motivos) or "—", "Hashes truncados": ", ".join(f"{k}:{v[:12]}" for k,v in hashes.items() if v), "Filas de origen": f"ML {r.filas_origen_ml}; Eccomapp {r.filas_origen_eccomapp}; MP {r.filas_origen_mp}", "Claves consumidas": f"Comercial {r.claves_resultados_comerciales}; Financiero {r.claves_resultados_financieros}", "Tolerancia": str(tolerancia)}


# ---------------------------------------------------------------------------
# Bloque B — Conciliación entre el neto ML y Mercado Pago
# ---------------------------------------------------------------------------

CONVENCION_DIFERENCIA_ML_MP = (
    "Convención: diferencia_ml_mp = neto_financiero_total_mp − total_informado_ml. "
    "Neto financiero total MP = pagos aprobados + reclamos/disputas + devoluciones + otros impactos independientes; "
    "PAGO_ENVIO se muestra como componente ya incluido y no se suma nuevamente. "
    "Positiva: Mercado Pago informa más neto que Mercado Libre. "
    "Negativa: Mercado Pago informa menos neto que Mercado Libre."
)

TEXTO_COBERTURA_FECHAS_MP = (
    "Mercado Libre y Eccomapp informan ventas ocurridas en el período seleccionado. "
    "Mercado Pago también incluye movimientos originados en días anteriores y liquidaciones futuras. "
    "Por eso las fechas de origen y liquidación no deben compararse directamente como si fueran fechas de venta."
)


def resumen_bloque_b_tabla(diag: DiagnosticoBloqueB) -> list[dict[str, str]]:
    """Devuelve filas compactas para el resumen de Bloque B."""
    r = diag.resumen
    return [
        {"Indicador": "Grupos comparables", "Valor": str(r.comparables_totales)},
        {"Indicador": "Coinciden dentro de tolerancia", "Valor": str(r.coincidencias)},
        {"Indicador": "Grupos con diferencia", "Valor": str(r.con_diferencia)},
        {"Indicador": "Neto ML comparable", "Valor": formato_importe(r.neto_ml_comparable)},
        {"Indicador": "Neto financiero total MP comparable", "Valor": formato_importe(r.neto_mp_comparable)},
        {"Indicador": "Diferencia universo comparable (MP − ML)", "Valor": formato_importe(r.diferencia_universo_comparable)},
        {"Indicador": "Diferencia operaciones fuera de tolerancia", "Valor": formato_importe(r.diferencia_operaciones_fuera_tolerancia)},
        {"Indicador": "Diferencia subuniverso conciliado (dentro de tolerancia)", "Valor": formato_importe(r.diferencia_subuniverso_conciliado)},
    ]


def filas_grupos_con_diferencia(grupos: Iterable[GrupoConDiferencia]) -> list[dict[str, Any]]:
    """Transforma grupos con diferencia en filas de presentación."""
    return [
        {
            "ID de grupo u orden": g.id_grupo,
            "Fecha de venta ML": g.fecha_venta_ml,
            "Neto informado ML": formato_importe(g.total_informado_ml),
            "Neto aprobado MP": formato_importe(g.neto_aprobado_mp),
            "Reclamos/disputas MP": formato_importe(g.impacto_reclamos_disputas_mp),
            "Devoluciones MP": formato_importe(g.impacto_devoluciones_mp),
            "Envíos MP (incluidos; no se resuman)": formato_importe(g.impacto_pagos_envio_mp),
            "Otros impactos MP": formato_importe(g.impacto_otros_mp),
            "Neto financiero total MP": formato_importe(g.neto_financiero_total_mp),
            "Diferencia MP − ML": formato_importe(g.diferencia_ml_mp),
            "Movimientos MP": g.cantidad_movimientos_mp,
            "Origen MP desde": g.fecha_min_origen_mp,
            "Origen MP hasta": g.fecha_max_origen_mp,
            "Liquidación desde": g.fecha_min_liquidacion,
            "Liquidación hasta": g.fecha_max_liquidacion,
            "Tipos de movimientos": ", ".join(g.tipos_movimientos),
            "Estado de explicación": ESTADOS_EXPLICACION_VISIBLES.get(g.estado_explicacion, g.estado_explicacion),
            "Motivo": g.motivo_visible,
            "Acción recomendada": g.accion_recomendada,
        }
        for g in grupos
    ]


def filas_mp_sin_venta(movs: Iterable[MovimientoMpSinVentaML]) -> list[dict[str, Any]]:
    """Transforma movimientos MP sin venta ML en filas de presentación."""
    return [
        {
            "ID de grupo u orden": m.id_grupo,
            "IDs de movimiento MP": ", ".join(m.ids_movimiento_mp) if m.ids_movimiento_mp else "—",
            "Subclasificación financiera": m.subclasificacion_financiera.value,
            "Tipos de movimiento": ", ".join(m.tipos_movimiento),
            "Tiene ID de orden": "Sí" if m.tiene_id_orden_utilizable else "No",
            "Fecha de origen desde": m.fecha_min_origen,
            "Fecha de origen hasta": m.fecha_origen_maxima,
            "Fecha de liquidación desde": m.fecha_liquidacion_minima,
            "Fecha de liquidación hasta": m.fecha_max_liquidacion,
            "Neto aprobado bruto MP": formato_importe(m.neto_aprobado_mp),
            "Neto financiero total MP": formato_importe(m.neto_financiero_total_mp),
            "Cantidad de movimientos": m.cantidad_movimientos,
            "Categoría temporal principal": m.categoria_principal.value,
            "Motivo visible": m.motivo_sin_venta,
            "Acción recomendada": m.accion_recomendada,
            "Filas de origen MP": ", ".join(map(str, m.filas_origen_mp)),
        }
        for m in movs
    ]


def filtrar_mp_sin_venta(
    movs: Iterable[MovimientoMpSinVentaML],
    busqueda_id: str = "",
    filtro_tipo: str = "",
    filtro_categoria: str = "",
    filtro_subclasificacion: str = "",
    filtro_id_orden: str = "",
    solo_prioritarios: bool = False,
) -> tuple[MovimientoMpSinVentaML, ...]:
    """Filtra movimientos MP sin venta ML por ID, tipo y categoría temporal."""
    q_id = (busqueda_id or "").strip().lower()
    q_tipo = (filtro_tipo or "").strip()
    q_cat = (filtro_categoria or "").strip()
    result = []
    for m in movs:
        if q_id and q_id not in m.id_grupo.lower():
            continue
        if q_tipo and q_tipo not in ", ".join(m.tipos_movimiento):
            continue
        if q_cat and q_cat not in {m.categoria_temporal, m.categoria_principal.value}:
            continue
        if filtro_subclasificacion and filtro_subclasificacion != m.subclasificacion_financiera.value:
            continue
        if filtro_id_orden == "Con ID" and not m.tiene_id_orden_utilizable:
            continue
        if filtro_id_orden == "Sin ID" and m.tiene_id_orden_utilizable:
            continue
        if solo_prioritarios and not (
            m.categoria_principal.value in {"DENTRO_DEL_PERIODO_ML_SIN_VENTA", "SIN_FECHA_DE_ORIGEN"}
            or m.subclasificacion_financiera.value == "OTRO_MOVIMIENTO"
        ):
            continue
        result.append(m)
    return tuple(result)


def filas_resumen_mp_sin_venta(diag: DiagnosticoBloqueB) -> list[dict[str, Any]]:
    return [{
        "Categoría": r.categoria.value,
        "Cantidad de grupos": r.cantidad_grupos,
        "Cantidad de movimientos": r.cantidad_movimientos,
        "Neto aprobado bruto": formato_importe(r.neto_aprobado_bruto),
        "Neto financiero total": formato_importe(r.neto_financiero_total),
        "Con ID de orden": r.con_id_orden,
        "Sin ID de orden": r.sin_id_orden,
        "Acción recomendada": r.accion_recomendada,
    } for r in diag.resumen_mp_sin_venta]


def filas_movimientos_diferencia(grupo: GrupoConDiferencia) -> list[dict[str, Any]]:
    """Devuelve una fila por cada movimiento MP individual asociado a un grupo con diferencia."""
    return [_fila_movimiento_mp(m) for m in grupo.movimientos_asociados]


def _fila_movimiento_mp(m: Any) -> dict[str, Any]:
    return {
            "ID movimiento MP": m.id_movimiento_mp,
            "ID orden": m.id_orden,
            "Tipo de movimiento": m.tipo_movimiento,
            "Clasificación normalizada": m.clasificacion_normalizada,
            "Tratamiento en neto comparable": texto_tratamiento_neto_comparable(m.tratamiento_neto_comparable),
            "Fecha de origen": m.fecha_origen,
            "Fecha de aprobación": m.fecha_aprobacion,
            "Fecha de liquidación": m.fecha_liquidacion,
            "Monto neto impactado": formato_importe(m.monto_neto_impactado),
            "Fila de origen": m.fila_origen,
        }


def texto_tratamiento_neto_comparable(
    tratamiento: TratamientoNetoComparable | None,
) -> str:
    """Traduce la semántica tipada del dominio a una etiqueta visible."""
    etiquetas = {
        TratamientoNetoComparable.COMPONENTE_YA_INCLUIDO: "Componente ya incluido; no se suma nuevamente",
        TratamientoNetoComparable.MOVIMIENTO_DE_FONDOS: "Movimiento de fondos separado",
        TratamientoNetoComparable.MODIFICA_NETO_COMPARABLE: "Modifica el neto comparable",
    }
    return etiquetas.get(tratamiento, "Sin tratamiento informado")


def filas_movimientos_bloque_b(diag: DiagnosticoBloqueB) -> list[dict[str, Any]]:
    """Lista todo movimiento individual y explicita si afecta el neto comparable."""
    filas: list[dict[str, Any]] = []
    for id_grupo, movimientos in diag.grupos_movimientos_asociados:
        for movimiento in movimientos:
            filas.append({"ID de grupo": id_grupo, **_fila_movimiento_mp(movimiento)})
    return filas


def filas_fondos_mp(movs: Iterable[MovimientoMpSinVentaML]) -> list[dict[str, Any]]:
    """Transforma movimientos de fondos/payouts MP en filas de presentación."""
    return filas_mp_sin_venta(movs)


def detalle_diferencia_ml(r: ResultadoControlConsolidado) -> list[dict[str, str]]:
    """Detalle de los datos ML para una operación con diferencia."""
    return [
        {"Concepto": "ID de venta o grupo", "Valor": ", ".join(r.ids_orden) if r.ids_orden else r.clave_resultado},
        {"Concepto": "Ingresos por productos (ARS)", "Valor": formato_importe(r.monto_venta_ml)},
        {"Concepto": "Ingresos por envío (ARS)", "Valor": formato_importe(r.ingresos_envio_ml)},
        {"Concepto": "Cargos e impuestos (ARS)", "Valor": formato_importe(r.cargo_venta_impuestos_ml)},
        {"Concepto": "Costos de envío (ARS)", "Valor": formato_importe(r.costo_envio_ml)},
        {"Concepto": "Anulaciones y reembolsos (ARS)", "Valor": formato_importe(r.anulaciones_reembolsos_ml)},
        {"Concepto": "Descuentos informados (ARS)", "Valor": formato_importe(r.descuentos_bonificaciones_ml)},
        {"Concepto": "Total informado (ARS)", "Valor": formato_importe(r.total_informado_ml)},
        {"Concepto": "Filas de origen ML", "Valor": ", ".join(map(str, r.filas_origen_ml)) or "—"},
    ]


def detalle_diferencia_mp(r: ResultadoControlConsolidado) -> list[dict[str, str]]:
    """Detalle de los datos MP para una operación con diferencia."""
    return [
        {"Concepto": "ID de orden", "Valor": ", ".join(r.ids_orden) if r.ids_orden else "—"},
        {"Concepto": "Neto aprobado bruto MP", "Valor": formato_importe(r.neto_aprobado_mp)},
        {"Concepto": "Neto financiero total MP", "Valor": formato_importe(r.neto_financiero_total_mp)},
        {"Concepto": "Pagos de envío MP (ya incluidos; no se resuman)", "Valor": formato_importe(r.impacto_pagos_envio_mp)},
        {"Concepto": "Devoluciones MP", "Valor": formato_importe(r.impacto_devoluciones_mp)},
        {"Concepto": "Reclamos o disputas MP", "Valor": formato_importe(r.impacto_reclamos_disputas_mp)},
        {"Concepto": "Otros impactos MP", "Valor": formato_importe(r.impacto_otros_mp)},
        {"Concepto": "Filas de origen MP", "Valor": ", ".join(map(str, r.filas_origen_mp)) or "—"},
    ]


def detalle_conciliacion_diferencia(r: ResultadoControlConsolidado) -> list[dict[str, str]]:
    """Tabla de construcción de la conciliación para una operación con diferencia."""
    return [
        {"Concepto": "Neto informado ML", "Valor": formato_importe(r.total_informado_ml), "Origen": "ML oficial — Total (ARS)"},
        {"Concepto": "Neto aprobado bruto MP", "Valor": formato_importe(r.neto_aprobado_mp), "Origen": "MP — pagos aprobados"},
        {"Concepto": "Devoluciones observadas", "Valor": formato_importe(r.impacto_devoluciones_mp), "Origen": "MP — impacto_devoluciones"},
        {"Concepto": "Reclamos/disputas observados", "Valor": formato_importe(r.impacto_reclamos_disputas_mp), "Origen": "MP — impacto_reclamos_disputas"},
        {"Concepto": "Envíos observados (ya incluidos; no se resuman)", "Valor": formato_importe(r.impacto_pagos_envio_mp), "Origen": "MP — componente informativo del pago aprobado"},
        {"Concepto": "Otros impactos observados", "Valor": formato_importe(r.impacto_otros_mp), "Origen": "MP — impacto_otros"},
        {"Concepto": "Neto financiero total MP", "Valor": formato_importe(r.neto_financiero_total_mp), "Origen": "Pago aprobado + movimientos que modifican el neto; excluye PAGO_ENVIO ya incluido y PAYOUT"},
        {"Concepto": "Diferencia financiera MP − ML", "Valor": formato_importe(r.diferencia_ml_mp), "Origen": "Calculado: neto_financiero_total_mp − total_informado_ml"},
    ]


def texto_universo_comparable(diag_bloque_b: DiagnosticoBloqueB) -> str:
    """Texto explícito del universo comparable para evitar la contradicción del puente."""
    r = diag_bloque_b.resumen
    return (
        f"Las {r.coincidencias} operaciones conciliadas cierran dentro de la tolerancia "
        f"(diferencia agregada del subuniverso conciliado: {formato_importe(r.diferencia_subuniverso_conciliado)}). "
        f"Quedan {r.con_diferencia} operaciones por analizar, "
        f"con una diferencia total fuera de tolerancia de {formato_importe(r.diferencia_operaciones_fuera_tolerancia)}."
    )


def texto_universo_comparable_puente(diag_bloque_b: DiagnosticoBloqueB, universo_triple: int) -> str:
    """Texto explícito del puente diferenciando el universo triple del comparable."""
    r = diag_bloque_b.resumen
    return (
        f"Universo comparable total (ML + MP): {r.comparables_totales} grupos "
        f"({r.coincidencias} coincidentes y {r.con_diferencia} con diferencia, "
        f"diferencia universo comparable {formato_importe(r.diferencia_universo_comparable)}, "
        f"de los cuales {formato_importe(r.diferencia_operaciones_fuera_tolerancia)} corresponden a operaciones fuera de tolerancia). "
        f"Universo del puente triple (ML + Eccomapp + MP): {universo_triple} grupos."
    )
