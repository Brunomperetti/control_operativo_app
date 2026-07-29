"""Reconocimiento temporal y selección de universos de las cuatro fuentes."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from kiki_control.domain.account_statement import ResumenEstadoCuentaMp


class EstadoReconocimiento(StrEnum):
    LISTO_PARA_ANALIZAR = "LISTO_PARA_ANALIZAR"
    COBERTURA_PARCIAL = "COBERTURA_PARCIAL"
    PERIODOS_INCOMPATIBLES = "PERIODOS_INCOMPATIBLES"
    ARCHIVO_SIN_FECHAS_VALIDAS = "ARCHIVO_SIN_FECHAS_VALIDAS"
    SIN_DATOS_EN_COMUN = "SIN_DATOS_EN_COMUN"
    ESTRUCTURA_INVALIDA = "ESTRUCTURA_INVALIDA"
    PENDIENTE_DE_VALIDACION_POR_IDS = "PENDIENTE_DE_VALIDACION_POR_IDS"


ETIQUETAS_ESTADO = {
    EstadoReconocimiento.LISTO_PARA_ANALIZAR: "Listo para analizar",
    EstadoReconocimiento.COBERTURA_PARCIAL: "Cobertura parcial",
    EstadoReconocimiento.PERIODOS_INCOMPATIBLES: "Períodos incompatibles",
    EstadoReconocimiento.ARCHIVO_SIN_FECHAS_VALIDAS: "Archivo sin fechas válidas",
    EstadoReconocimiento.SIN_DATOS_EN_COMUN: "No hay datos en común",
    EstadoReconocimiento.ESTRUCTURA_INVALIDA: "Estructura inválida",
    EstadoReconocimiento.PENDIENTE_DE_VALIDACION_POR_IDS: "Pendiente de validación por IDs",
}


class TipoSeleccionPeriodo(StrEnum):
    AYER = "Ayer"
    ULTIMOS_3_DIAS = "Últimos 3 días"
    ULTIMOS_7_DIAS = "Últimos 7 días"
    TODO_DISPONIBLE = "Todo el período disponible"
    PERSONALIZADO = "Rango personalizado"


@dataclass(frozen=True)
class PeriodoAnalisis:
    fecha_desde: date
    fecha_hasta: date
    zona_horaria: str
    tipo_seleccion: TipoSeleccionPeriodo

    def __post_init__(self) -> None:
        if self.fecha_desde > self.fecha_hasta:
            raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")


@dataclass(frozen=True)
class CoberturaTemporalFuente:
    fuente: str
    tipo_fecha: str
    fecha_desde: date | None
    fecha_hasta: date | None
    cantidad_registros: int
    cantidad_ids: int
    fechas_faltantes: int
    estado: EstadoReconocimiento
    observaciones: str


@dataclass(frozen=True)
class ReconocimientoCuatroFuentes:
    coberturas: tuple[CoberturaTemporalFuente, ...]
    periodo_b1_disponible: tuple[date, date] | None
    periodo_b2_b3_disponible: tuple[date, date] | None
    estado_b1: EstadoReconocimiento
    estado_b2_b3: EstadoReconocimiento
    advertencias: tuple[str, ...]

    def filas_tabla(self) -> list[dict[str, object]]:
        return [{"Fuente": c.fuente, "Tipo de fecha": c.tipo_fecha,
                 "Fecha desde": c.fecha_desde, "Fecha hasta": c.fecha_hasta,
                 "Registros": c.cantidad_registros, "IDs únicos": c.cantidad_ids,
                 "Estado": ETIQUETAS_ESTADO[c.estado], "Observación": c.observaciones}
                for c in self.coberturas]


def _fecha(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


def cobertura(fuente: str, tipo: str, registros: Sequence[object], atributo_fecha: str,
              atributo_id: str, observacion: str) -> CoberturaTemporalFuente:
    fechas = tuple(filter(None, (_fecha(getattr(r, atributo_fecha, None)) for r in registros)))
    ids = {str(v).strip() for r in registros if (v := getattr(r, atributo_id, None)) is not None and str(v).strip()}
    estado = EstadoReconocimiento.LISTO_PARA_ANALIZAR if fechas else EstadoReconocimiento.ARCHIVO_SIN_FECHAS_VALIDAS
    return CoberturaTemporalFuente(fuente, tipo, min(fechas) if fechas else None,
                                   max(fechas) if fechas else None, len(registros), len(ids),
                                   len(registros) - len(fechas), estado, observacion)


def reconocer_cuatro_fuentes(ventas_ml: Sequence[object], operaciones_ec: Sequence[object],
                             settlement: Sequence[object], resumen_statement: ResumenEstadoCuentaMp) -> ReconocimientoCuatroFuentes:
    cs = (
        cobertura("Mercado Libre oficial", "Fecha de venta", ventas_ml, "fecha_venta", "id_venta", "Ventas reconocidas"),
        cobertura("Eccomapp", "Fecha de operación", operaciones_ec, "fecha_hora_venta", "id_orden", "Cobertura comercial preliminar"),
        cobertura("Settlement MP", "Fecha de origen", settlement, "fecha_origen_local", "id_operacion_mercado_pago", "Puede explicar operaciones históricas"),
        cobertura("Settlement MP", "Fecha de liquidación", settlement, "fecha_liquidacion_local", "id_operacion_mercado_pago", "Puede incluir liquidaciones posteriores"),
        cobertura("Account Statement", "Fecha de impacto", resumen_statement.movimientos, "fecha_liberacion", "reference_id", "Control de saldo"),
    )
    ml, ec, _, _, statement = cs
    b1 = None
    warnings: list[str] = []
    if ml.fecha_desde and ec.fecha_desde:
        inicio, fin = max(ml.fecha_desde, ec.fecha_desde), min(ml.fecha_hasta, ec.fecha_hasta)  # type: ignore[arg-type]
        if inicio <= fin:
            b1 = (inicio, fin)
        else:
            warnings.append("Mercado Libre y Eccomapp no tienen fechas en común.")
    if ml.fecha_desde != ec.fecha_desde or ml.fecha_hasta != ec.fecha_hasta:
        warnings.append("Mercado Libre y Eccomapp no cubren exactamente el mismo período.")
    estado_b1 = (EstadoReconocimiento.PENDIENTE_DE_VALIDACION_POR_IDS if b1 else
                 EstadoReconocimiento.PERIODOS_INCOMPATIBLES)
    b23 = (statement.fecha_desde, statement.fecha_hasta) if statement.fecha_desde else None
    estado_b23 = EstadoReconocimiento.PENDIENTE_DE_VALIDACION_POR_IDS if b23 else EstadoReconocimiento.ARCHIVO_SIN_FECHAS_VALIDAS
    warnings.append("El Settlement tiene cobertura temporal amplia, pero la cobertura definitiva se valida por IDs.")
    return ReconocimientoCuatroFuentes(cs, b1, b23, estado_b1, estado_b23, tuple(warnings))


def resolver_periodo(tipo: TipoSeleccionPeriodo, zona: str, disponible: tuple[date, date] | None = None,
                     desde: date | None = None, hasta: date | None = None,
                     ahora: datetime | None = None) -> PeriodoAnalisis:
    hoy = (ahora or datetime.now(ZoneInfo(zona))).astimezone(ZoneInfo(zona)).date()
    if tipo == TipoSeleccionPeriodo.AYER:
        inicio = fin = hoy - timedelta(days=1)
    elif tipo in (TipoSeleccionPeriodo.ULTIMOS_3_DIAS, TipoSeleccionPeriodo.ULTIMOS_7_DIAS):
        dias = 3 if tipo == TipoSeleccionPeriodo.ULTIMOS_3_DIAS else 7
        fin, inicio = hoy - timedelta(days=1), hoy - timedelta(days=dias)
    elif tipo == TipoSeleccionPeriodo.TODO_DISPONIBLE:
        if disponible is None:
            raise ValueError("No hay un período disponible para seleccionar.")
        inicio, fin = disponible
    else:
        if desde is None or hasta is None:
            raise ValueError("Ingresá ambas fechas del rango personalizado.")
        inicio, fin = desde, hasta
    return PeriodoAnalisis(inicio, fin, zona, tipo)


def filtrar_por_periodo(registros: Iterable[object], atributo: str, periodo: PeriodoAnalisis) -> tuple[object, ...]:
    return tuple(r for r in registros if (f := _fecha(getattr(r, atributo, None))) is not None
                 and periodo.fecha_desde <= f <= periodo.fecha_hasta)


def filtrar_estado_cuenta(resumen: ResumenEstadoCuentaMp, periodo: PeriodoAnalisis) -> ResumenEstadoCuentaMp | None:
    movimientos = filtrar_por_periodo(resumen.movimientos, "fecha_liberacion", periodo)
    if not movimientos:
        return None
    primero, ultimo = movimientos[0], movimientos[-1]
    inicial = primero.saldo_parcial - primero.importe_neto if primero.saldo_parcial is not None else (
        resumen.saldo_inicial if _fecha(resumen.fecha_desde) == periodo.fecha_desde else Decimal("0"))
    final = ultimo.saldo_parcial if ultimo.saldo_parcial is not None else inicial + sum((m.importe_neto for m in movimientos), Decimal("0"))
    creditos = sum((m.importe_neto for m in movimientos if m.importe_neto > 0), Decimal("0"))
    debitos = sum((m.importe_neto for m in movimientos if m.importe_neto < 0), Decimal("0"))
    return ResumenEstadoCuentaMp(inicial, creditos, debitos, final, movimientos,
                                 min(m.fecha_liberacion for m in movimientos), max(m.fecha_liberacion for m in movimientos))


def universos_settlement(ventas: Sequence[object], operaciones: Sequence[object], settlement: Sequence[object],
                         periodo: PeriodoAnalisis) -> tuple[tuple[object, ...], tuple[object, ...]]:
    """Deriva B1 por vínculos comerciales y conserva Settlement completo para B2/B3."""
    ventas_periodo = filtrar_por_periodo(ventas, "fecha_venta", periodo)
    ops_periodo = filtrar_por_periodo(operaciones, "fecha_hora_venta", periodo)
    ids = {str(getattr(x, a)).strip() for x, a in
           ((*((x, "id_venta") for x in ventas_periodo), *((x, "id_orden") for x in ops_periodo)))
           if getattr(x, a, None)}
    b1 = tuple(m for m in settlement if any(str(getattr(m, a, "") or "").strip() in ids
                                            for a in ("id_operacion_mercado_pago", "id_orden", "id_paquete")))
    return b1, tuple(settlement)
