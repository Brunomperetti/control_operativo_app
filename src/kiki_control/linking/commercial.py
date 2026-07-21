"""Motor puro de vinculación comercial entre Mercado Libre oficial y Eccomapp."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from kiki_control.domain.commercial_link import (
    EstadoValidacionSku,
    EstadoVinculacionComercial,
    MetodoVinculacionComercial,
    ReporteVinculacionComercial,
    ResultadoVinculacionComercial,
)
from kiki_control.domain.commercial_operation import OperacionComercial
from kiki_control.domain.official_sale import VentaOficialMercadoLibre


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _grupo(op: OperacionComercial) -> str:
    return _texto(op.id_carrito) or str(op.id_orden).strip()


def _ordenar_ops(ops: Iterable[OperacionComercial]) -> tuple[OperacionComercial, ...]:
    return tuple(sorted(ops, key=lambda op: (_grupo(op), str(op.id_orden), op.numero_fila_origen, op.hash_importacion)))


def _ordenar_ventas(ventas: Iterable[VentaOficialMercadoLibre]) -> tuple[VentaOficialMercadoLibre, ...]:
    return tuple(sorted(ventas, key=lambda v: (str(v.id_venta), v.fila_origen, v.hash_importacion)))


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
    if sku_ml == sku_ec or (sku_ml & sku_ec and (sku_ml <= sku_ec or sku_ec <= sku_ml)):
        return EstadoValidacionSku.COINCIDE
    return EstadoValidacionSku.DIFIERE


def _resultado(
    *, clave: str, grupo: str | None, ventas: Iterable[VentaOficialMercadoLibre], ops: Iterable[OperacionComercial],
    principal: VentaOficialMercadoLibre | None, estado: EstadoVinculacionComercial,
    metodos: Iterable[MetodoVinculacionComercial], motivos: Iterable[str], explicaciones: Iterable[str], revision: bool,
) -> ResultadoVinculacionComercial:
    ventas_t = _ordenar_ventas(ventas)
    ops_t = _ordenar_ops(ops)
    detalle = tuple(v for v in ventas_t if v is not principal)
    sku = _validar_sku(ventas_t, ops_t)
    motivos_l = list(dict.fromkeys(motivos))
    explicaciones_l = list(dict.fromkeys(explicaciones))
    if sku == EstadoValidacionSku.DIFIERE:
        motivos_l.append("SKU_DIFIERE")
        explicaciones_l.append("Los SKU agregados del grupo difieren entre Mercado Libre oficial y Eccomapp; la vinculación por ID se conserva para revisión.")
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


def vincular_ventas_oficiales_con_eccomapp(
    ventas_oficiales: Iterable[VentaOficialMercadoLibre], operaciones_eccomapp: Iterable[OperacionComercial]
) -> ReporteVinculacionComercial:
    """Vincula ventas oficiales con operaciones Eccomapp por carrito u orden, sin efectos colaterales."""
    ventas = _ordenar_ventas(tuple(ventas_oficiales))
    ops = _ordenar_ops(tuple(operaciones_eccomapp))
    grupos: dict[str, list[OperacionComercial]] = defaultdict(list)
    carritos: dict[str, set[str]] = defaultdict(set)
    ordenes: dict[str, set[str]] = defaultdict(set)
    ops_por_orden: dict[str, list[OperacionComercial]] = defaultdict(list)
    for op in ops:
        g = _grupo(op); grupos[g].append(op); ordenes[str(op.id_orden).strip()].add(g); ops_por_orden[str(op.id_orden).strip()].append(op)
        if _texto(op.id_carrito): carritos[_texto(op.id_carrito) or ""].add(g)
    conflictos = {oid for oid, gl in ordenes.items() if len(gl) > 1 or len({_texto(o.id_carrito) for o in ops_por_orden[oid]}) > 1 or len(ops_por_orden[oid]) > 1}
    asignadas: dict[str, list[VentaOficialMercadoLibre]] = defaultdict(list); metodos = defaultdict(set); principales: dict[str, list[VentaOficialMercadoLibre]] = defaultdict(list)
    resultados: list[ResultadoVinculacionComercial] = []
    ventas_usadas: set[tuple[str, int, str]] = set(); grupos_conflictivos: set[str] = set()
    for v in ventas:
        vid = str(v.id_venta).strip(); via_carrito = set(carritos.get(vid, set())); via_orden = set(ordenes.get(vid, set()))
        destinos = via_carrito | via_orden; keyv = (v.id_venta, v.fila_origen, v.hash_importacion)
        if vid in conflictos:
            destinos |= via_orden
            for g in destinos: grupos_conflictivos.add(g)
            resultados.append(_resultado(clave=f"duplicada:ml:{vid}:{v.fila_origen}", grupo=None, ventas=(v,), ops=[op for g in destinos for op in grupos[g]], principal=None, estado=EstadoVinculacionComercial.DUPLICADA, metodos=(MetodoVinculacionComercial.SIN_VINCULO,), motivos=("ID_ORDER_ECCOMAPP_DUPLICADO",), explicaciones=("El ID Order de Eccomapp está repetido o asociado a más de un carrito; no se fuerza la vinculación.",), revision=True)); ventas_usadas.add(keyv); continue
        if len(destinos) > 1:
            for g in destinos: grupos_conflictivos.add(g)
            resultados.append(_resultado(clave=f"ambigua:ml:{vid}:{v.fila_origen}", grupo=None, ventas=(v,), ops=[op for g in destinos for op in grupos[g]], principal=None, estado=EstadoVinculacionComercial.AMBIGUA, metodos=(MetodoVinculacionComercial.SIN_VINCULO,), motivos=("ID_CONDUCE_A_MULTIPLES_GRUPOS",), explicaciones=("El identificador coincide con más de un grupo canónico; queda en revisión sin elegir automáticamente.",), revision=True)); ventas_usadas.add(keyv); continue
        if len(destinos) == 1:
            g = next(iter(destinos)); asignadas[g].append(v); ventas_usadas.add(keyv)
            if vid in via_carrito:
                metodos[g].add(MetodoVinculacionComercial.ID_CARRITO); principales[g].append(v)
            elif any(_texto(op.id_carrito) for op in grupos[g]): metodos[g].add(MetodoVinculacionComercial.ID_ORDER_DENTRO_DE_CARRITO)
            else: metodos[g].add(MetodoVinculacionComercial.ID_ORDER); principales[g].append(v)
        else:
            resultados.append(_resultado(clave=f"solo-ml:{vid}:{v.fila_origen}", grupo=None, ventas=(v,), ops=(), principal=None, estado=EstadoVinculacionComercial.SOLO_MERCADO_LIBRE, metodos=(MetodoVinculacionComercial.SIN_VINCULO,), motivos=("SIN_CONTRAPARTE_ECCOMAPP",), explicaciones=("No se encontró contraparte por ID Carrito ni ID Order en Eccomapp; puede ser cancelación, devolución, diferencia de cobertura u operación no incluida.",), revision=False)); ventas_usadas.add(keyv)
    for g in sorted(grupos):
        if g in grupos_conflictivos: continue
        if g in asignadas:
            ps = principales[g]; estado = EstadoVinculacionComercial.VINCULADA; revision = False; motivos=[]; expl=[]
            if len(ps) != 1:
                estado = EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES; revision=True; motivos.append("VENTA_PRINCIPAL_ML_FALTANTE_O_MULTIPLE"); expl.append("El grupo conserva sus relaciones, pero falta la venta principal de carrito o aparece más de una principal.")
            resultados.append(_resultado(clave=f"grupo:{g}", grupo=g, ventas=asignadas[g], ops=grupos[g], principal=ps[0] if len(ps)==1 else None, estado=estado, metodos=metodos[g], motivos=motivos, explicaciones=expl, revision=revision))
        else:
            resultados.append(_resultado(clave=f"solo-eccomapp:{g}", grupo=g, ventas=(), ops=grupos[g], principal=None, estado=EstadoVinculacionComercial.SOLO_ECCOMAPP, metodos=(MetodoVinculacionComercial.SIN_VINCULO,), motivos=("SIN_CONTRAPARTE_MERCADO_LIBRE",), explicaciones=("No se encontró contraparte en el archivo oficial de Mercado Libre cargado.",), revision=True))
    resultados_t = tuple(sorted(resultados, key=lambda r: r.clave_resultado))
    cuenta = lambda e: sum(1 for r in resultados_t if r.estado == e)
    vinculados = [r for r in resultados_t if r.estado in (EstadoVinculacionComercial.VINCULADA, EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES)]
    return ReporteVinculacionComercial(resultados_t, len(ventas), len(ops), len(grupos), len(vinculados), cuenta(EstadoVinculacionComercial.VINCULADA), cuenta(EstadoVinculacionComercial.VINCULADA_CON_OBSERVACIONES), cuenta(EstadoVinculacionComercial.SOLO_MERCADO_LIBRE), cuenta(EstadoVinculacionComercial.SOLO_ECCOMAPP), cuenta(EstadoVinculacionComercial.AMBIGUA), cuenta(EstadoVinculacionComercial.DUPLICADA), sum(1 for r in resultados_t if r.requiere_revision), tuple(sorted({v.hash_importacion for v in ventas})), tuple(sorted({op.hash_importacion for op in ops})))
