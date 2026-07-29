"""Vinculación exacta y clasificación excluyente del estado de cuenta."""

from collections import defaultdict

from kiki_control.domain.account_statement import *


def controlar_estado_cuenta_mp(resumen, movimientos_settlement, ids_grupos_ml: set[str] | None = None) -> ControlEstadoCuentaMp:
    indice = defaultdict(list)
    for mov in movimientos_settlement:
        indice[str(mov.id_operacion_mercado_pago).strip()].append(mov)
    clasificados = tuple(_clasificar(m, indice, ids_grupos_ml) for m in resumen.movimientos)
    return ControlEstadoCuentaMp(resumen, clasificados)


def _clasificar(m, indice, ids_grupos_ml):
    coincidencias = indice.get(m.reference_id or "", [])
    if not m.reference_id:
        estado = EstadoVinculacionEstadoCuentaMp.ID_VACIO
    elif not coincidencias:
        estado = EstadoVinculacionEstadoCuentaMp.SIN_VINCULO_SETTLEMENT
    elif len(coincidencias) > 1:
        estado = EstadoVinculacionEstadoCuentaMp.ID_AMBIGUO
    else:
        estado = EstadoVinculacionEstadoCuentaMp.VINCULADO_SETTLEMENT
    settlement = coincidencias[0] if len(coincidencias) == 1 else None
    texto = m.tipo_movimiento_original.casefold()
    canal = (getattr(settlement, "canal_venta", None) or "").casefold()
    plataforma = (getattr(settlement, "plataforma_cobro", None) or "").casefold()
    grupo = getattr(settlement, "id_orden", None) if settlement else None
    es_salida = any(x in texto for x in ("transferencia enviada", "pago a proveedor", "retenido", "cancelada", "devolución", "devolucion", "reclamo", "impuesto", "comisión", "comision", "débito", "debito"))
    if es_salida:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SALIDA_O_AJUSTE_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original identifica explícitamente una salida o ajuste."
    elif settlement and m.importe_neto > 0 and ("código qr" in plataforma or "codigo qr" in plataforma or canal == "mercado pago"):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Venta por mostrador con Código QR", "El settlement identifica canal Mercado Pago o plataforma Código QR."
    elif settlement and grupo and (ids_grupos_ml is None or grupo in ids_grupos_ml) and canal == "mercado libre":
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML, "Movimiento de venta Mercado Libre", "ID exacto vinculado a una operación settlement reconocida por el motor ML."
    elif m.importe_neto > 0 and any(x in texto for x in ("rendimiento", "código qr", "codigo qr", "programa de protección", "programa de proteccion")):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original aporta evidencia explícita de un ingreso no ML."
    else:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE, "Origen no determinado", "No existe vínculo settlement inequívoco ni evidencia suficiente en el estado de cuenta."
    accion = "Revisar con un settlement que cubra la fecha de origen." if categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE else "Sin acción; conservar para trazabilidad."
    return MovimientoEstadoCuentaClasificado(m, estado, categoria, subtipo, motivo, accion, getattr(settlement, "numero_fila_origen", None), grupo)
