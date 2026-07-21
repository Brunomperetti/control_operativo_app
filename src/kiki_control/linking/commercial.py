"""Motor puro de vinculación comercial entre Mercado Libre oficial y Eccomapp."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import Decimal

from kiki_control.domain.commercial_link import (
    EstadoValidacionSku,
    EstadoVinculacionComercial,
    MetodoVinculacionComercial,
    ReporteVinculacionComercial,
    ResultadoVinculacionComercial,
)
from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.official_sale import VentaOficialMercadoLibre

_IDENTIDAD_VENTA = tuple[str, int]
_IDENTIDAD_ECCOMAPP = tuple[str, int]

_ESTADOS_ML_SIN_REVISION = (
    "cancel",
    "devol",
    "reembols",
    "anulad",
)


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _grupo(op: OperacionComercial) -> str:
    return _texto(op.id_carrito) or str(op.id_orden).strip()


def _identidad_venta(venta: VentaOficialMercadoLibre) -> _IDENTIDAD_VENTA:
    return (venta.hash_importacion, venta.fila_origen)


def _identidad_eccomapp(op: OperacionComercial) -> _IDENTIDAD_ECCOMAPP:
    return (op.hash_importacion, op.numero_fila_origen)


def _ordenar_ops(ops: Iterable[OperacionComercial]) -> tuple[OperacionComercial, ...]:
    return tuple(sorted(ops, key=lambda op: (_grupo(op), str(op.id_orden), op.numero_fila_origen, op.hash_importacion)))


def _ordenar_ventas(ventas: Iterable[VentaOficialMercadoLibre]) -> tuple[VentaOficialMercadoLibre, ...]:
    return tuple(sorted(ventas, key=lambda v: (str(v.id_venta), v.hash_importacion, v.fila_origen)))


def _sku(s: str | None) -> str | None:
    t = _texto(s)
    return t.upper() if t else None


def _validar_sku(ventas: Iterable[VentaOficialMercadoLibre], ops: Iterable[OperacionComercial]) -> EstadoValidacionSku:
    sku_ml = {_sku(v.sku) for v in ventas if _sku(v.sku)}
    sku_ec = {_sku(op.sku) for op in ops if _sku(op.sku)}
    if not sku_ml and not sku_ec:
        return EstadoValidacionSku.NO_DISPONIBLE_EN_AMBAS
    if not sku_ml:
        return EstadoValidacionSku.FALTA_EN_MERCADO_LIBRE
    if not sku_ec:
        return EstadoValidacionSku.FALTA_EN_ECCOMAPP
    if sku_ml == sku_ec:
        return EstadoValidacionSku.COINCIDE
    return EstadoValidacionSku.DIFIERE


def _importe_cero(valor: Decimal | None) -> bool:
    return valor is not None and valor == Decimal("0")


def _solo_ml_requiere_revision(venta: VentaOficialMercadoLibre) -> bool:
    estado = " ".join(
        texto for texto in (_texto(venta.estado), _texto(venta.descripcion_estado)) if texto
    ).lower()
    parece_cancelada_o_devuelta = any(patron in estado for patron in _ESTADOS_ML_SIN_REVISION)
    return not (parece_cancelada_o_devuelta and _importe_cero(venta.total_informado_ml))


def _resultado(
    *,
    clave: str,
    grupo: str | None,
    ventas: Iterable[VentaOficialMercadoLibre],
    ops: Iterable[OperacionComercial],
    principal: VentaOficialMercadoLibre | None,
    estado: EstadoVinculacionComercial,
    metodos: Iterable[MetodoVinculacionComercial],
    motivos: Iterable[str],
    explicaciones: Iterable[str],
    revision: bool,
) -> ResultadoVinculacionComercial:
    ventas_t = _ordenar_ventas(ventas)
    ops_t = _ordenar_ops(ops)
    detalle = tuple(v for v in ventas_t if v is not principal)
    sku = _validar_sku(ventas_t, ops_t)
    motivos_l = list(dict.fromkeys(motivos))
    explicaciones_l = list(dict.fromkeys(explicaciones))
    if sku == EstadoValidacionSku.DIFIERE:
        motivos_l.append("SKU_DIFIERE")
        explicaciones_l.append(
            "Los conjuntos de SKU no vacíos difieren entre Mercado Libre oficial y Eccomapp; "
            "la vinculación por ID se conserva para revisión."
        )
        revision = True
        if estado == EstadoVinculacionComercial.VINCULADA:
            estado = EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES
    ids_orden = tuple(sorted({_texto(op.id_orden) or "" for op in ops_t}))
    carritos = sorted({_texto(op.id_carrito) for op in ops_t if _texto(op.id_carrito)})
    return ResultadoVinculacionComercial(
        clave_resultado=clave,
        id_grupo_canonico=grupo,
        id_carrito=carritos[0] if len(carritos) == 1 else None,
        ids_orden=ids_orden,
        venta_principal_ml=principal,
        ventas_detalle_ml=detalle,
        operaciones_eccomapp=ops_t,
        estado=estado,
        metodos_vinculacion=tuple(sorted(set(metodos), key=lambda m: m.value)),
        estado_validacion_sku=sku,
        requiere_revision=revision,
        motivos=tuple(motivos_l),
        explicaciones=tuple(explicaciones_l),
        hashes_importacion_ml=tuple(sorted({v.hash_importacion for v in ventas_t})),
        hashes_importacion_eccomapp=tuple(sorted({op.hash_importacion for op in ops_t})),
        filas_origen_ml=tuple(sorted({v.fila_origen for v in ventas_t})),
        filas_origen_eccomapp=tuple(sorted({op.numero_fila_origen for op in ops_t})),
    )


def _validar_particion(
    ventas: tuple[VentaOficialMercadoLibre, ...],
    ops: tuple[OperacionComercial, ...],
    resultados: tuple[ResultadoVinculacionComercial, ...],
) -> None:
    ventas_entrada = Counter(_identidad_venta(v) for v in ventas)
    ops_entrada = Counter(_identidad_eccomapp(op) for op in ops)
    ventas_salida = Counter(
        _identidad_venta(v)
        for r in resultados
        for v in ((r.venta_principal_ml,) if r.venta_principal_ml else ()) + r.ventas_detalle_ml
    )
    ops_salida = Counter(_identidad_eccomapp(op) for r in resultados for op in r.operaciones_eccomapp)
    if ventas_salida != ventas_entrada or ops_salida != ops_entrada:
        raise AssertionError("El reporte de vinculación comercial no conserva una partición exacta de los registros de entrada.")


def vincular_ventas_oficiales_con_eccomapp(
    ventas_oficiales: Iterable[VentaOficialMercadoLibre],
    operaciones_eccomapp: Iterable[OperacionComercial],
) -> ReporteVinculacionComercial:
    """Vincula ventas oficiales con operaciones Eccomapp por carrito u orden, sin efectos colaterales."""
    ventas = _ordenar_ventas(tuple(ventas_oficiales))
    ops = _ordenar_ops(tuple(operaciones_eccomapp))
    grupos: dict[str, list[OperacionComercial]] = defaultdict(list)
    carritos: dict[str, set[str]] = defaultdict(set)
    ordenes: dict[str, set[str]] = defaultdict(set)
    ops_por_orden: dict[str, list[OperacionComercial]] = defaultdict(list)
    for op in ops:
        g = _grupo(op)
        grupos[g].append(op)
        ordenes[str(op.id_orden).strip()].add(g)
        ops_por_orden[str(op.id_orden).strip()].append(op)
        carrito = _texto(op.id_carrito)
        if carrito:
            carritos[carrito].add(g)

    ordenes_conflictivas = {
        oid
        for oid, grupos_de_orden in ordenes.items()
        if len(grupos_de_orden) > 1
        or len({_texto(o.id_carrito) for o in ops_por_orden[oid]}) > 1
        or len(ops_por_orden[oid]) > 1
    }
    grupos_con_conflictos = {g for oid in ordenes_conflictivas for g in ordenes.get(oid, set())}
    ids_venta_duplicados = {id_venta for id_venta, cantidad in Counter(str(v.id_venta).strip() for v in ventas).items() if cantidad > 1}

    asignadas: dict[str, list[VentaOficialMercadoLibre]] = defaultdict(list)
    metodos: dict[str, set[MetodoVinculacionComercial]] = defaultdict(set)
    principales: dict[str, list[VentaOficialMercadoLibre]] = defaultdict(list)
    resultados: list[ResultadoVinculacionComercial] = []

    for id_duplicado in sorted(ids_venta_duplicados):
        ventas_duplicadas = tuple(v for v in ventas if str(v.id_venta).strip() == id_duplicado)
        resultados.append(
            _resultado(
                clave=f"duplicada-ml:{id_duplicado}",
                grupo=None,
                ventas=ventas_duplicadas,
                ops=(),
                principal=None,
                estado=EstadoVinculacionComercial.DUPLICADA,
                metodos=(MetodoVinculacionComercial.SIN_VINCULO,),
                motivos=("ID_VENTA_MERCADO_LIBRE_DUPLICADO",),
                explicaciones=(
                    "Dos o más filas oficiales tienen el mismo # de venta; quedan en revisión sin vincularse silenciosamente.",
                ),
                revision=True,
            )
        )

    for v in ventas:
        vid = str(v.id_venta).strip()
        if vid in ids_venta_duplicados:
            continue
        via_carrito = set(carritos.get(vid, set()))
        via_orden = set(ordenes.get(vid, set()))
        destinos = via_carrito | via_orden
        if len(destinos) > 1:
            resultados.append(
                _resultado(
                    clave=f"ambigua-ml:{vid}:{v.hash_importacion}:{v.fila_origen}",
                    grupo=None,
                    ventas=(v,),
                    ops=(),
                    principal=None,
                    estado=EstadoVinculacionComercial.AMBIGUA,
                    metodos=(MetodoVinculacionComercial.SIN_VINCULO,),
                    motivos=("ID_CONDUCE_A_MULTIPLES_GRUPOS",),
                    explicaciones=(
                        "El identificador coincide con más de un grupo canónico; queda en revisión sin elegir automáticamente.",
                    ),
                    revision=True,
                )
            )
            continue
        if vid in ordenes_conflictivas:
            resultados.append(
                _resultado(
                    clave=f"duplicada-order-ml:{vid}:{v.hash_importacion}:{v.fila_origen}",
                    grupo=None,
                    ventas=(v,),
                    ops=(),
                    principal=None,
                    estado=EstadoVinculacionComercial.DUPLICADA,
                    metodos=(MetodoVinculacionComercial.SIN_VINCULO,),
                    motivos=("ID_ORDER_ECCOMAPP_DUPLICADO",),
                    explicaciones=(
                        "El ID Order de Eccomapp está repetido o asociado a más de un carrito; la venta queda en revisión sin forzar vínculo.",
                    ),
                    revision=True,
                )
            )
            continue
        if len(destinos) == 1:
            g = next(iter(destinos))
            asignadas[g].append(v)
            if vid in via_carrito:
                metodos[g].add(MetodoVinculacionComercial.ID_CARRITO)
                principales[g].append(v)
            elif any(_texto(op.id_carrito) for op in grupos[g]):
                metodos[g].add(MetodoVinculacionComercial.ID_ORDER_DENTRO_DE_CARRITO)
            else:
                metodos[g].add(MetodoVinculacionComercial.ID_ORDER)
                principales[g].append(v)
            continue
        revision = _solo_ml_requiere_revision(v)
        explicacion = (
            "No se encontró contraparte por ID Carrito ni ID Order en Eccomapp; requiere revisión porque "
            "puede faltar el costo de producto de una venta activa o con importe comercial."
            if revision
            else "No se encontró contraparte por ID Carrito ni ID Order en Eccomapp; por estado cancelado/devuelto/reembolsado "
            "y total comercial cero puede corresponder a cancelación, devolución, diferencia de cobertura u operación no incluida."
        )
        resultados.append(
            _resultado(
                clave=f"solo-ml:{vid}:{v.hash_importacion}:{v.fila_origen}",
                grupo=None,
                ventas=(v,),
                ops=(),
                principal=None,
                estado=EstadoVinculacionComercial.SOLO_MERCADO_LIBRE,
                metodos=(MetodoVinculacionComercial.SIN_VINCULO,),
                motivos=("SIN_CONTRAPARTE_ECCOMAPP",),
                explicaciones=(explicacion,),
                revision=revision,
            )
        )

    for g in sorted(grupos):
        ps = principales[g]
        motivos: list[str] = []
        explicaciones: list[str] = []
        revision = False
        estado = EstadoVinculacionComercial.VINCULADA if g in asignadas else EstadoVinculacionComercial.SOLO_ECCOMAPP
        metodos_grupo = metodos[g] if g in asignadas else {MetodoVinculacionComercial.SIN_VINCULO}
        if g in grupos_con_conflictos:
            estado = EstadoVinculacionComercial.DUPLICADA if g not in asignadas else EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES
            revision = True
            motivos.append("GRUPO_ECCOMAPP_CON_CONFLICTO_DE_IDENTIDAD")
            explicaciones.append(
                "El grupo Eccomapp contiene al menos un ID Order duplicado o asociado a más de un carrito; "
                "las operaciones se conservan una sola vez en su grupo canónico."
            )
        if g in asignadas and len(ps) != 1:
            if estado == EstadoVinculacionComercial.VINCULADA:
                estado = EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES
            revision = True
            motivos.append("VENTA_PRINCIPAL_ML_FALTANTE_O_MULTIPLE")
            explicaciones.append(
                "El grupo conserva sus relaciones, pero falta la venta principal de carrito o aparece más de una principal."
            )
        if g not in asignadas:
            revision = True
            motivos.append("SIN_CONTRAPARTE_MERCADO_LIBRE")
            explicaciones.append("No se encontró contraparte en el archivo oficial de Mercado Libre cargado.")
        resultados.append(
            _resultado(
                clave=f"grupo:{g}",
                grupo=g,
                ventas=asignadas[g],
                ops=grupos[g],
                principal=ps[0] if len(ps) == 1 else None,
                estado=estado,
                metodos=metodos_grupo,
                motivos=motivos,
                explicaciones=explicaciones,
                revision=revision,
            )
        )

    resultados_t = tuple(sorted(resultados, key=lambda r: r.clave_resultado))
    _validar_particion(ventas, ops, resultados_t)
    cuenta = lambda e: sum(1 for r in resultados_t if r.estado == e)
    vinculados = [
        r
        for r in resultados_t
        if r.estado in (EstadoVinculacionComercial.VINCULADA, EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES)
    ]
    return ReporteVinculacionComercial(
        resultados=resultados_t,
        total_ventas_oficiales_recibidas=len(ventas),
        total_operaciones_eccomapp_recibidas=len(ops),
        total_grupos_eccomapp=len(grupos),
        total_grupos_vinculados=len(vinculados),
        total_vinculados_sin_observaciones=cuenta(EstadoVinculacionComercial.VINCULADA),
        total_vinculados_con_observaciones=cuenta(EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES),
        total_solo_mercado_libre=cuenta(EstadoVinculacionComercial.SOLO_MERCADO_LIBRE),
        total_solo_eccomapp=cuenta(EstadoVinculacionComercial.SOLO_ECCOMAPP),
        total_ambiguos=cuenta(EstadoVinculacionComercial.AMBIGUA),
        total_duplicados=cuenta(EstadoVinculacionComercial.DUPLICADA),
        total_requieren_revision=sum(1 for r in resultados_t if r.requiere_revision),
        hashes_importacion_ml=tuple(sorted({v.hash_importacion for v in ventas})),
        hashes_importacion_eccomapp=tuple(sorted({op.hash_importacion for op in ops})),
    )
