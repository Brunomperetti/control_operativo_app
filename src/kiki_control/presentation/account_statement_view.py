"""Textos puros para presentar el control diario de Mercado Pago."""

from kiki_control.domain.account_statement import (
    CategoriaEstadoCuentaMp,
    ControlEstadoCuentaMp,
    EstadoVinculacionEstadoCuentaMp,
)


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
        return "La cobertura comercial es parcial; revisá el detalle de movimientos sin asociación suficiente."
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
