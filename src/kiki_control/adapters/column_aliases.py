"""Alias de columnas externas resueltos en la frontera de adaptación."""

from __future__ import annotations

from types import MappingProxyType

from kiki_control.domain.enums import TipoFuente

ALIAS_COLUMNAS_MERCADO_LIBRE = MappingProxyType(
    {
        "Iva": "IVA",
        "Costo unitario (Con IVA) ($)": "Costo Unitario (Con IVA) ($)",
        "Bonificación por envío": "Bonificación envío ($)",
        "precio_equilibrio ($)": "Precio de equilibrio ($)",
        "Rentabilidad (precio de venta)": "Rentabilidad s/ precio venta",
        "Rentabilidad (costo de producto)": "Rentabilidad s/ costo producto",
        "Rentabilidad (suma de costos)": "Rentabilidad s/ suma costos",
        "Comisión MeLi (%)": "% Comisión MeLi",
        "Costo de envío (%)": "% Costo de envío",
    }
)

ALIAS_COLUMNAS_MERCADO_PAGO = MappingProxyType(
    {
        "MONTO RECIBIDO POR COMPRAS POR SPLIT": "MONTO RECIBIDO POR SPLIT",
        "MONEDA DE LA LIQUIDACIÓN": "MONEDA DE LIQUIDACIÓN",
        "ID DEL ENVÍO": "ID DE ENVÍO",
        "ID DEL PAQUETE": "ID DE PAQUETE",
    }
)

_ALIAS_POR_FUENTE = MappingProxyType(
    {
        TipoFuente.MERCADO_LIBRE: ALIAS_COLUMNAS_MERCADO_LIBRE,
        TipoFuente.MERCADO_PAGO: ALIAS_COLUMNAS_MERCADO_PAGO,
    }
)


def canonizar_columna(nombre: str, tipo_fuente: TipoFuente) -> str:
    """Devuelve el nombre canónico interno para una columna externa."""

    return _ALIAS_POR_FUENTE.get(tipo_fuente, {}).get(nombre, nombre)


def canonizar_columnas(columnas: tuple[str, ...], tipo_fuente: TipoFuente) -> tuple[str, ...]:
    """Canoniza una secuencia de columnas sin modificar el archivo recibido."""

    return tuple(canonizar_columna(columna, tipo_fuente) for columna in columnas)


def canonizar_fila(fila: dict[str, object], tipo_fuente: TipoFuente) -> dict[str, object]:
    """Canoniza claves de una fila preservando valores y priorizando columnas canónicas."""

    canonica: dict[str, object] = {}
    for columna, valor in fila.items():
        nombre_canonico = canonizar_columna(columna, tipo_fuente)
        if nombre_canonico not in canonica or columna == nombre_canonico:
            canonica[nombre_canonico] = valor
    return canonica
