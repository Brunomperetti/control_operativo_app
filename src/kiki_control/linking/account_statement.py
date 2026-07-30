"""Vinculación exacta y clasificación excluyente del estado de cuenta."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
import logging
from time import perf_counter
from typing import Any
import unicodedata

from kiki_control.domain.account_statement import (
    CategoriaEstadoCuentaMp,
    ControlEstadoCuentaMp,
    EstadoVinculacionEstadoCuentaMp,
    EvidenciaComercialOperacionMp,
    GrupoSettlementPorOperacionMp,
    MovimientoEstadoCuentaClasificado,
    OrigenComercialOperacionMp,
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
    inicio = perf_counter()
    ids_requeridos = {m.reference_id.strip() for m in resumen.movimientos
                      if m.reference_id and m.reference_id.strip()}
    # Un único recorrido: B2/B3 no agrupa ni enriquece las decenas de miles
    # de operaciones ajenas a los reference IDs del Statement seleccionado.
    seleccionados = tuple(m for m in movimientos_settlement
                          if str(getattr(m, "id_operacion_mercado_pago", "") or "").strip()
                          in ids_requeridos)
    grupos = agrupar_settlement_por_operacion(seleccionados, operacion_a_grupo_ml)
    evidencias = construir_evidencias_comerciales_operaciones(grupos)
    clasificados = tuple(_clasificar(m, grupos, evidencias) for m in resumen.movimientos)
    encontrados = ids_requeridos.intersection(grupos)
    logging.getLogger(__name__).info(
        "Clasificación Statement: ids_requeridos=%d ids_encontrados=%d filas_seleccionadas=%d tiempo_segundos=%.3f",
        len(ids_requeridos), len(encontrados), len(seleccionados), perf_counter() - inicio,
    )
    return ControlEstadoCuentaMp(resumen, clasificados, (
        ("IDs requeridos por Statement", str(len(ids_requeridos))),
        ("IDs encontrados en Settlement", str(len(encontrados))),
        ("Filas Settlement retenidas para B2/B3", str(len(seleccionados))),
    ))


def construir_evidencias_comerciales_operaciones(
    grupos: Mapping[str, GrupoSettlementPorOperacionMp],
) -> dict[str, EvidenciaComercialOperacionMp]:
    """Resuelve evidencia histórica desde el Settlement completo, separada de B1."""
    resultado = {}
    for operacion, grupo in grupos.items():
        canales = tuple(c.casefold() for c in grupo.canales)
        plataformas = tuple(p.casefold() for p in grupo.plataformas)
        canal_ml = any("mercado libre" in c for c in canales)
        canal_mp = any("mercado pago" in c for c in canales)
        qr = any("código qr" in p or "codigo qr" in p or "qr" == p.strip() for p in plataformas)
        point = any("point" in p for p in plataformas)
        evidencia = []
        if grupo.es_ambiguo or len(grupo.ids_grupo_ml) > 1 or (canal_ml and (canal_mp or qr or point)):
            origen = OrigenComercialOperacionMp.AMBIGUO
            evidencia.append(grupo.motivo_ambiguedad or "El Settlement mezcla evidencia ML y Mercado Pago/QR/Point.")
        elif grupo.ids_grupo_ml:
            origen = OrigenComercialOperacionMp.MERCADO_LIBRE_PERIODO_B1
            evidencia.append("Vínculo canónico con un grupo ML del período B1.")
        elif canal_ml and grupo.ids_orden and not (qr or point or canal_mp):
            origen = OrigenComercialOperacionMp.MERCADO_LIBRE_HISTORICO
            evidencia.extend(("Canal de venta Mercado Libre.", "ID de orden ML presente en una agrupación Settlement coherente."))
        elif qr and not canal_ml:
            origen = OrigenComercialOperacionMp.MERCADO_PAGO_QR
            evidencia.append("Plataforma Código QR informada por el Settlement.")
        elif point and not canal_ml:
            origen = OrigenComercialOperacionMp.MERCADO_PAGO_POINT
            evidencia.append("Plataforma Point informada por el Settlement.")
        elif grupo.canales or grupo.plataformas:
            origen = OrigenComercialOperacionMp.OTRO
            evidencia.append("El Settlement aporta canal o plataforma no ML.")
        else:
            origen = OrigenComercialOperacionMp.NO_DETERMINADO
            evidencia.append("El Settlement no aporta evidencia comercial suficiente.")
        resultado[operacion] = EvidenciaComercialOperacionMp(
            operacion, origen, tuple(evidencia), grupo.filas_origen, grupo.canales,
            grupo.plataformas, grupo.ids_orden, origen == OrigenComercialOperacionMp.AMBIGUO,
            grupo.motivo_ambiguedad if origen == OrigenComercialOperacionMp.AMBIGUO else None,
            grupo.ids_grupo_ml[0] if len(grupo.ids_grupo_ml) == 1 else None,
        )
    return resultado


def _clasificar(m: Any, grupos: Mapping[str, GrupoSettlementPorOperacionMp],
                evidencias: Mapping[str, EvidenciaComercialOperacionMp]) -> MovimientoEstadoCuentaClasificado:
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
    texto = _texto_normalizado(m.tipo_movimiento_original)
    canales = tuple(c.casefold() for c in coherente.canales) if coherente else tuple()
    plataformas = tuple(p.casefold() for p in coherente.plataformas) if coherente else tuple()
    id_grupo_ml = coherente.ids_grupo_ml[0] if coherente and len(coherente.ids_grupo_ml) == 1 else None
    evidencia = evidencias.get(m.reference_id or "")
    es_reintegro_comision = any(x in texto for x in (
        "reintegro de comision", "reintegro de comisiones", "reintegro comision",
        "reintegro comisiones", "devolucion de comision cobrada",
        "devolucion de comisiones cobradas",
    ))
    # Una salida inequívoca identifica expresamente un egreso financiero no
    # comercial. Los ajustes genéricos se registran aparte: no acreditan canal.
    salida_no_ml_inequivoca = any(x in texto for x in (
        "transferencia enviada", "pago a tercero", "pago a proveedor",
        "pago de servicio", "retiro", "extraccion", "envio de dinero",
        "debito por transferencia", "salida de dinero",
    ))
    ajuste_comercial_generico = any(x in texto for x in (
        "devolucion", "reclamo", "impuesto", "comision", "retencion",
        "cancelacion", "cancelada", "contracargo", "ajuste", "dinero retenido",
    ))
    # La evidencia canónica ML prevalece sobre el signo y sobre el tipo: una
    # devolución, retención o comisión vinculada continúa perteneciendo a ML.
    if evidencia and evidencia.origen_comercial == OrigenComercialOperacionMp.AMBIGUO:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE, "Evidencia contradictoria", " ".join(evidencia.evidencia)
    elif evidencia and evidencia.origen_comercial == OrigenComercialOperacionMp.MERCADO_LIBRE_PERIODO_B1:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML, "Movimiento de venta Mercado Libre", "El motor consolidado vinculó las filas settlement a un único grupo ML canónico."
    elif evidencia and evidencia.origen_comercial == OrigenComercialOperacionMp.MERCADO_LIBRE_HISTORICO:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.ASOCIADO_A_VENTA_ML, "Movimiento de operación Mercado Libre histórica", " ".join(evidencia.evidencia)
    elif evidencia and evidencia.origen_comercial == OrigenComercialOperacionMp.MERCADO_PAGO_QR and m.importe_neto > 0:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Venta por mostrador con Código QR", " ".join(evidencia.evidencia)
    elif evidencia and evidencia.origen_comercial == OrigenComercialOperacionMp.MERCADO_PAGO_POINT and m.importe_neto > 0:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Venta con Point", " ".join(evidencia.evidencia)
    elif m.importe_neto > 0 and es_reintegro_comision:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Reintegro de comisiones", "Account Statement — tipo explícito informado por Mercado Pago."
    elif m.importe_neto <= 0 and salida_no_ml_inequivoca:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SALIDA_O_AJUSTE_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original identifica explícitamente una salida o ajuste no vinculada a ML."
    elif coherente and m.importe_neto > 0 and ("mercado pago" in canales or any("código qr" in p or "codigo qr" in p for p in plataformas)):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, "Venta por mostrador con Código QR", "El settlement identifica canal Mercado Pago o plataforma Código QR y no pertenece a un grupo ML."
    elif m.importe_neto > 0 and any(x in texto for x in ("rendimiento", "codigo qr", "programa de proteccion")):
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.OTRO_INGRESO_NO_ML_IDENTIFICADO, m.tipo_movimiento_original, "El tipo original aporta evidencia explícita de un ingreso no ML."
    else:
        categoria, subtipo, motivo = CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE, "Origen no determinado", "No existe vínculo settlement inequívoco ni evidencia suficiente en el estado de cuenta."
        if ajuste_comercial_generico:
            subtipo = "Ajuste comercial genérico sin canal acreditado"
            motivo = "El tipo describe un ajuste comercial, pero no acredita si pertenece a Mercado Libre o a otro canal."
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
    evidencia_texto = evidencia.evidencia if evidencia else tuple()
    faltante = ("Canal o plataforma inequívocos y vínculo comercial de la operación."
                if categoria == CategoriaEstadoCuentaMp.SIN_ASOCIACION_SUFICIENTE else None)
    return MovimientoEstadoCuentaClasificado(
        m, estado, categoria, subtipo, motivo, accion, filas, id_grupo_ml,
        grupo_settlement.canales if grupo_settlement else tuple(),
        grupo_settlement.plataformas if grupo_settlement else tuple(),
        grupo_settlement.ids_orden if grupo_settlement else tuple(),
        evidencia_texto, faltante,
    )


def _valores(movimientos: Iterable[Any], atributo: str) -> tuple[str, ...]:
    return tuple(sorted({str(valor).strip() for m in movimientos if (valor := getattr(m, atributo, None)) is not None and str(valor).strip()}))


def _texto_normalizado(valor: object) -> str:
    """Normaliza variantes ortográficas sin depender de IDs ni importes."""
    texto = unicodedata.normalize("NFKD", str(valor).casefold())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())
