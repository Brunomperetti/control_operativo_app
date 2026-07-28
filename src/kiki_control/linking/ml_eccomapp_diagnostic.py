"""Diagnóstico determinista y auditable entre ventas oficiales y costos Eccomapp."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import Decimal

from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.ml_eccomapp_diagnostic import (
    CasoCruceMlEccomapp, DiagnosticoMlEccomapp, EstadoAptitudUtilidad, EstadoCruceMlEccomapp,
)
from kiki_control.domain.official_sale import VentaOficialMercadoLibre


def _id(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _grupo_ec(op: OperacionComercial) -> str | None:
    return _id(op.id_carrito) or _id(op.id_orden)


def _sumar_completo(values: Iterable[Decimal | None]) -> Decimal | None:
    vals = tuple(values)
    return None if not vals or any(v is None for v in vals) else sum(vals, Decimal("0"))  # type: ignore[arg-type]


def _caso(clave, grupo, ventas, ops, estado, motivo, accion):
    ventas = tuple(sorted(ventas, key=lambda v: (v.fila_origen, v.hash_importacion)))
    ops = tuple(sorted(ops, key=lambda o: (o.numero_fila_origen, o.hash_importacion)))
    total = _sumar_completo(v.total_informado_ml for v in ventas)
    costo = _sumar_completo(o.costo_total_con_iva for o in ops)
    if estado in {EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO, EstadoCruceMlEccomapp.DUPLICADO_ML, EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP}:
        aptitud = EstadoAptitudUtilidad.VINCULO_AMBIGUO
    elif estado == EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO:
        aptitud = EstadoAptitudUtilidad.DATOS_CRITICOS_INCOMPLETOS
    elif not ops:
        aptitud = EstadoAptitudUtilidad.SIN_VINCULO_ECCOMAPP
    elif total is None:
        aptitud = EstadoAptitudUtilidad.SIN_TOTAL_ML
    elif costo is None or costo < 0:
        aptitud = EstadoAptitudUtilidad.SIN_COSTO
    elif not ventas:
        aptitud = EstadoAptitudUtilidad.DATOS_CRITICOS_INCOMPLETOS
    else:
        aptitud = EstadoAptitudUtilidad.UTILIDAD_CALCULABLE
    return CasoCruceMlEccomapp(
        clave, grupo, tuple(sorted({_id(v.id_venta) or "" for v in ventas})),
        tuple(sorted({_id(o.id_orden) or "" for o in ops})), ventas, ops, estado, aptitud,
        motivo, accion, next((v.fecha_venta for v in ventas if v.fecha_venta), next((o.fecha_hora_venta for o in ops), None)), total, costo,
    )


def diagnosticar_ml_eccomapp(ventas_ml: Iterable[VentaOficialMercadoLibre], operaciones_eccomapp: Iterable[OperacionComercial]) -> DiagnosticoMlEccomapp:
    """Compara grupos comerciales; nunca usa posición, fecha, SKU ni importe como vínculo."""
    ventas = tuple(ventas_ml); ops = tuple(operaciones_eccomapp)
    ml_por_id = defaultdict(list); ec_por_grupo = defaultdict(list)
    for v in ventas: ml_por_id[_id(v.id_venta)].append(v)
    for o in ops: ec_por_grupo[_grupo_ec(o)].append(o)
    casos = []; ml_consumidas = set(); ec_consumidos = set()

    # Incompletos se conservan explícitamente, aunque los normalizadores normalmente los rechazan antes.
    for key, rows in ((None, ml_por_id.get(None, [])),):
        if rows:
            casos.append(_caso("incompleto-ml", None, rows, (), EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO, "Falta el identificador comercial esencial en ML.", "Completar o recuperar el ID de venta en el archivo de origen.")); ml_consumidas.add(key)
    if ec_por_grupo.get(None):
        casos.append(_caso("incompleto-ec", None, (), ec_por_grupo[None], EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO, "Faltan ID de orden y carrito en Eccomapp.", "Completar el identificador comercial en Eccomapp.")); ec_consumidos.add(None)

    # Índice inverso: un ID ML puede coincidir por carrito y por orden con grupos incompatibles.
    destinos = defaultdict(set)
    for group, group_ops in ec_por_grupo.items():
        if group is None: continue
        destinos[group].add(group)
        for op in group_ops:
            oid = _id(op.id_orden)
            if oid: destinos[oid].add(group)

    for mid, mrows in sorted(((k, v) for k, v in ml_por_id.items() if k is not None)):
        candidates = destinos.get(mid, set())
        duplicate_ml = len(mrows) > 1 and len({(_id(v.sku), _id(v.id_publicacion), v.total_informado_ml) for v in mrows}) < len(mrows)
        if duplicate_ml:
            casos.append(_caso(f"duplicado-ml:{mid}", mid, mrows, (), EstadoCruceMlEccomapp.DUPLICADO_ML, "El ID de venta repite filas comerciales indistinguibles; no se presume una composición válida.", "Revisar y deduplicar las filas oficiales.")); ml_consumidas.add(mid); continue
        if len(candidates) > 1:
            casos.append(_caso(f"ambiguo:{mid}", mid, mrows, (), EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO, "El mismo ID conduce a varios grupos Eccomapp incompatibles.", "Resolver la identidad de carrito/orden antes de calcular utilidad.")); ml_consumidas.add(mid); continue
        if len(candidates) == 1:
            group = next(iter(candidates)); erows = ec_por_grupo[group]
            duplicate_ec = len(erows) > 1 and len({(_id(o.id_order if hasattr(o, 'id_order') else o.id_orden), _id(o.sku), o.costo_total_con_iva) for o in erows}) < len(erows)
            if duplicate_ec:
                state = EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP; reason = "Eccomapp repite operaciones indistinguibles dentro del grupo."; action = "Revisar y deduplicar Eccomapp."
            else:
                grouped = len(mrows) > 1 or len(erows) > 1 or any(_id(o.id_carrito) for o in erows)
                state = EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO if grouped else EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA
                reason = "Vínculo inequívoco por carrito/orden normalizado." if grouped else "Vínculo uno a uno por ID comercial normalizado."
                action = "Sin acción." if state == EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA else "Conservar la comparación consolidada del grupo."
            casos.append(_caso(f"grupo:{group}", group, mrows, erows, state, reason, action)); ml_consumidas.add(mid); ec_consumidos.add(group)
        else:
            casos.append(_caso(f"solo-ml:{mid}", mid, mrows, (), EstadoCruceMlEccomapp.SOLO_ML, "No se encontró contraparte por carrito ni orden; puede existir una diferencia de cobertura.", "Verificar cobertura y buscar la operación en Eccomapp.")); ml_consumidas.add(mid)

    for group, erows in sorted(((k, v) for k, v in ec_por_grupo.items() if k is not None and k not in ec_consumidos)):
        duplicate = len(erows) > 1 and len({(_id(o.id_orden), _id(o.sku), o.costo_total_con_iva) for o in erows}) < len(erows)
        state = EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP if duplicate else EstadoCruceMlEccomapp.SOLO_ECCOMAPP
        reason = "Eccomapp repite operaciones indistinguibles." if duplicate else "No se encontró venta oficial por carrito ni orden; puede existir una diferencia de cobertura."
        casos.append(_caso(f"ec:{group}", group, (), erows, state, reason, "Revisar duplicados en Eccomapp." if duplicate else "Verificar cobertura del archivo oficial ML."))

    result = tuple(sorted(casos, key=lambda c: c.clave))
    ml_rows = sum(len(c.ventas_ml) for c in result); ec_rows = sum(len(c.operaciones_eccomapp) for c in result)
    if ml_rows != len(ventas) or ec_rows != len(ops): raise AssertionError("El diagnóstico no conserva exactamente todas las filas originales.")
    count = lambda s: sum(c.estado == s for c in result)
    duplicate_count = count(EstadoCruceMlEccomapp.DUPLICADO_ML) + count(EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP)
    apt = sum(c.aptitud_utilidad == EstadoAptitudUtilidad.UTILIDAD_CALCULABLE for c in result)
    diag = DiagnosticoMlEccomapp(result, len(ventas), len({_id(v.id_venta) for v in ventas if _id(v.id_venta)}), len(ml_por_id), len(ops), len({_id(o.id_orden) for o in ops if _id(o.id_orden)}), len(ec_por_grupo), count(EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA), count(EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO), count(EstadoCruceMlEccomapp.SOLO_ML), count(EstadoCruceMlEccomapp.SOLO_ECCOMAPP), count(EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO), count(EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO), duplicate_count, apt, len(result)-apt)
    if sum((diag.cantidad_coincidencias_exactas, diag.cantidad_coincidencias_por_grupo, diag.cantidad_solo_ml, diag.cantidad_solo_eccomapp, diag.cantidad_identificador_incompleto, diag.cantidad_ambiguas, diag.cantidad_duplicadas)) != len(result): raise AssertionError("Las categorías excluyentes no cierran con el universo de grupos.")
    return diag
