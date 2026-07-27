"""Formateadores puros sin dependencia de locale global."""

from decimal import Decimal, ROUND_HALF_UP


def formato_pesos_argentino(valor: Decimal | None) -> str:
    """Formatea importes como pesos argentinos sin convertir a float."""

    if valor is None:
        return "—"
    cuantizado = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    signo = "-$ " if cuantizado < 0 else "$ "
    absoluto = abs(cuantizado)
    entero, decimales = f"{absoluto:.2f}".split(".")
    grupos: list[str] = []
    while entero:
        grupos.append(entero[-3:])
        entero = entero[:-3]
    return f"{signo}{'.'.join(reversed(grupos))},{decimales}"


def formato_bool(valor: bool) -> str:
    return "Sí" if valor else "No"
