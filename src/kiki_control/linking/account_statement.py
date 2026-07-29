"""Vinculación exacta y clasificación excluyente del estado de cuenta."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from kiki_control.domain.account_statement import (
    CategoriaEstadoCuentaMp,
    ControlEstadoCuentaMp,
    EstadoVinculacionEstadoCuentaMp,
    GrupoSettlementPorOperacionMp,
    MovimientoEstadoCuentaClasificado,
)


def construir_indice_operacion_mp_a_grupo_ml(reporte_consolidado: Any, movimientos_settlement: Iterable[Any]) -> dict[str, tuple[str, ...]]:
    """Reutiliza la pertenencia canónica ya resuelta por el consolidado.

    El puente se realiza por número de fila settlement, que el motor conserva en
    ``filas_origen_mp``. Nunca se compara ``id_orden`` con el grupo canónico.
    Solo se indexan resultados que efectivamente contienen venta oficial ML.
    """
    grupo_por_fila: dict[int, set[str]] = defaultdict(set)
    for resultado in reporte_consolidado.resultados:
        grupo = getattr(resultado, "id_grupo_canonico", None)
        if not grupo or not getattr(resultado, "tiene_mercado_libre_oficial", False):
            continue
        for fila in getattr(resultado, "filas_origen_mp", tuple()):
            grupo_por_fila[fila].add(grupo)
    indice_temporal: dict[str, set[str]] = defaultdict(set)
    for movimiento in movimientos_settlement:
        grupos = grupo_por_fila.get(movimiento.numero_fila_origen, set())
        if len(grupos) == 1:
            operacion = str(movimiento.id_operacion_mercado_pago).strip()
            indice_temporal[operacion].update(grupos)
    return {operacion: tuple(sorted(grupos)) for operacion, grupos in indice_temporal.items()}


def agrupar_settlement_por_operacion(
    movimientos_settlement: Iterable[Any],
    operacion_a_grupo_ml: Mapping[str, str | Iterable[str]] | None = None,
) -> dict[str, GrupoSettlementPorOperacionMp]:
    """Agrupa filas settlement y detecta contradicciones comerciales reales."""
    filas_por_id: dict[str, list[Any]] = defaultdict(list)
    for movimiento in movimientos_settlement:
        filas_por_id[str(movimiento.id_operacion_mercado_pago).strip()].append(movimiento)
    resultado = {}
    vinculos = operacion_a_grupo_ml or {}
    for operacion, movimientos in filas_por_id.items():
        ids_orden = _valores(movimientos, "id_orden")
        canales = _valores(movimientos, "canal_venta")
        plataformas = _valores(movimientos, "plataforma_cobro")
        vinculo = vinculos.get(operacion)
        if isinstance(vinculo, str):
            grupos = (vinculo,)
        else:
            grupos = tuple(sorted(set(vinculo or tuple())))
        canal_ml = any(c.casefold() == "mercado libre" for c in canales)
        canal_mp = any(c.casefold() == "mercado pago" for c in canales)
        qr = any("código qr" in p.casefold() or "codigo qr" in p.casefold() for p in plataformas)
        motivos = []
        # IDs de orden diferentes son compatibles solamente si el motor ya los
        # consolidó explícitamente en un único grupo ML.
        if len(ids_orden) > 1 and len(grupos) != 1:
            motivos.append("IDs de orden contradictorios")
        if canal_ml and (canal_mp or qr):
            motivos.append("mezcla contradictoria de canal Mercado Libre y QR/Mercado Pago")
        if len(grupos) > 1:
            motivos.append("asociación a más de un grupo ML")
        resultado[operacion] = GrupoSettlementPorOperacionMp(
            operacion,
            tuple(m.numero_fila_origen for m in movimientos),
            ids_orden,
            canales,
            plataformas,
            grupos,
            tuple(movimientos),
            bool(motivos),
            "; ".join(motivos) or None,
        )
    return resultado


def controlar_estado_cuenta_mp(
    resumen: Any,
    movimientos_settlement: Iterable[Any],
    operacion_a_grupo_ml: Mapping[str, str | Iterable[str]] | None = None,
) -> ControlEstadoCuentaMp:
    grupos = agrupar_settlement_por_operacion(movimientos_settlement, operacion_a_grupo_ml)
    clasificados = tuple(_clasificar(m, grupos) for m in resumen.movimientos)
    return ControlEstadoCuentaMp(resumen, clasificados)


def _clasificar(m: Any, grupos: Mapping[str, GrupoSettlementPorOperacionMp]) -> MovimientoEstadoCuentaClasificado:
    grupo_settlement = grupos.get(m.reference_id or "")
    if not m.reference_id:
        estado = EstadoVinculacionEstadoCuentaMp.ID_VACIO
    elif grupo_settlement is None:
        estado = EstadoVinculacionEstadoCuentaMp.SIN_VINCULO_SETTLEMENT
    elif grupo_settlement.es_ambiguo:
        estado = EstadoVinculacionEstadoCuentaMp.ID_AMBIGUO
    else:
        estado = EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT
    coherente = grupo_settlement if estado == EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT else None
    texto = m.tipo_movimiento_original.casefold()
    canales = tuple(c.casefold() for c in coherente.canales) if coherente else tuple()
    plataformas = tuple(p.casefold() for p in coherente.plataformas) if coherente else tuple()
    id_grupo_ml = coherente.ids_grupo_ml[0] if coherente and len(coherente.ids_grupo_ml) == 1 else None
    es_salida = any(x in texto for x in ("transferencia enviada", "pago a proveedor", "retenido", "cancelada", "devolución", "devolucion", "reclamo", "impuesto", "comisión", "comision", "débito", "debito"))
    if es_salida:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SALIDA_O_AJUSTE_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original identifica explícitamente una salida o ajuste."
    elif id_grupo_ml:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML, "Movimiento de venta Mercado Libre", "El motor consolidado vinculó las filas settlement a un único grupo ML canónico."
    elif coherente and m.importe_neto > 0 and ("mercado pago" in canales or any("código qr" in p or "codigo qr" in p for p in plataformas)):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Venta por mostrador con Código QR", "El settlement identifica canal Mercado Pago o plataforma Código QR y no pertenece a un grupo ML."
    elif m.importe_neto > 0 and any(x in texto for x in ("rendimiento", "código qr", "codigo qr", "programa de protección", "programa de proteccion")):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original aporta evidencia explícita de un ingreso no ML."
    else:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE, "Origen no determinado", "No existe vínculo settlement inequívoco ni evidencia suficiente en el estado de cuenta."
        if grupo_settlement and grupo_settlement.es_ambiguo:
            motivo = f"El ID settlement es ambiguo: {grupo_settlement.motivo_ambiguedad}."
    if estado == EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT and categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE:
        estado = EstadoVinculacionEstadoCuentaMp.VINCULADO_SIN_ORIGEN_COMERCIAL
    acciones_revision = {
        EstadoVinculacionEstadoCuentaMp.SIN_VINCULO_SETTLEMENT: "Revisar con un settlement que cubra la fecha de origen.",
        EstadoVinculacionEstadoCuentaMp.VINCULADO_SIN_ORIGEN_COMERCIAL: "Revisar el detalle comercial de la operación o ampliar la información del canal de cobro.",
        EstadoVinculacionEstadoCuentaMp.ID_AMBIGUO: "Revisar las filas settlement contradictorias y definir la operación comercial correcta.",
        EstadoVinculacionEstadoCuentaMp.ID_VACIO: "Completar o verificar el reference ID en el estado de cuenta.",
    }
    accion = acciones_revision[estado] if categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE else "Sin acción; conservar para trazabilidad."
    filas = grupo_settlement.filas_origen if grupo_settlement else tuple()
    return MovimientoEstadoCuentaClasificado(m, estado, categoria, subtipo, motivo, accion, filas, id_grupo_ml)


def _valores(movimientos: Iterable[Any], atributo: str) -> tuple[str, ...]:
    return tuple(sorted({str(valor).strip() for m in movimientos if (valor := getattr(m, atributo, None)) is not None and str(valor).strip()}))
