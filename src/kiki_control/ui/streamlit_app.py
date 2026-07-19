"""Interfaz Streamlit para conciliación Mercado Libre / Mercado Pago."""

from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.enums import TipoFuente
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.presentation.reconciliation_view import (
    clave_resultado,
    cobertura_archivos,
    conclusion_ejecutiva,
    detalle_cliente,
    detalle_tecnico_seguro,
    filas_presentacion,
    filtrar_filas,
    filtrar_resultados_por_vista,
    resumen_kpis,
    tabla_principal,
)
from kiki_control.reconciliation import reconciliar
from kiki_control.ui.session_cycle import (
    construir_firma_procesamiento,
    detectar_cambio,
    invalidar_resultados_conocidos,
    limpiar_claves_conocidas,
    tolerancia_canonica,
)

ZONA_DEFAULT = "America/Argentina/Cordoba"
TOLERANCIA_DEFAULT = "0,01"


def main() -> None:
    st.set_page_config(page_title="Kiki Control Financiero", layout="wide")
    _inicializar_estado()
    st.title("Kiki Control Financiero")
    st.subheader("Control cruzado Mercado Libre / Mercado Pago")
    st.info("Tus archivos se procesan únicamente durante esta sesión y no son almacenados por la aplicación.")
    with st.expander("Cómo se tratan tus datos"):
        st.write(
            "Los archivos se transmiten al servidor privado de la aplicación para procesarse. "
            "La aplicación no los persiste en disco ni base de datos. Los datos normalizados "
            "y resultados permanecen únicamente en memoria de sesión. El botón de limpieza "
            "elimina el estado mantenido por la aplicación para esta sesión."
        )
    st.button("Limpiar archivos y resultados", type="secondary", on_click=_limpiar_sesion_streamlit)

    st.header("Etapa 1 — Carga de archivos")
    col_ml, col_mp = st.columns(2)
    with col_ml:
        ml = st.file_uploader("Ventas de Mercado Libre", type=["csv"], help="Archivo de ventas, costos y rentabilidad", key="archivo_ml")
        info_ml = _inspeccionar_upload("ml", ml, TipoFuente.MERCADO_LIBRE)
    with col_mp:
        mp = st.file_uploader("Movimientos de Mercado Pago", type=["xlsx"], help="Reporte financiero de liquidaciones y movimientos", key="archivo_mp")
        info_mp = _inspeccionar_upload("mp", mp, TipoFuente.MERCADO_PAGO)

    st.header("Etapa 2 — Configuración")
    c1, c2 = st.columns(2)
    with c1:
        zona = st.text_input("Zona horaria operativa", value=st.session_state["zona_horaria"])
    with c2:
        tolerancia_txt = st.text_input("Tolerancia monetaria", value=st.session_state["tolerancia_texto"], help="Diferencia máxima aceptada para clasificar una operación como diferencia menor.")
    zona_valida, zona_error = _validar_zona(zona)
    tolerancia, tolerancia_error = _parsear_tolerancia(tolerancia_txt)
    zona_anterior = st.session_state.get("zona_horaria")
    tolerancia_anterior = st.session_state.get("tolerancia_canonica")
    tolerancia_actual = tolerancia_canonica(tolerancia) if tolerancia is not None else None
    if detectar_cambio(zona_anterior, zona) or detectar_cambio(tolerancia_anterior, tolerancia_actual):
        invalidar_resultados_conocidos(st.session_state)
    st.session_state["zona_horaria"] = zona
    st.session_state["tolerancia_texto"] = tolerancia_txt
    st.session_state["tolerancia_canonica"] = tolerancia_actual
    if zona_error:
        st.error(zona_error)
    if tolerancia_error:
        st.error(tolerancia_error)

    st.header("Etapa 3 — Procesamiento")
    listo = bool(info_ml and info_mp and info_ml["valido_fuente"] and info_mp["valido_fuente"] and zona_valida and tolerancia is not None)
    if st.button("Procesar y conciliar", disabled=not listo):
        try:
            _procesar(info_ml, info_mp, zona, tolerancia)
        except Exception:
            st.error("No se pudo completar el procesamiento. Revisá que los archivos correspondan a los formatos esperados.")

    firma_actual = _firma_actual(tolerancia, zona)
    if firma_actual is not None:
        st.session_state["firma_actual"] = firma_actual
    if "reporte" in st.session_state and st.session_state.get("firma_procesamiento") == firma_actual:
        _mostrar_resultados()
    elif "reporte" in st.session_state:
        invalidar_resultados_conocidos(st.session_state)


def _limpiar_sesion_streamlit() -> None:
    limpiar_claves_conocidas(st.session_state)


def _inicializar_estado() -> None:
    st.session_state.setdefault("zona_horaria", ZONA_DEFAULT)
    st.session_state.setdefault("tolerancia_texto", TOLERANCIA_DEFAULT)


def _inspeccionar_upload(clave: str, upload: Any, fuente_esperada: TipoFuente) -> dict[str, Any] | None:
    hash_key = f"hash_{clave}"
    if upload is None:
        if st.session_state.get(hash_key) is not None:
            st.session_state.pop(hash_key, None)
            invalidar_resultados_conocidos(st.session_state)
        return None
    contenido = upload.getvalue()
    inspeccion = inspeccionar_archivo(upload.name, contenido)
    hash_actual = inspeccion.metadatos.sha256
    if detectar_cambio(st.session_state.get(hash_key), hash_actual):
        st.session_state[hash_key] = hash_actual
        invalidar_resultados_conocidos(st.session_state)
    st.markdown(f"**Fuente detectada:** {inspeccion.fuente_detectada.value}")
    st.write(f"Filas: {inspeccion.metadatos.cantidad_filas} · Columnas: {len(inspeccion.metadatos.columnas_encontradas)}")
    st.write(f"Tamaño: {inspeccion.metadatos.tamaño_bytes} bytes · SHA-256: `{hash_actual[:12]}`")
    if inspeccion.metadatos.nombre_hoja:
        st.write(f"Hoja utilizada: {inspeccion.metadatos.nombre_hoja}")
    st.write(f"Válido: {'Sí' if inspeccion.es_valido else 'No'}")
    _mostrar_problemas("Errores estructurales", inspeccion.errores, st.error)
    _mostrar_problemas("Advertencias estructurales", inspeccion.advertencias, st.warning)
    valido_fuente = inspeccion.es_valido and inspeccion.fuente_detectada == fuente_esperada
    if inspeccion.es_valido and inspeccion.fuente_detectada != fuente_esperada:
        st.error("El archivo es válido, pero corresponde a otra fuente.")
    return {"nombre": upload.name, "contenido": contenido, "inspeccion": inspeccion, "valido_fuente": valido_fuente}


def _mostrar_problemas(titulo: str, problemas: tuple[Any, ...], render) -> None:
    if not problemas:
        return
    resumen: dict[str, int] = {}
    for p in problemas:
        resumen[p.codigo] = resumen.get(p.codigo, 0) + 1
    render(f"{titulo}: " + ", ".join(f"{k} ({v})" for k, v in resumen.items()))
    with st.expander(f"Ver detalle de {titulo.lower()}"):
        for p in problemas[:20]:
            fila = f"Fila {p.fila}: " if p.fila else ""
            st.write(f"{fila}{p.codigo} — {p.mensaje}")
        if len(problemas) > 20:
            st.write(f"… y {len(problemas) - 20} problemas más.")


def _validar_zona(zona: str) -> tuple[bool, str | None]:
    try:
        ZoneInfo(zona)
    except ZoneInfoNotFoundError:
        return False, "La zona horaria configurada no existe."
    return True, None


def _parsear_tolerancia(texto: str) -> tuple[Decimal | None, str | None]:
    try:
        valor = Decimal(texto.strip().replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None, "La tolerancia debe ser un número decimal válido."
    if valor < Decimal("0"):
        return None, "La tolerancia no puede ser negativa."
    return valor, None


def _firma_actual(tolerancia: Decimal | None, zona: str) -> str | None:
    hash_ml = st.session_state.get("hash_ml")
    hash_mp = st.session_state.get("hash_mp")
    if not hash_ml or not hash_mp or tolerancia is None:
        return None
    return construir_firma_procesamiento(hash_ml, hash_mp, zona, tolerancia)


def _procesar(info_ml: dict[str, Any], info_mp: dict[str, Any], zona: str, tolerancia: Decimal) -> None:
    with st.spinner("Normalizando y conciliando…"):
        ml = normalizar_mercado_libre(info_ml["nombre"], info_ml["contenido"], zona)
        mp = normalizar_mercado_pago(info_mp["nombre"], info_mp["contenido"], zona)
        st.session_state["normalizacion"] = {"Mercado Libre": ml, "Mercado Pago": mp}
        _mostrar_normalizacion("Mercado Libre", ml)
        _mostrar_normalizacion("Mercado Pago", mp)
        if not ml.operaciones:
            st.error("No quedaron operaciones comerciales válidas para conciliar.")
            return
        if not mp.movimientos:
            st.error("No quedaron movimientos financieros válidos para conciliar.")
            return
        firma = construir_firma_procesamiento(st.session_state["hash_ml"], st.session_state["hash_mp"], zona, tolerancia)
        st.session_state["cobertura"] = cobertura_archivos(ml.operaciones, mp.movimientos)
        st.session_state["reporte"] = reconciliar(ml.operaciones, mp.movimientos, tolerancia)
        st.session_state["firma_procesamiento"] = firma
        st.success("Conciliación finalizada.")


def _mostrar_normalizacion(nombre: str, resultado: Any) -> None:
    st.write(f"**{nombre}:** recibidas {resultado.cantidad_total_recibida}, normalizadas {resultado.cantidad_normalizada}, rechazadas {resultado.cantidad_rechazada}.")
    _mostrar_problemas(f"Advertencias de normalización {nombre}", resultado.advertencias, st.warning)
    if resultado.cantidad_rechazada:
        st.warning(f"Procesamiento parcial en {nombre}: {resultado.cantidad_rechazada} filas excluidas de la conciliación.")
        with st.expander(f"Filas rechazadas de {nombre}"):
            for rechazada in resultado.filas_rechazadas[:20]:
                mensajes = "; ".join(e.mensaje for e in rechazada.errores)
                st.write(f"Fila {rechazada.numero_fila_origen}: {mensajes}")



def _mostrar_cobertura(cobertura: Any) -> None:
    st.header("Cobertura de los archivos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas ML", cobertura.periodo_ventas_ml.texto)
    c2.metric("Origen movimientos MP", cobertura.periodo_origen_mp.texto)
    c3.metric("Liquidaciones MP", cobertura.periodo_liquidacion_mp.texto)
    c4.metric("Sin fecha de liquidación", cobertura.movimientos_sin_fecha_liquidacion)
    st.caption("La cobertura se calcula con fechas locales normalizadas. Ventas ML usa fecha de venta; MP usa fecha de origen y fecha de liquidación cuando existe.")
    if cobertura.advertencia_origenes:
        st.info(cobertura.advertencia_origenes)

def _mostrar_resultados() -> None:
    reporte = st.session_state["reporte"]
    if "cobertura" in st.session_state:
        _mostrar_cobertura(st.session_state["cobertura"])

    st.header("Resumen ejecutivo")
    st.caption("Las métricas comparables usan solo resultados con diferencia_control calculada. Los grupos financieros sin operación comercial se informan separados; devoluciones y reclamos pueden integrar ese grupo por ausencia comercial aunque su estado prioritario sea Devuelta o En reclamo. Los movimientos de fondos se mantienen separados y no se tratan como pérdidas comerciales.")
    conclusion, severidad = conclusion_ejecutiva(reporte)
    if severidad == "ok":
        st.success(conclusion)
    else:
        st.warning(conclusion)
    kpis = resumen_kpis(reporte)
    for bloque in (list(kpis.items())[:5], list(kpis.items())[5:10], list(kpis.items())[10:]):
        cols = st.columns(len(bloque))
        for col, (nombre, valor) in zip(cols, bloque, strict=False):
            col.metric(nombre, valor)

    st.header("Resultados por operación")
    vista = st.radio("Vista", options=["Excepciones y casos especiales", "Todas las operaciones"], horizontal=True, key="vista_resultados")
    resultados_visibles_por_vista = filtrar_resultados_por_vista(reporte.resultados, vista)
    filas = filas_presentacion(resultados_visibles_por_vista)
    estados = sorted({f.estado_codigo: f.estado for f in filas}.items(), key=lambda x: x[1])
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    seleccion = c1.multiselect("Estados", options=[c for c, _ in estados], format_func=dict(estados).get, key="filtro_estados")
    busqueda = c2.text_input("Buscar ID de orden", key="filtro_busqueda_orden")
    solo_revision = c3.checkbox("Solo requieren revisión", key="filtro_solo_revision")
    solo_divididos = c4.checkbox("Solo pagos divididos", key="filtro_solo_divididos")
    visibles = filtrar_filas(filas, set(seleccion), busqueda, solo_revision, solo_divididos)
    st.caption(f"Mostrando {len(visibles)} de {len(filas)} resultados de la vista seleccionada.")
    st.dataframe(tabla_principal(visibles), use_container_width=True, hide_index=True)

    if visibles:
        claves = [f.clave for f in visibles]
        elegida = st.selectbox("Seleccionar operación para ver detalle", claves, key="detalle_operacion")
        mapa = {(r.id_orden or clave_resultado(r)): r for r in reporte.resultados}
        st.subheader("Detalle de operación")
        st.markdown("#### Información de la operación")
        st.table([{"Campo": k, "Valor": v} for k, v in detalle_cliente(mapa[elegida]).items()])
        with st.expander("Trazabilidad técnica"):
            st.table([{"Campo": k, "Valor": v} for k, v in detalle_tecnico_seguro(mapa[elegida]).items()])

if __name__ == "__main__":
    main()
