"""Definiciones y explicaciones puras para la presentación de conciliaciones."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.financial_movement import MovimientoFinanciero, TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion, MotivoConciliacion, ResultadoConciliacion
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.reconciliation_view import etiqueta_estado

ML_ID_ORDER = "ID Order"
MP_ID_ORDER = "ID DE LA ORDEN"
MP_ID_OPERACION = "ID DE OPERACIÓN EN MERCADO PAGO"
ML_SKU = "Sku"
MP_SKU = "CÓDIGO DE PRODUCTO SKU"
ML_NETO = "Monto neto (en MP) ($)"
ML_UTILIDAD = "Utilidades netas ($)"
ML_FECHA = "Fecha de venta"
ML_HORA = "Hora"
MP_TIPO = "TIPO DE OPERACIÓN"
MP_NETO = "MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO"
MP_FECHA_ORIGEN = "FECHA DE ORIGEN"
MP_FECHA_LIQUIDACION = "FECHA DE LIQUIDACIÓN DEL DINERO"
SENSITIVE_COLUMNS = frozenset({"PAGADOR", "TIPO DE IDENTIFICACIÓN DEL PAGADOR", "NÚMERO DE IDENTIFICACIÓN DEL PAGADOR", "NÚMERO INICIAL DE TARJETA"})

@dataclass(frozen=True)
class DefinicionMetrica:
    nombre: str
    ayuda: str

@dataclass(frozen=True)
class DefinicionColumna:
    campo: str
    encabezado: str
    ayuda: str

@dataclass(frozen=True)
class DefinicionEstado:
    estado: EstadoConciliacion
    nombre: str
    significado: str
    deteccion: str
    accion_usuaria: str

@dataclass(frozen=True)
class PasoCalculoOperacion:
    resultado: str
    valor_calculado: str
    regla_o_formula: str
    archivo_origen: str
    columnas_utilizadas: tuple[str, ...]
    filas_origen: str

METRICAS_RESUMEN = {
    "Comparables": DefinicionMetrica("Comparables", f"Cantidad de resultados donde existe un neto comercial ML y un neto aprobado MP que pueden compararse. Columnas ML: {ML_ID_ORDER}, {ML_NETO}. Columnas MP: {MP_ID_ORDER}, {MP_TIPO}, {MP_NETO}. No es la cantidad total de filas de los archivos."),
    "Coincidencias exactas": DefinicionMetrica("Coincidencias exactas", "Operaciones comparables cuya diferencia es exactamente $0. Fórmula por orden: diferencia = neto aprobado MP - neto informado ML. La coincidencia se refiere solamente al control de netos comparables."),
    "Con diferencia": DefinicionMetrica("Con diferencia", "Operaciones comparables cuya diferencia no es cero. Positivo: MP informa más neto que ML. Negativo: MP informa menos neto que ML. La tolerancia define si supera el límite, pero no convierte una diferencia no nula en coincidencia exacta."),
    "Sin venta en ML": DefinicionMetrica("Sin venta en ML", "Cantidad de grupos financieros con ID de orden o referencia financiera que no encontraron una operación comercial normalizada asociada. No afirma ventas faltantes; puede deberse a cobertura temporal distinta, devoluciones, reclamos u otros movimientos. Excluye movimientos de fondos."),
    "Sin movimiento en MP": DefinicionMetrica("Sin movimiento en MP", "Operaciones presentes en Mercado Libre sin movimientos financieros asociados en el archivo de Mercado Pago. Puede indicar distinto período financiero o que todavía no existe movimiento."),
    "Requieren revisión": DefinicionMetrica("Requieren revisión", "Cuenta únicamente resultados cuyo requiere_revision es verdadero. No es igual a excepciones y casos especiales: una devolución, pago dividido o movimiento de fondos puede ser caso especial sin requerir revisión manual."),
    "Movimientos de fondos": DefinicionMetrica("Movimientos de fondos", f"Movimientos PAYOUT sin orden. Columnas MP: {MP_TIPO}, {MP_ID_ORDER} y {MP_NETO}. Se muestran separados y no se consideran pérdida de una venta."),
    "Utilidad informada ML": DefinicionMetrica("Utilidad informada ML", f"Fuente exclusiva: columna {ML_UTILIDAD} de Mercado Libre. Cálculo: suma de la utilidad informada para las operaciones consideradas por el reporte. La aplicación no la recalcula ni la presenta como ganancia contable, fiscal o definitiva."),
    "Neto ML comparable": DefinicionMetrica("Neto ML comparable", f"Fuente: {ML_NETO}. Suma únicamente los resultados comparables."),
    "Neto MP comparable": DefinicionMetrica("Neto MP comparable", f"Fuente: {MP_NETO}. Incluye únicamente movimientos cuyo tipo normalizado es PAGO_APROBADO, agrupados por {MP_ID_ORDER}, y solo resultados comparables."),
    "Diferencia comparable": DefinicionMetrica("Diferencia comparable", "Suma de diferencias por orden comparable: neto aprobado MP - neto informado ML. Positivo: MP informa más; negativo: MP informa menos."),
    "Neto MP fuera del archivo ML": DefinicionMetrica("Neto MP fuera del archivo ML", "Suma del neto de pagos aprobados de grupos financieros sin operación comercial en el CSV cargado. No es pérdida ni diferencia; puede corresponder a otro período."),
}

METRICAS_COBERTURA = {
    "Ventas ML": DefinicionMetrica("Ventas ML", f"Fuente: Mercado Libre. Columnas: {ML_FECHA} y {ML_HORA}. Cálculo: fecha mínima y máxima de las operaciones comerciales normalizadas. Utilidad: permite saber qué período comercial se está controlando."),
    "Origen movimientos MP": DefinicionMetrica("Origen movimientos MP", f"Fuente: Mercado Pago. Columna: {MP_FECHA_ORIGEN}. Cálculo: fecha local mínima y máxima de los movimientos financieros. Utilidad: indica el período de movimientos incluido en el XLSX."),
    "Liquidaciones MP": DefinicionMetrica("Liquidaciones MP", f"Fuente: Mercado Pago. Columna: {MP_FECHA_LIQUIDACION}. Cálculo: fecha mínima y máxima entre movimientos que poseen liquidación. Utilidad: distingue cuándo impactó o impactará el dinero."),
    "Sin fecha de liquidación": DefinicionMetrica("Sin fecha de liquidación", f"Fuente: Mercado Pago. Columna: {MP_FECHA_LIQUIDACION}. Cálculo: cantidad de movimientos normalizados donde esa fecha está vacía. No implica automáticamente un error; puede existir acreditación pendiente."),
}

COLUMNAS_TABLA = {
    "ID de orden": DefinicionColumna("id_orden", "ID de orden", f"Orden vinculada por {ML_ID_ORDER} contra {MP_ID_ORDER}. Si no hay orden, se muestra una referencia interna de fila creada por la aplicación para trazabilidad; no proviene de Mercado Libre."),
    "Estado": DefinicionColumna("estado", "Estado", "Estado final asignado por el motor según reglas vigentes y prioridad oficial."),
    "Neto informado ML": DefinicionColumna("neto_informado_ml", "Neto informado ML", f"Columna ML {ML_NETO}."),
    "Neto aprobado MP": DefinicionColumna("neto_pagos_aprobados_mp", "Neto aprobado MP", f"Suma de {MP_NETO} solo para movimientos PAGO_APROBADO de la orden."),
    "Diferencia": DefinicionColumna("diferencia", "Diferencia", "Neto aprobado MP menos neto informado ML. Queda vacía cuando la operación no es comparable."),
    "Neto financiero total": DefinicionColumna("neto_financiero_total", "Neto financiero total", "Suma el impacto neto de todos los movimientos MP asociados: pagos, envíos, devoluciones, reclamos y otros. Por eso puede diferir del neto aprobado MP."),
    "Utilidad informada ML": DefinicionColumna("utilidad_informada", "Utilidad informada ML", f"Valor informado en {ML_UTILIDAD}; no recalculado por la aplicación."),
    "Pago dividido": DefinicionColumna("pago_dividido", "Pago dividido", "Sí cuando la orden posee más de un movimiento PAGO_APROBADO; la aplicación suma sus netos para el control principal."),
    "Devolución": DefinicionColumna("devolucion", "Devolución", "Derivado de tipos financieros normalizados como devolución de dinero o devolución de envío."),
    "Reclamo o disputa": DefinicionColumna("reclamo_o_disputa", "Reclamo o disputa", "Derivado de tipos normalizados de reclamo o disputa."),
    "Pendiente de acreditación": DefinicionColumna("pendiente_acreditacion", "Pendiente de acreditación", f"Existe un pago aprobado sin {MP_FECHA_LIQUIDACION}."),
    "Requiere revisión": DefinicionColumna("requiere_revision", "Requiere revisión", "Resultado marcado para intervención manual según las reglas vigentes."),
}

ESTADOS = tuple(
    DefinicionEstado(e, etiqueta_estado(e), sig, det, acc) for e, sig, det, acc in [
        (EstadoConciliacion.CONCILIADA, "El neto comparable coincide exactamente.", "Diferencia MP menos ML igual a cero.", "Puede considerarse cerrada para este control."),
        (EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR, "Hay diferencia no nula dentro de tolerancia.", "La diferencia absoluta es menor o igual a la tolerancia configurada.", "Revisar si la tolerancia es aceptable."),
        (EstadoConciliacion.CONCILIADA_CON_DIFERENCIA, "Hay contraparte, pero los netos comparables no coinciden.", "La diferencia supera la tolerancia configurada.", "Analizar los movimientos y la fuente."),
        (EstadoConciliacion.PENDIENTE_ACREDITACION, "Existe pago aprobado sin liquidación informada.", "Pago aprobado sin fecha de liquidación normalizada.", "Verificar si la acreditación está pendiente."),
        (EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO, "Venta ML sin movimiento MP en el archivo.", "Hay operación comercial y cero movimientos financieros.", "Revisar cobertura del XLSX o esperar movimiento."),
        (EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL, "Grupo MP sin operación ML asociada.", "Hay movimientos financieros con orden o referencia sin operación comercial normalizada.", "Revisar cobertura temporal, devoluciones o reclamos."),
        (EstadoConciliacion.DEVUELTA, "La orden o grupo tiene devolución.", "Se detectó devolución de dinero o envío.", "Conciliar venta y devolución."),
        (EstadoConciliacion.EN_RECLAMO, "La orden o grupo tiene reclamo o disputa.", "Se detectó reclamo o disputa normalizada.", "Revisar el caso manualmente."),
        (EstadoConciliacion.EN_REVISION, "El motor no tiene evidencia suficiente.", "Existe movimiento desconocido u otra condición ambigua.", "Intervenir manualmente."),
        (EstadoConciliacion.DUPLICADA, "Hay registros potencialmente repetidos.", "Más de una operación comercial para la orden o clave financiera duplicada.", "Resolver duplicados antes de cerrar."),
        (EstadoConciliacion.MOVIMIENTO_DE_FONDOS, "PAYOUT sin orden tratado como movimiento de fondos.", "Movimiento PAYOUT sin ID de orden.", "No tratarlo como pérdida comercial; revisar como movimiento de fondos."),
    ]
)

def guia_general() -> dict[str, str | tuple[DefinicionEstado, ...]]:
    return {
        "Cómo se vinculan Mercado Libre y Mercado Pago": f"La clave primaria es el ID de orden: Mercado Libre usa {ML_ID_ORDER} y Mercado Pago usa {MP_ID_ORDER}. El SKU ({ML_SKU} en ML y {MP_SKU} en MP) es validación secundaria, no clave principal. Los movimientos de Mercado Pago se agrupan por orden; un contador de grupos financieros no equivale a cantidad de filas del XLSX.",
        "Cobertura temporal de los archivos": "La aplicación compara las coberturas informadas y no recorta automáticamente el XLSX. Si los períodos no coinciden, un movimiento sin venta en el CSV de Mercado Libre no demuestra por sí solo un error.",
        "Cómo se calculan los indicadores del resumen": "Los indicadores se calculan sobre resultados normalizados y universos explícitos: comparables, solo ML, solo MP y movimientos de fondos separados.",
        "Diferencia entre neto aprobado MP y neto financiero total": "El neto aprobado MP suma solo pagos aprobados usados en el control principal. El neto financiero total suma todos los movimientos asociados, incluidos envíos, devoluciones, reclamos y otros movimientos.",
        "Costo de envío vacío en Mercado Libre oficial": "En el archivo oficial de Mercado Libre, un valor vacío en Costos de envío (ARS) se interpreta como $0 porque la clienta confirmó que significa que el seller no tuvo costo de envío.",
        "Significado de los estados": ESTADOS,
        "Diferencia entre excepción y revisión manual": "Excepciones y casos especiales es una clasificación visual amplia. Revisión manual cuenta únicamente resultados con requiere_revision verdadero; una devolución, pago dividido o movimiento de fondos puede mostrarse como caso especial sin requerir revisión manual.",
        "Límites del resultado y aclaración contable": "Los PAYOUTS sin orden son movimientos de fondos y no pérdidas comerciales. La utilidad de Mercado Libre es informada por la fuente y no constituye una ganancia contable o fiscal definitiva. La aplicación no inventa reglas contables, fiscales ni financieras." ,
    }

def etiqueta_id_resultado(resultado: ResultadoConciliacion) -> str:
    if resultado.id_orden:
        return resultado.id_orden
    fila = resultado.numeros_fila_financiera[0] if resultado.numeros_fila_financiera else "sin fila"
    return f"Movimiento MP sin ID de orden — referencia interna fila {fila}"

def explicar_operacion(resultado: ResultadoConciliacion, operaciones: Sequence[OperacionComercial], movimientos: Sequence[MovimientoFinanciero], tolerancia: Decimal) -> tuple[PasoCalculoOperacion, ...]:
    ops = tuple(o for o in operaciones if resultado.id_orden is not None and o.id_orden == resultado.id_orden)
    movs = tuple(m for m in movimientos if (m.id_orden == resultado.id_orden if resultado.id_orden is not None else m.numero_fila_origen in resultado.numeros_fila_financiera))
    if not ops and resultado.numeros_fila_comercial:
        ops = tuple(o for o in operaciones if o.numero_fila_origen in resultado.numeros_fila_comercial)
    pagos = tuple(m for m in movs if m.tipo_operacion == TipoOperacionFinanciera.PAGO_APROBADO)
    pasos = [PasoCalculoOperacion("Vinculación", etiqueta_id_resultado(resultado), f"Se vinculó {ML_ID_ORDER} contra {MP_ID_ORDER}; filas comerciales agrupadas: {len(ops)}, filas financieras agrupadas: {len(movs)}. El SKU es secundario.", "Mercado Libre / Mercado Pago", (ML_ID_ORDER, MP_ID_ORDER, ML_SKU, MP_SKU), _filas(resultado.numeros_fila_comercial, resultado.numeros_fila_financiera))]
    if resultado.neto_comercial_informado is not None:
        pasos.append(PasoCalculoOperacion("Neto informado ML", formato_pesos_argentino(resultado.neto_comercial_informado), f"Valor informado por la fuente en {ML_NETO}; la aplicación no lo recalcula.", "Mercado Libre", (ML_NETO,), _solo_filas(resultado.numeros_fila_comercial)))
    detalle_pagos = "; ".join(f"fila {m.numero_fila_origen}: {formato_pesos_argentino(m.monto_neto_impactado)}" for m in pagos)
    if resultado.neto_pagos_aprobados is not None:
        regla_pagos = (
            f"Movimientos PAGO_APROBADO utilizados: {detalle_pagos}. "
            f"Suma final: {formato_pesos_argentino(resultado.neto_pagos_aprobados)}. "
            f"Estos movimientos fueron agrupados por {MP_ID_ORDER} para el control comparable."
        )
    elif pagos and resultado.id_orden is None:
        regla_pagos = (
            f"Se detectó un pago aprobado en la fila {pagos[0].numero_fila_origen}, pero no posee `{MP_ID_ORDER}`. "
            f"Importe del movimiento como dato explicativo: {formato_pesos_argentino(pagos[0].monto_neto_impactado)}. "
            "Por ese motivo no se utiliza para calcular el neto aprobado comparable ni la diferencia contra Mercado Libre. "
            "No puede agruparse ni compararse por orden. "
            "Su impacto sí está incluido en el Neto financiero total de este resultado."
        )
    else:
        regla_pagos = "No hay movimientos normalizados como pago aprobado; por eso el Neto aprobado MP queda vacío."
    pasos.append(PasoCalculoOperacion("Neto aprobado MP", formato_pesos_argentino(resultado.neto_pagos_aprobados), regla_pagos, "Mercado Pago", (MP_ID_ORDER, MP_TIPO, MP_NETO), _solo_filas(tuple(m.numero_fila_origen for m in pagos))))
    if resultado.diferencia_control is not None:
        signo = "MP informa más neto que ML" if resultado.diferencia_control > 0 else "MP informa menos neto que ML" if resultado.diferencia_control < 0 else "MP y ML informan el mismo neto comparable"
        formula = f"{formato_pesos_argentino(resultado.neto_pagos_aprobados)} - {formato_pesos_argentino(resultado.neto_comercial_informado)} = {formato_pesos_argentino(resultado.diferencia_control)}. {signo}. Tolerancia aplicada: {formato_pesos_argentino(tolerancia)}."
        pasos.append(PasoCalculoOperacion("Diferencia", formato_pesos_argentino(resultado.diferencia_control), formula, "Mercado Libre / Mercado Pago", (ML_NETO, MP_NETO), _filas(resultado.numeros_fila_comercial, resultado.numeros_fila_financiera)))
    pago_aprobado_sin_id = _sumar_decimales(m.monto_neto_impactado for m in pagos if m.id_orden is None and resultado.id_orden is None)
    componentes_total = [
        f"Pagos aprobados comparables: {formato_pesos_argentino(resultado.neto_pagos_aprobados)}",
        f"pagos de envío: {formato_pesos_argentino(resultado.impacto_pagos_envio)}",
        f"devoluciones: {formato_pesos_argentino(resultado.impacto_devoluciones)}",
        f"reclamos/disputas: {formato_pesos_argentino(resultado.impacto_reclamos_disputas)}",
        f"otros: {formato_pesos_argentino(resultado.impacto_otros)}",
    ]
    if pago_aprobado_sin_id is not None:
        componentes_total.append(f"Pago aprobado sin ID de orden — no comparable: {formato_pesos_argentino(pago_aprobado_sin_id)}")
    regla_total = "Suma todos los movimientos MP asociados. " + "; ".join(componentes_total) + "."
    if pago_aprobado_sin_id is not None:
        regla_total += " Este pago aprobado sin ID de orden forma parte del Neto financiero total, pero no forma parte del neto aprobado comparable, no genera diferencia contra Mercado Libre y no modifica el motor ni el modelo de dominio."
    pasos.append(PasoCalculoOperacion("Neto financiero total", formato_pesos_argentino(resultado.neto_financiero_total), regla_total, "Mercado Pago", (MP_TIPO, MP_NETO), _solo_filas(resultado.numeros_fila_financiera)))
    if resultado.utilidad_neta_informada is not None:
        pasos.append(PasoCalculoOperacion("Utilidad informada", formato_pesos_argentino(resultado.utilidad_neta_informada), f"Valor informado en {ML_UTILIDAD}. La app no lo recalcula y no es ganancia contable o fiscal definitiva.", "Mercado Libre", (ML_UTILIDAD,), _solo_filas(resultado.numeros_fila_comercial)))
    cantidad_pagos = len(pagos)
    if resultado.id_orden is None:
        regla_pago_dividido = (
            f"No se evalúa como pago dividido por orden porque el movimiento no posee `{MP_ID_ORDER}`. "
            "El valor No no representa una orden con un único pago, sino la imposibilidad de agrupar y evaluar pagos por orden."
        )
    else:
        regla_pago_dividido = (
            f"Es Sí cuando existen dos o más movimientos normalizados como pago aprobado (`PAGO_APROBADO`) para la orden. Cantidad encontrada: {cantidad_pagos}. "
            + ("Se suman sus netos para el control principal." if resultado.es_pago_dividido else "Se encontró cero o un único pago aprobado.")
        )
    pasos.append(PasoCalculoOperacion(
        "Pago dividido",
        _si_no(resultado.es_pago_dividido),
        regla_pago_dividido,
        "Mercado Pago",
        (MP_ID_ORDER, MP_TIPO, MP_NETO),
        _solo_filas(tuple(m.numero_fila_origen for m in pagos)),
    ))
    devoluciones = tuple(m for m in movs if m.tipo_operacion in {TipoOperacionFinanciera.DEVOLUCION_DINERO, TipoOperacionFinanciera.DEVOLUCION_ENVIO})
    pasos.append(PasoCalculoOperacion(
        "Devolución",
        _si_no(resultado.tiene_devolucion),
        "Es Sí cuando existe un movimiento normalizado como DEVOLUCION_DINERO o DEVOLUCION_ENVIO. "
        + (f"Se detectaron {len(devoluciones)} movimientos de devolución." if resultado.tiene_devolucion else "No se detectaron movimientos normalizados como DEVOLUCION_DINERO ni DEVOLUCION_ENVIO."),
        "Mercado Pago",
        (MP_TIPO,),
        _solo_filas(tuple(m.numero_fila_origen for m in devoluciones)),
    ))
    reclamos_disputas = tuple(m for m in movs if m.tipo_operacion in {TipoOperacionFinanciera.RECLAMO, TipoOperacionFinanciera.DISPUTA_ENVIO})
    pasos.append(PasoCalculoOperacion(
        "Reclamo o disputa",
        _si_no(resultado.tiene_reclamo or resultado.tiene_disputa),
        "Es Sí cuando existe un movimiento normalizado como RECLAMO o DISPUTA_ENVIO. "
        + (f"Se detectaron {len(reclamos_disputas)} movimientos de reclamo o disputa." if (resultado.tiene_reclamo or resultado.tiene_disputa) else "No se detectaron movimientos normalizados como RECLAMO ni DISPUTA_ENVIO."),
        "Mercado Pago",
        (MP_TIPO,),
        _solo_filas(tuple(m.numero_fila_origen for m in reclamos_disputas)),
    ))
    pagos_sin_liquidacion = tuple(m for m in pagos if m.fecha_liquidacion_local is None)
    pasos.append(PasoCalculoOperacion(
        "Pendiente de acreditación",
        _si_no(resultado.tiene_liquidacion_pendiente),
        "Es Sí cuando existe al menos un PAGO_APROBADO sin fecha de liquidación. "
        + (f"Se detectaron {len(pagos_sin_liquidacion)} pagos aprobados sin liquidación." if resultado.tiene_liquidacion_pendiente else "No se encontró ningún PAGO_APROBADO sin fecha de liquidación."),
        "Mercado Pago",
        (MP_TIPO, MP_FECHA_LIQUIDACION),
        _solo_filas(tuple(m.numero_fila_origen for m in pagos_sin_liquidacion)),
    ))
    pasos.append(PasoCalculoOperacion(
        "Requiere revisión",
        _si_no(resultado.requiere_revision),
        _regla_revision(resultado),
        "Motor de conciliación",
        _columnas_estado(resultado),
        _filas(resultado.numeros_fila_comercial, resultado.numeros_fila_financiera),
    ))
    secundarios = ", ".join([t for t, v in [("pago dividido", resultado.es_pago_dividido), ("devolución", resultado.tiene_devolucion), ("reclamo", resultado.tiene_reclamo), ("disputa", resultado.tiene_disputa), ("liquidación pendiente", resultado.tiene_liquidacion_pendiente), ("requiere revisión", resultado.requiere_revision)] if v]) or "sin indicadores secundarios relevantes"
    pasos.append(PasoCalculoOperacion("Estado final", etiqueta_estado(resultado.estado), _explicacion_estado(resultado, secundarios), "Motor de conciliación", _columnas_estado(resultado), _filas(resultado.numeros_fila_comercial, resultado.numeros_fila_financiera)))
    return tuple(pasos)

def cobertura_desigual_no_bloqueante() -> str:
    return "Cuando la cobertura temporal no coincide, la aplicación advierte y continúa: no recorta automáticamente el XLSX ni concluye por sí sola que un movimiento sin venta sea un error."

def _sumar_decimales(importes: Iterable[Decimal]) -> Decimal | None:
    total = Decimal("0")
    tiene_importes = False
    for importe in importes:
        total += importe
        tiene_importes = True
    return total if tiene_importes else None

def _si_no(valor: bool) -> str:
    return "Sí" if valor else "No"

def _regla_revision(resultado: ResultadoConciliacion) -> str:
    base = "Es un indicador derivado por las reglas del motor, no una columna directa. Excepción o caso especial no equivale necesariamente a revisión manual. "
    if resultado.requiere_revision:
        return base + f"El valor es Sí por el estado vigente {etiqueta_estado(resultado.estado)} o por una condición que el motor marca para intervención manual."
    return base + f"El valor es No porque el estado vigente {etiqueta_estado(resultado.estado)} no requiere intervención manual según las reglas actuales."

def _explicacion_estado(resultado: ResultadoConciliacion, secundarios: str) -> str:
    explicaciones = "; ".join(resultado.explicaciones) or "el motor no agregó observaciones adicionales"
    return f"El estado ganador es {etiqueta_estado(resultado.estado)} porque {explicaciones}. Si había varias condiciones candidatas, se aplicó la prioridad oficial de estados. Indicadores secundarios: {secundarios}."

def _columnas_estado(resultado: ResultadoConciliacion) -> tuple[str, ...]:
    """Columnas que determinaron el estado, no todas las columnas disponibles."""

    motivos = set(resultado.motivos)
    columnas: list[str] = []
    if resultado.estado in {
        EstadoConciliacion.CONCILIADA,
        EstadoConciliacion.CONCILIADA_CON_DIFERENCIA_MENOR,
        EstadoConciliacion.CONCILIADA_CON_DIFERENCIA,
    }:
        columnas.extend([ML_ID_ORDER, ML_NETO, MP_ID_ORDER, MP_TIPO, MP_NETO])
    elif resultado.estado == EstadoConciliacion.PENDIENTE_ACREDITACION:
        columnas.extend([MP_ID_ORDER, MP_TIPO, MP_FECHA_LIQUIDACION])
    elif resultado.estado == EstadoConciliacion.OPERACION_SIN_MOVIMIENTO_FINANCIERO:
        columnas.append(ML_ID_ORDER)
    elif resultado.estado == EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL:
        columnas.extend([MP_ID_ORDER, MP_TIPO])
    elif resultado.estado == EstadoConciliacion.DEVUELTA:
        columnas.extend([MP_ID_ORDER, MP_TIPO])
    elif resultado.estado == EstadoConciliacion.EN_RECLAMO:
        columnas.extend([MP_ID_ORDER, MP_TIPO])
    elif resultado.estado == EstadoConciliacion.EN_REVISION:
        columnas.extend([MP_ID_ORDER, MP_TIPO])
    elif resultado.estado == EstadoConciliacion.MOVIMIENTO_DE_FONDOS:
        columnas.extend([MP_TIPO, MP_ID_ORDER])
    elif resultado.estado == EstadoConciliacion.DUPLICADA:
        if MotivoConciliacion.OPERACION_COMERCIAL_DUPLICADA in motivos:
            columnas.append(ML_ID_ORDER)
        if MotivoConciliacion.MOVIMIENTO_FINANCIERO_DUPLICADO in motivos:
            columnas.extend([MP_ID_OPERACION, MP_TIPO])
    return tuple(dict.fromkeys(columnas))

def _filas(comerciales: tuple[int, ...], financieras: tuple[int, ...]) -> str:
    return f"ML: {_solo_filas(comerciales)}; MP: {_solo_filas(financieras)}"

def _solo_filas(filas: Iterable[int]) -> str:
    vals = tuple(filas)
    return ", ".join(map(str, vals)) if vals else "—"
