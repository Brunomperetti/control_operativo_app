"""Textos puros para presentar el control diario de Mercado Pago."""


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
