"""Textos puros para presentar el control diario de Mercado Pago."""

from decimal import Decimal

from kiki_control.domain.account_statement import (
    CategoriaEstadoCuentaMp,
    ControlEstadoCuentaMp,
    EstadoVinculacionEstadoCuentaMp,
)
from kiki_control.presentation.control_consolidado_view import formato_importe


def leyenda_cobertura_tecnica(control: ControlEstadoCuentaMp) -> str:
    """Distingue procesamiento técnico de atribución comercial."""
    procesadas = control.cantidad_lineas_entrada - control.cantidad_no_clasificadas
    return (
        f"Cobertura calculada: {procesadas} líneas procesadas · "
        f"{control.cantidad_lineas_clasificadas} categorizadas exactamente una vez · "
        f"{control.cantidad_sin_clasificacion_comercial} sin atribución comercial suficiente · "
        f"{control.cantidad_clasificadas_mas_de_una_vez} con conflicto · diferencia monetaria "
        f"{formato_importe(control.diferencia_cobertura_monetaria)}."
    )


def detalle_cobertura_tecnica(control: ControlEstadoCuentaMp) -> str:
    return (f"Sin categoría técnica: {control.cantidad_no_clasificadas} · "
            f"procesadas exactamente una vez: {control.cantidad_lineas_clasificadas}.")


def sintesis_ejecutiva(b1: object, control: ControlEstadoCuentaMp | None) -> str:
    """Resume conciliación, cierre y atribución usando resultados de dominio."""
    diferencias = b1.resumen.con_diferencia
    frase_b1 = ("Conciliación ML–MP sin diferencias." if diferencias == 0 else
                f"Conciliación ML–MP con {diferencias} {'diferencia' if diferencias == 1 else 'diferencias'}.")
    if control is None or not control.resumen.control_contable_verificable:
        frase_saldo, pendientes = "El saldo de Mercado Pago no es verificable.", 0
    else:
        frase_saldo = ("El saldo de Mercado Pago cierra." if control.resumen.diferencia_control == Decimal("0")
                       else "El saldo de Mercado Pago no cierra.")
        pendientes = control.cantidad_sin_clasificacion_comercial
    frase_pendientes = ("No quedan movimientos pendientes de atribución comercial." if pendientes == 0 else
                        f"{'Queda' if pendientes == 1 else 'Quedan'} {pendientes} "
                        f"{'movimiento pendiente' if pendientes == 1 else 'movimientos pendientes'} de atribución comercial.")
    return f"{frase_b1} {frase_saldo} {frase_pendientes}"


_MENSAJES_CAUSA_COBERTURA = {
    EstadoVinculacionEstadoCuentaMp.SIN_VINCULO_SETTLEMENT: (
        "Existen líneas sin vínculo Settlement y sin evidencia comercial; "
        "descargá el Settlement Report con un período de origen más amplio."
    ),
    EstadoVinculacionEstadoCuentaMp.VINCULADO_SIN_ORIGEN_COMERCIAL: (
        "La cobertura comercial es parcial porque existen movimientos vinculados al "
        "Settlement cuya evidencia no permite determinar responsablemente el origen comercial."
    ),
    EstadoVinculacionEstadoCuentaMp.ID_AMBIGUO: (
        "Existen IDs con evidencia contradictoria en el Settlement; revisá sus filas antes de atribuir el origen comercial."
    ),
    EstadoVinculacionEstadoCuentaMp.ID_VACIO: (
        "Existen movimientos con la referencia vacía; completá o verificá el reference ID del estado de cuenta."
    ),
}


def mensaje_cobertura_comercial_parcial(control: ControlEstadoCuentaMp) -> str:
    """Explica cada causa real de cobertura parcial, sin inferencias por importe."""
    pendientes = tuple(
        movimiento for movimiento in control.movimientos
        if movimiento.categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE
    )
    causas = tuple(
        estado for estado in _MENSAJES_CAUSA_COBERTURA
        if any(m.estado_vinculacion == estado for m in pendientes)
    )
    if not causas:
        return "La cobertura comercial es parcial; revisá el detalle de movimientos sin atribución comercial suficiente."
    mensajes = tuple(_MENSAJES_CAUSA_COBERTURA[estado] for estado in causas)
    if len(mensajes) == 1:
        return mensajes[0]
    resumen = "; ".join(
        f"{sum(m.estado_vinculacion == estado for m in pendientes)} {estado.value}"
        for estado in causas
    )
    return f"La cobertura comercial es parcial por varias causas ({resumen}). " + " ".join(mensajes)


def aclaracion_b1_b2(cantidad_grupos_conciliados: int) -> str:
    return (
        "B1 concilia las ventas de Mercado Libre originadas en el período. B2 analiza "
        "los movimientos que impactaron efectivamente el saldo de Mercado Pago durante "
        "el día. Una venta puede originarse un día y liquidarse en otro; por eso los "
        f"{cantidad_grupos_conciliados} grupos conciliados de B1 no deben coincidir con "
        "la cantidad de movimientos asociados a ML en B2."
    )


def aclaracion_sin_movimientos_ml(cantidad_grupos_conciliados: int) -> str:
    return (
        "Con los archivos cargados no se identificaron movimientos del saldo "
        "pertenecientes a ventas ML del período. Esto no invalida los "
        f"{cantidad_grupos_conciliados} grupos conciliados en B1."
    )
