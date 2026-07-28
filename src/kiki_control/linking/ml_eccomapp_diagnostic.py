"""Diagnóstico auditable derivado del vinculador comercial canónico."""

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from kiki_control.domain.commercial_link import EstadoVinculacionComercial, ResultadoVinculacionComercial
from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.ml_eccomapp_diagnostic import (
    CasoCruceMlEccomapp,
    DiagnosticoMlEccomapp,
    EstadoAptitudUtilidad,
    EstadoCruceMlEccomapp,
)
from kiki_control.domain.official_sale import VentaOficialMercadoLibre
from kiki_control.linking.commercial import vincular_ventas_oficiales_con_eccomapp


def _id(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _grupo_ec(op: OperacionComercial) -> str | None:
    return _id(op.id_carrito) or _id(op.id_orden)


def _identidad_ml(v: VentaOficialMercadoLibre) -> tuple[str, int]:
    return v.hash_importacion, v.fila_origen


def _identidad_ec(op: OperacionComercial) -> tuple[str, int]:
    return op.hash_importacion, op.numero_fila_origen


def _sumar_completo(values: Iterable[Decimal | None]) -> Decimal | None:
    vals = tuple(values)
    return None if not vals or any(v is None for v in vals) else sum(vals, Decimal("0"))  # type: ignore[arg-type]


def _estado_resultado(r: ResultadoVinculacionComercial) -> EstadoCruceMlEccomapp:
    if r.estado == EstadoVinculacionComercial.AMBIGUA:
        return EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO
    if r.estado == EstadoVinculacionComercial.DUPLICADA:
        if any("ECCOMAPP" in motivo or "ORDER" in motivo for motivo in r.motivos):
            return EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP
        return EstadoCruceMlEccomapp.DUPLICADO_ML
    if r.estado == EstadoVinculacionComercial.SOLO_MERCADO_LIBRE:
        return EstadoCruceMlEccomapp.SOLO_ML
    if r.estado == EstadoVinculacionComercial.SOLO_ECCOMAPP:
        return EstadoCruceMlEccomapp.SOLO_ECCOMAPP
    if "GRUPO_ECCOMAPP_CON_CONFLICTO_DE_IDENTIDAD" in r.motivos:
        return EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP
    ventas = ((r.venta_principal_ml,) if r.venta_principal_ml else ()) + r.ventas_detalle_ml
    es_grupo = len(ventas) > 1 or len(r.operaciones_eccomapp) > 1 or r.id_carrito is not None
    return EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO if es_grupo else EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA


def _total_ml(r: ResultadoVinculacionComercial | None, ventas: tuple[VentaOficialMercadoLibre, ...]) -> Decimal | None:
    """Usa la venta principal de carrito como total, evitando sumar detalles dos veces."""
    if r is not None and r.venta_principal_ml is not None:
        return r.venta_principal_ml.total_informado_ml
    if len(ventas) == 1:
        return ventas[0].total_informado_ml
    return None


def _caso(
    clave: str,
    grupo: str | None,
    ventas: Iterable[VentaOficialMercadoLibre],
    ops: Iterable[OperacionComercial],
    estado: EstadoCruceMlEccomapp,
    motivo: str,
    accion: str,
    resultado: ResultadoVinculacionComercial | None = None,
) -> CasoCruceMlEccomapp:
    ventas_t = tuple(sorted(ventas, key=lambda v: (v.fila_origen, v.hash_importacion)))
    ops_t = tuple(sorted(ops, key=lambda o: (o.numero_fila_origen, o.hash_importacion)))
    total = _total_ml(resultado, ventas_t)
    costo = _sumar_completo(o.costo_total_con_iva for o in ops_t)
    if estado in {EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO, EstadoCruceMlEccomapp.DUPLICADO_ML, EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP}:
        aptitud = EstadoAptitudUtilidad.VINCULO_AMBIGUO
    elif estado == EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO:
        aptitud = EstadoAptitudUtilidad.DATOS_CRITICOS_INCOMPLETOS
    elif not ops_t:
        aptitud = EstadoAptitudUtilidad.SIN_VINCULO_ECCOMAPP
    elif not ventas_t:
        aptitud = EstadoAptitudUtilidad.DATOS_CRITICOS_INCOMPLETOS
    elif total is None:
        aptitud = EstadoAptitudUtilidad.SIN_TOTAL_ML
    elif costo is None or costo < 0:
        aptitud = EstadoAptitudUtilidad.SIN_COSTO
    else:
        aptitud = EstadoAptitudUtilidad.UTILIDAD_CALCULABLE
    return CasoCruceMlEccomapp(
        clave=clave,
        id_grupo=grupo,
        ids_venta_ml=tuple(sorted({_id(v.id_venta) for v in ventas_t if _id(v.id_venta)})),
        ids_orden_eccomapp=tuple(sorted({_id(o.id_orden) for o in ops_t if _id(o.id_orden)})),
        ventas_ml=ventas_t,
        operaciones_eccomapp=ops_t,
        estado=estado,
        aptitud_utilidad=aptitud,
        motivo=motivo,
        accion_recomendada=accion,
        fecha=next((v.fecha_venta for v in ventas_t if v.fecha_venta), next((o.fecha_hora_venta for o in ops_t), None)),
        total_ml=total,
        costo_eccomapp=costo,
    )


def _validar_particion(ventas, ops, casos) -> None:
    entrada_ml = Counter(_identidad_ml(v) for v in ventas)
    entrada_ec = Counter(_identidad_ec(o) for o in ops)
    salida_ml = Counter(_identidad_ml(v) for c in casos for v in c.ventas_ml)
    salida_ec = Counter(_identidad_ec(o) for c in casos for o in c.operaciones_eccomapp)
    if entrada_ml != salida_ml or entrada_ec != salida_ec:
        raise AssertionError("El diagnóstico no conserva exactamente las identidades de todas las filas originales.")
    if any(frecuencia != 1 for frecuencia in salida_ml.values()) or any(frecuencia != 1 for frecuencia in salida_ec.values()):
        raise AssertionError("Una identidad de fila aparece más de una vez en el diagnóstico.")


def diagnosticar_ml_eccomapp(
    ventas_ml: Iterable[VentaOficialMercadoLibre],
    operaciones_eccomapp: Iterable[OperacionComercial],
) -> DiagnosticoMlEccomapp:
    """Adapta la partición del vinculador comercial; no implementa otro motor de identidad."""
    ventas = tuple(ventas_ml)
    ops = tuple(operaciones_eccomapp)
    ventas_validas = tuple(v for v in ventas if _id(v.id_venta))
    ventas_incompletas = tuple(v for v in ventas if not _id(v.id_venta))
    ops_validas = tuple(o for o in ops if _grupo_ec(o))
    ops_incompletas = tuple(o for o in ops if not _grupo_ec(o))
    reporte = vincular_ventas_oficiales_con_eccomapp(ventas_validas, ops_validas)
    casos: list[CasoCruceMlEccomapp] = []

    if ventas_incompletas:
        casos.append(_caso("incompleto-ml", None, ventas_incompletas, (), EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO, "Falta el identificador comercial esencial en ML.", "Completar o recuperar el ID de venta en el archivo de origen."))
    if ops_incompletas:
        casos.append(_caso("incompleto-ec", None, (), ops_incompletas, EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO, "Faltan ID de orden y carrito en Eccomapp.", "Completar el identificador comercial en Eccomapp."))

    for r in reporte.resultados:
        ventas_r = ((r.venta_principal_ml,) if r.venta_principal_ml else ()) + r.ventas_detalle_ml
        estado = _estado_resultado(r)
        grupo = r.id_grupo_canonico
        if grupo is None and estado == EstadoCruceMlEccomapp.SOLO_ML and len(ventas_r) == 1:
            grupo = _id(ventas_r[0].id_venta)
        motivo = " ".join(r.explicaciones) or "Clasificación derivada del vinculador comercial canónico."
        accion = {
            EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA: "Sin acción.",
            EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO: "Conservar la comparación consolidada del carrito u orden.",
            EstadoCruceMlEccomapp.SOLO_ML: "Verificar identidad y cobertura del archivo Eccomapp.",
            EstadoCruceMlEccomapp.SOLO_ECCOMAPP: "Verificar identidad y cobertura del archivo oficial ML.",
        }.get(estado, "Resolver la identidad comercial antes de calcular utilidad.")
        casos.append(_caso(r.clave_resultado, grupo, ventas_r, r.operaciones_eccomapp, estado, motivo, accion, r))

    casos_t = tuple(sorted(casos, key=lambda c: c.clave))
    _validar_particion(ventas, ops, casos_t)
    count = lambda state: sum(c.estado == state for c in casos_t)
    duplicadas = count(EstadoCruceMlEccomapp.DUPLICADO_ML) + count(EstadoCruceMlEccomapp.DUPLICADO_ECCOMAPP)
    aptas = sum(c.aptitud_utilidad == EstadoAptitudUtilidad.UTILIDAD_CALCULABLE for c in casos_t)
    estados_grupo_ml = {EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA, EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO, EstadoCruceMlEccomapp.SOLO_ML}
    grupos_ml = {c.id_grupo for c in casos_t if c.id_grupo is not None and c.ventas_ml and c.estado in estados_grupo_ml}
    grupos_ec = {_grupo_ec(o) for o in ops_validas if _grupo_ec(o) is not None}
    diag = DiagnosticoMlEccomapp(
        casos=casos_t,
        cantidad_filas_ml=len(ventas),
        cantidad_ventas_unicas_ml=len({_id(v.id_venta) for v in ventas_validas}),
        cantidad_grupos_ml=len(grupos_ml),
        cantidad_filas_eccomapp=len(ops),
        cantidad_operaciones_unicas_eccomapp=len({_id(o.id_orden) for o in ops_validas if _id(o.id_orden)}),
        cantidad_grupos_eccomapp=len(grupos_ec),
        cantidad_coincidencias_exactas=count(EstadoCruceMlEccomapp.COINCIDENCIA_EXACTA),
        cantidad_coincidencias_por_grupo=count(EstadoCruceMlEccomapp.COINCIDENCIA_POR_GRUPO),
        cantidad_solo_ml=count(EstadoCruceMlEccomapp.SOLO_ML),
        cantidad_solo_eccomapp=count(EstadoCruceMlEccomapp.SOLO_ECCOMAPP),
        cantidad_identificador_incompleto=count(EstadoCruceMlEccomapp.IDENTIFICADOR_INCOMPLETO),
        cantidad_ambiguas=count(EstadoCruceMlEccomapp.IDENTIFICADOR_AMBIGUO),
        cantidad_duplicadas=duplicadas,
        cantidad_apta_utilidad=aptas,
        cantidad_no_apta_utilidad=len(casos_t) - aptas,
    )
    categorias = (diag.cantidad_coincidencias_exactas, diag.cantidad_coincidencias_por_grupo, diag.cantidad_solo_ml, diag.cantidad_solo_eccomapp, diag.cantidad_identificador_incompleto, diag.cantidad_ambiguas, diag.cantidad_duplicadas)
    if sum(categorias) != len(casos_t):
        raise AssertionError("Las categorías excluyentes no cierran con el universo de casos.")
    return diag
