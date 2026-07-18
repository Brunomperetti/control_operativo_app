"""Agrupación determinista para conciliación Mercado Libre / Mercado Pago."""

from collections import defaultdict
from dataclasses import dataclass

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.financial_movement import MovimientoFinanciero


@dataclass(frozen=True)
class GruposConciliacion:
    operaciones_por_orden: dict[str, tuple[OperacionComercial, ...]]
    movimientos_por_orden: dict[str, tuple[MovimientoFinanciero, ...]]
    movimientos_sin_orden: tuple[MovimientoFinanciero, ...]
    ids_orden: tuple[str, ...]


def agrupar_por_id_orden(
    operaciones: tuple[OperacionComercial, ...],
    movimientos: tuple[MovimientoFinanciero, ...],
) -> GruposConciliacion:
    """Agrupa por ID Order sin descartar grupos presentes en una sola fuente."""

    ops: dict[str, list[OperacionComercial]] = defaultdict(list)
    movs: dict[str, list[MovimientoFinanciero]] = defaultdict(list)
    sin_orden: list[MovimientoFinanciero] = []

    for operacion in operaciones:
        ops[operacion.id_orden].append(operacion)
    for movimiento in movimientos:
        if movimiento.id_orden:
            movs[movimiento.id_orden].append(movimiento)
        else:
            sin_orden.append(movimiento)

    ids = tuple(sorted(set(ops) | set(movs)))
    return GruposConciliacion(
        operaciones_por_orden={k: tuple(v) for k, v in ops.items()},
        movimientos_por_orden={k: tuple(v) for k, v in movs.items()},
        movimientos_sin_orden=tuple(sorted(sin_orden, key=lambda m: (m.numero_fila_origen, m.id_operacion_mercado_pago, m.tipo_operacion.value))),
        ids_orden=ids,
    )
