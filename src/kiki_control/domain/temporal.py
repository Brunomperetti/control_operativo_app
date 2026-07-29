"""Reconocimiento temporal y selección de universos de las cuatro fuentes."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable, Sequence
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


class EstadoBloqueB1(StrEnum):
    COMPLETO = "COMPLETO"
    PARCIAL = "PARCIAL"
    SIN_ACTIVIDAD_COMERCIAL = "SIN_ACTIVIDAD_COMERCIAL"
    SIN_ECCOMAPP = "SIN_ECCOMAPP"
    SIN_VINCULO_MP = "SIN_VINCULO_MP"
    NO_CALCULABLE = "NO_CALCULABLE"


class EstadoBloqueB2B3(StrEnum):
    COMPLETO = "COMPLETO"
    COBERTURA_COMERCIAL_PARCIAL = "COBERTURA_COMERCIAL_PARCIAL"
    CONTROL_CONTABLE_NO_VERIFICABLE = "CONTROL_CONTABLE_NO_VERIFICABLE"
    SIN_MOVIMIENTOS_EN_PERIODO = "SIN_MOVIMIENTOS_EN_PERIODO"
    NO_CALCULABLE = "NO_CALCULABLE"


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
class DisponibilidadBloques:
    periodo_solicitado: PeriodoAnalisis
    periodo_efectivo_b1: PeriodoAnalisis | None
    periodo_efectivo_b2_b3: PeriodoAnalisis | None
    fechas_sin_cobertura_b1: tuple[date, ...]
    fechas_sin_cobertura_b2_b3: tuple[date, ...]


def periodo_efectivo(periodo: PeriodoAnalisis, cobertura_disponible: tuple[date, date] | None) -> PeriodoAnalisis | None:
    if cobertura_disponible is None:
        return None
    inicio = max(periodo.fecha_desde, cobertura_disponible[0])
    fin = min(periodo.fecha_hasta, cobertura_disponible[1])
    return None if inicio > fin else PeriodoAnalisis(inicio, fin, periodo.zona_horaria, periodo.tipo_seleccion)


def fechas_sin_cobertura(periodo: PeriodoAnalisis, efectivo: PeriodoAnalisis | None) -> tuple[date, ...]:
    cubiertas = set()
    if efectivo is not None:
        cubiertas = {efectivo.fecha_desde + timedelta(days=i)
                     for i in range((efectivo.fecha_hasta - efectivo.fecha_desde).days + 1)}
    return tuple(periodo.fecha_desde + timedelta(days=i)
                 for i in range((periodo.fecha_hasta - periodo.fecha_desde).days + 1)
                 if periodo.fecha_desde + timedelta(days=i) not in cubiertas)


def calcular_disponibilidad_bloques(periodo: PeriodoAnalisis,
                                    cobertura_b1: tuple[date, date] | None,
                                    cobertura_b2_b3: tuple[date, date] | None) -> DisponibilidadBloques:
    b1 = periodo_efectivo(periodo, cobertura_b1)
    b23 = periodo_efectivo(periodo, cobertura_b2_b3)
    return DisponibilidadBloques(periodo, b1, b23, fechas_sin_cobertura(periodo, b1),
                                 fechas_sin_cobertura(periodo, b23))


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
    # Las fechas solo acreditan cobertura temporal preliminar; la suficiencia
    # definitiva requiere vínculos por IDs y cobertura comercial/monetaria.
    estado = EstadoReconocimiento.PENDIENTE_DE_VALIDACION_POR_IDS if fechas else EstadoReconocimiento.ARCHIVO_SIN_FECHAS_VALIDAS
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
    comienza_con_statement = _fecha(resumen.fecha_desde) == periodo.fecha_desde
    inicial = (primero.saldo_parcial - primero.importe_neto if primero.saldo_parcial is not None
               else resumen.saldo_inicial if comienza_con_statement else None)
    motivo = None
    if inicial is None:
        motivo = ("La composición de movimientos puede analizarse, pero el archivo no aporta evidencia suficiente "
                  "para reconstruir el saldo inicial de este recorte.")
    # PARTIAL_BALANCE es evidencia explícita del saldo posterior al movimiento.
    # Sin él solo se deriva el final si el saldo inicial del recorte es conocido.
    final = (ultimo.saldo_parcial if ultimo.saldo_parcial is not None else
             inicial + sum((m.importe_neto for m in movimientos), Decimal("0")) if inicial is not None else None)
    creditos = sum((m.importe_neto for m in movimientos if m.importe_neto > 0), Decimal("0"))
    debitos = sum((m.importe_neto for m in movimientos if m.importe_neto < 0), Decimal("0"))
    return ResumenEstadoCuentaMp(inicial, creditos, debitos, final, movimientos,
                                 min(m.fecha_liberacion for m in movimientos), max(m.fecha_liberacion for m in movimientos), motivo)


def universos_settlement(ventas: Sequence[object], operaciones: Sequence[object], settlement: Sequence[object],
                         periodo: PeriodoAnalisis, reporte_comercial: Any | None = None) -> tuple[tuple[object, ...], tuple[object, ...]]:
    """Deriva B1 desde grupos comerciales y conserva Settlement completo para B2/B3.

    ``id_venta`` nunca se compara con el ID de operación MP. El reporte del
    motor aporta órdenes/carritos canónicos; una vez hallada una fila se
    expanden todas las filas de la misma operación y órdenes relacionadas.
    """
    ventas_periodo = filtrar_por_periodo(ventas, "fecha_venta", periodo)
    ops_periodo = filtrar_por_periodo(operaciones, "fecha_hora_venta", periodo)
    ids_orden = {str(getattr(x, "id_orden")).strip() for x in ops_periodo if getattr(x, "id_orden", None)}
    grupos = set()
    if reporte_comercial is not None:
        for resultado in reporte_comercial.resultados:
            tiene_venta_periodo = any(v in ventas_periodo for v in (
                *((resultado.venta_principal_ml,) if resultado.venta_principal_ml else ()),
                *resultado.ventas_detalle_ml,
            ))
            if not tiene_venta_periodo:
                continue
            grupos.add(resultado.id_grupo_canonico)
            ids_orden.update(str(x).strip() for x in resultado.ids_orden if x)
            ids_orden.update(str(op.id_orden).strip() for op in resultado.operaciones_eccomapp if op.id_orden)
            ids_orden.update(str(op.id_carrito).strip() for op in resultado.operaciones_eccomapp if getattr(op, "id_carrito", None))
    # Semilla exclusivamente por orden/grupo comercial, nunca por id_venta=id_operación MP.
    ids_operacion = {str(m.id_operacion_mercado_pago).strip() for m in settlement
                     if str(getattr(m, "id_orden", "") or "").strip() in ids_orden
                     or str(getattr(m, "id_paquete", "") or "").strip() in grupos}
    # Expansión transitiva: devoluciones/ajustes pueden aportar la operación en
    # otra fila, pero comparten orden, paquete o referencia de reembolso.
    cambio = True
    while cambio:
        cambio = False
        for m in settlement:
            operacion = str(getattr(m, "id_operacion_mercado_pago", "") or "").strip()
            orden = str(getattr(m, "id_orden", "") or "").strip()
            paquete = str(getattr(m, "id_paquete", "") or "").strip()
            relacionada = operacion in ids_operacion or orden in ids_orden or paquete in grupos
            if relacionada:
                if operacion and operacion not in ids_operacion:
                    ids_operacion.add(operacion); cambio = True
                if orden and orden not in ids_orden:
                    ids_orden.add(orden); cambio = True
    b1 = tuple(m for m in settlement if str(getattr(m, "id_operacion_mercado_pago", "") or "").strip() in ids_operacion)
    return b1, tuple(settlement)
