"""Interfaz Streamlit para conciliación Mercado Libre / Mercado Pago."""

from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from kiki_control.adapters.mercado_libre import normalizar_mercado_libre
from kiki_control.adapters.mercado_libre_ventas import normalizar_ventas_mercado_libre
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago
from kiki_control.domain.enums import TipoFuente
from kiki_control.domain.control_consolidado import ErrorControlConsolidado
from kiki_control.exporting import generar_excepciones_consolidadas_excel, generar_reporte_completo_excel, generar_reporte_consolidado_excel, generar_reporte_excepciones_excel, generar_revisiones_consolidadas_excel, generar_revisiones_pendientes_excel
from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.presentation.explanations import (
    COLUMNAS_TABLA,
    METRICAS_COBERTURA,
    METRICAS_RESUMEN,
    explicar_operacion,
    guia_general,
)
from kiki_control.presentation.review_cases import (
    DEFINICIONES_REVISION,
    clasificar_revisiones,
    conteo_por_tipo,
    filas_revisiones,
    filtrar_casos,
    clave_caso_revision,
    referencia_visible_caso,
)
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
from kiki_control.linking.commercial import vincular_ventas_oficiales_con_eccomapp
from kiki_control.linking.control_financiero import consolidar_control_financiero
from kiki_control.presentation.control_consolidado_view import (
    advertir_periodos_distintos,
    conclusion_ejecutiva_consolidada,
    cobertura_tres_fuentes,
    detalle_control,
    explicacion_resultado,
    filas_tabla_consolidada,
    filtrar_filas_consolidadas,
    etiqueta_selector_detalle,
    formato_importe,
    kpis_consolidados,
    tabla_consolidada,
    trazabilidad_tecnica,
)
from kiki_control.presentation.control_consolidado_diagnostics import diagnosticar_control_consolidado
from kiki_control.reconciliation import reconciliar
from kiki_control.ui.session_cycle import (
    construir_firma_procesamiento,
    construir_firma_procesamiento_tres_fuentes,
    detectar_cambio,
    invalidar_resultados_conocidos,
    limpiar_claves_conocidas,
    limpiar_detalle_revision,
    limpiar_detalle_revision_si_obsoleto,
    limpiar_filtros_de_vista,
    tolerancia_canonica,
)

ZONA_DEFAULT = "America/Argentina/Cordoba"
TOLERANCIA_DEFAULT = "0,01"


def main() -> None:
    st.set_page_config(page_title="Kiki Control Financiero", layout="wide")
    _inicializar_estado()
    st.title("Kiki Control Financiero")
    st.subheader("Control financiero consolidado ML oficial / Eccomapp / Mercado Pago")
    st.info("Tus tres archivos se procesan únicamente durante esta sesión y no son almacenados por la aplicación.")
    with st.expander("Cómo se tratan tus datos"):
        st.write(
            "Los reportes de ventas oficiales de Mercado Libre, costos de Eccomapp y movimientos de Mercado Pago "
            "se procesan en memoria. La aplicación no persiste bytes originales ni muestra comprador, documentos, "
            "domicilio, tarjeta, datos personales ni contenido crudo."
        )
    st.button("Limpiar archivos y resultados", type="secondary", on_click=_limpiar_sesion_streamlit)

    st.header("Etapa 1 — Carga de archivos")
    col_ml_oficial, col_eccomapp, col_mp = st.columns(3)
    with col_ml_oficial:
        ml_oficial = st.file_uploader("Ventas oficiales de Mercado Libre", type=["xlsx"], help="Reporte oficial que aporta ventas, cargos, envíos y Total (ARS).", key="archivo_ml_oficial")
        info_ml_oficial = _inspeccionar_upload("ml_oficial", ml_oficial, TipoFuente.MERCADO_LIBRE_VENTAS)
    with col_eccomapp:
        eccomapp_file = st.file_uploader("Costos y rentabilidad de Eccomapp", type=["csv"], help="Reporte que aporta costo de productos y valores de rentabilidad informados.", key="archivo_eccomapp")
        info_eccomapp = _inspeccionar_upload("eccomapp", eccomapp_file, TipoFuente.ECCOMAPP_RENTABILIDAD)
    with col_mp:
        mp = st.file_uploader("Movimientos de Mercado Pago", type=["xlsx"], help="Reporte financiero de pagos, liquidaciones, devoluciones y reclamos.", key="archivo_mp")
        info_mp = _inspeccionar_upload("mp", mp, TipoFuente.MERCADO_PAGO)

    st.header("Etapa 2 — Configuración")
    c1, c2 = st.columns(2)
    with c1:
        zona = st.text_input("Zona horaria operativa", value=st.session_state["zona_horaria"])
    with c2:
        tolerancia_txt = st.text_input("Tolerancia monetaria", value=st.session_state["tolerancia_texto"], help="Diferencia máxima aceptada para clasificar controles financieros.")
    zona_valida, zona_error = _validar_zona(zona)
    tolerancia, tolerancia_error = _parsear_tolerancia(tolerancia_txt)
    tolerancia_actual = tolerancia_canonica(tolerancia) if tolerancia is not None else None
    if detectar_cambio(st.session_state.get("zona_horaria"), zona) or detectar_cambio(st.session_state.get("tolerancia_canonica"), tolerancia_actual):
        invalidar_resultados_conocidos(st.session_state)
    st.session_state["zona_horaria"] = zona
    st.session_state["tolerancia_texto"] = tolerancia_txt
    st.session_state["tolerancia_canonica"] = tolerancia_actual
    if zona_error: st.error(zona_error)
    if tolerancia_error: st.error(tolerancia_error)

    st.header("Etapa 3 — Procesamiento")
    listo = bool(info_ml_oficial and info_eccomapp and info_mp and info_ml_oficial["valido_fuente"] and info_eccomapp["valido_fuente"] and info_mp["valido_fuente"] and zona_valida and tolerancia is not None)
    if st.button("Procesar y consolidar", disabled=not listo):
        try:
            _procesar(info_ml_oficial, info_eccomapp, info_mp, zona, tolerancia)
        except ErrorControlConsolidado as exc:
            st.error(str(exc))
        except Exception:
            st.error("No se pudo completar el procesamiento. Revisá que los archivos correspondan a los formatos esperados.")

    firma_actual = _firma_actual(tolerancia, zona)
    if firma_actual is not None:
        st.session_state["firma_actual"] = firma_actual
    if "reporte_consolidado" in st.session_state and st.session_state.get("firma_procesamiento") == firma_actual:
        _mostrar_resultados()
    elif "reporte_consolidado" in st.session_state:
        invalidar_resultados_conocidos(st.session_state)

def _limpiar_sesion_streamlit() -> None:
    limpiar_claves_conocidas(st.session_state)


def _limpiar_filtros_por_cambio_de_vista() -> None:
    limpiar_filtros_de_vista(st.session_state)


def _limpiar_detalle_revision_por_cambio_de_filtro() -> None:
    limpiar_detalle_revision(st.session_state)


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
    resumenes = []
    for codigo, cantidad in resumen.items():
        problemas_codigo = tuple(p for p in problemas if p.codigo == codigo)
        detalles = tuple(p.detalle for p in problemas_codigo if getattr(p, "detalle", None))
        detalle = f" {detalles[0]}." if len(set(detalles)) == 1 else ""
        if codigo == "COSTO_ENVIO_VACIO_INTERPRETADO_CERO" and problemas_codigo:
            resumenes.append(f"Costo de envío vacío interpretado como $0 según regla confirmada.{detalle}")
        else:
            resumenes.append(f"{codigo} ({cantidad})" + (f" — {detalles[0]}" if len(set(detalles)) == 1 else ""))
    render(f"{titulo}: " + ", ".join(resumenes))
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
    h1 = st.session_state.get("hash_ml_oficial")
    h2 = st.session_state.get("hash_eccomapp")
    h3 = st.session_state.get("hash_mp")
    if not h1 or not h2 or not h3 or tolerancia is None:
        return None
    return construir_firma_procesamiento_tres_fuentes(h1, h2, h3, zona, tolerancia)


def _procesar(info_ml_oficial: dict[str, Any], info_eccomapp: dict[str, Any], info_mp: dict[str, Any], zona: str, tolerancia: Decimal) -> None:
    with st.spinner("Normalizando, vinculando, conciliando y consolidando…"):
        ventas_ml = normalizar_ventas_mercado_libre(info_ml_oficial["nombre"], info_ml_oficial["contenido"], zona_horaria=zona)
        eccomapp = normalizar_mercado_libre(info_eccomapp["nombre"], info_eccomapp["contenido"], zona)
        mercado_pago = normalizar_mercado_pago(info_mp["nombre"], info_mp["contenido"], zona)
        st.session_state["normalizacion"] = {"Ventas oficiales ML": ventas_ml, "Eccomapp": eccomapp, "Mercado Pago": mercado_pago}
        _mostrar_normalizacion("Ventas oficiales ML", ventas_ml)
        _mostrar_normalizacion("Eccomapp", eccomapp)
        _mostrar_normalizacion("Mercado Pago", mercado_pago)
        if not ventas_ml.ventas:
            st.error("No quedaron ventas oficiales de Mercado Libre válidas; no se puede consolidar.")
            return
        if not eccomapp.operaciones:
            st.error("No quedaron operaciones/costos de Eccomapp válidos; no se puede consolidar.")
            return
        if not mercado_pago.movimientos:
            st.error("No quedaron movimientos de Mercado Pago válidos; no se puede consolidar.")
            return
        reporte_comercial = vincular_ventas_oficiales_con_eccomapp(ventas_ml.ventas, eccomapp.operaciones)
        reporte_financiero = reconciliar(eccomapp.operaciones, mercado_pago.movimientos, tolerancia)
        reporte_consolidado = consolidar_control_financiero(reporte_comercial, reporte_financiero)
        firma = construir_firma_procesamiento_tres_fuentes(st.session_state["hash_ml_oficial"], st.session_state["hash_eccomapp"], st.session_state["hash_mp"], zona, tolerancia)
        st.session_state["reporte_comercial"] = reporte_comercial
        st.session_state["reporte_financiero"] = reporte_financiero
        st.session_state["reporte"] = reporte_financiero
        st.session_state["reporte_consolidado"] = reporte_consolidado
        st.session_state["cobertura_consolidada"] = cobertura_tres_fuentes(ventas_ml.ventas, eccomapp.operaciones, mercado_pago.movimientos)
        st.session_state["cobertura"] = cobertura_archivos(eccomapp.operaciones, mercado_pago.movimientos)
        st.session_state["firma_procesamiento"] = firma
        st.success("Control consolidado finalizado.")

def _mostrar_normalizacion(nombre: str, resultado: Any) -> None:
    st.write(f"**{nombre}:** recibidas {resultado.cantidad_total_recibida}, normalizadas {resultado.cantidad_normalizada}, rechazadas {resultado.cantidad_rechazada}.")
    _mostrar_problemas(f"Advertencias de normalización {nombre}", resultado.advertencias, st.warning)
    if resultado.cantidad_rechazada:
        st.warning(f"Procesamiento parcial en {nombre}: {resultado.cantidad_rechazada} filas excluidas de la conciliación.")
        with st.expander(f"Filas rechazadas de {nombre}"):
            for rechazada in resultado.filas_rechazadas[:20]:
                mensajes = "; ".join(e.mensaje for e in rechazada.errores)
                st.write(f"Fila {rechazada.numero_fila_origen}: {mensajes}")




def _mostrar_guia_general() -> None:
    with st.expander("Cómo se calculan los resultados"):
        for titulo, contenido in guia_general().items():
            st.markdown(f"#### {titulo}")
            if titulo == "Significado de los estados":
                st.table([
                    {
                        "Estado": e.nombre,
                        "Qué significa": e.significado,
                        "Cómo se detecta": e.deteccion,
                        "Qué debería hacer la usuaria": e.accion_usuaria,
                    }
                    for e in contenido
                ])
            else:
                st.write(contenido)


def _column_config_tabla() -> dict[str, Any]:
    return {nombre: st.column_config.TextColumn(nombre, help=definicion.ayuda) for nombre, definicion in COLUMNAS_TABLA.items()}

def _mostrar_cobertura(cobertura: Any) -> None:
    st.header("Cobertura de los archivos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas ML", cobertura.periodo_ventas_ml.texto, help=METRICAS_COBERTURA["Ventas ML"].ayuda)
    c2.metric("Origen movimientos MP", cobertura.periodo_origen_mp.texto, help=METRICAS_COBERTURA["Origen movimientos MP"].ayuda)
    c3.metric("Liquidaciones MP", cobertura.periodo_liquidacion_mp.texto, help=METRICAS_COBERTURA["Liquidaciones MP"].ayuda)
    c4.metric("Sin fecha de liquidación", cobertura.movimientos_sin_fecha_liquidacion, help=METRICAS_COBERTURA["Sin fecha de liquidación"].ayuda)
    st.caption("La cobertura se calcula con fechas locales normalizadas. Ventas ML usa fecha de venta; MP usa fecha de origen y fecha de liquidación cuando existe.")
    if cobertura.advertencia_origenes:
        st.info(cobertura.advertencia_origenes + " La aplicación no recorta automáticamente el XLSX.")


def _nombre_exportacion(prefijo: str, reporte: Any | None = None) -> str:
    reporte_fecha = reporte if reporte is not None and hasattr(reporte, "fecha_procesamiento_utc") else st.session_state["reporte"]
    fecha = reporte_fecha.fecha_procesamiento_utc.strftime("%Y%m%d_%H%M%S")
    return f"{prefijo}_{fecha}.xlsx"


def _mostrar_descargas() -> None:
    reporte = st.session_state["reporte"]
    cobertura = st.session_state.get("cobertura")
    zona = st.session_state["zona_horaria"]
    st.header("Descargas")
    c1, c2, c3 = st.columns(3)
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    c1.download_button(
        "Descargar reporte completo",
        data=generar_reporte_completo_excel(reporte, cobertura, zona),
        file_name=_nombre_exportacion("kiki_control_reporte_completo"),
        mime=mime,
    )
    c2.download_button(
        "Descargar solo excepciones",
        data=generar_reporte_excepciones_excel(reporte, cobertura, zona),
        file_name=_nombre_exportacion("kiki_control_excepciones"),
        mime=mime,
    )
    c3.download_button(
        "Descargar revisiones pendientes",
        data=generar_revisiones_pendientes_excel(reporte, cobertura, zona),
        file_name=_nombre_exportacion("kiki_control_revisiones_pendientes"),
        mime=mime,
    )
    st.caption("Los archivos descargados se guardan en tu dispositivo. La aplicación no conserva una copia.")


def _mostrar_revisiones_pendientes(reporte: Any) -> None:
    casos = clasificar_revisiones(reporte.resultados)
    total = len(casos)
    st.header("Revisiones pendientes")
    st.metric("Total de resultados que requieren revisión", total)
    st.caption("Se cuentan resultados o grupos de conciliación, no filas crudas. La suma por tipo coincide con el KPI Requieren revisión.")
    conteos = conteo_por_tipo(casos)
    if conteos:
        st.table([{"Tipo de revisión": DEFINICIONES_REVISION[t].nombre_visible, "Cantidad": c} for t, c in conteos.items()])
    with st.expander("Ver las revisiones pendientes y qué hacer"):
        tipos = list(conteos)
        c1, c2 = st.columns([2, 2])
        tipo = c1.selectbox("Tipo de revisión", options=[None, *tipos], format_func=lambda t: "Todos" if t is None else DEFINICIONES_REVISION[t].nombre_visible, key="revision_tipo", on_change=_limpiar_detalle_revision_por_cambio_de_filtro)
        busqueda = c2.text_input("Buscar por ID de orden o referencia", key="revision_busqueda", on_change=_limpiar_detalle_revision_por_cambio_de_filtro)
        visibles = filtrar_casos(casos, tipo, busqueda)
        filas = filas_revisiones(visibles)
        st.dataframe([
            {
                "ID de orden o referencia": f.id_orden_o_referencia,
                "Tipo de revisión": f.tipo_revision,
                "Estado": f.estado,
                "Por qué requiere revisión": f.motivo_explicado,
                "Acción recomendada": f.accion_recomendada,
                "Neto informado ML": f.neto_informado_ml,
                "Neto aprobado MP": f.neto_aprobado_mp,
                "Neto financiero total": f.neto_financiero_total,
                "Filas ML": f.filas_ml,
                "Filas MP": f.filas_mp,
            } for f in filas
        ], use_container_width=True, hide_index=True, column_config={
            "Por qué requiere revisión": st.column_config.TextColumn("Por qué requiere revisión", help="Explicación de presentación basada en estados, motivos e indicadores existentes."),
            "Acción recomendada": st.column_config.TextColumn("Acción recomendada", help="Siguiente verificación sugerida sin afirmar errores contables ni pérdidas."),
            "Filas ML": st.column_config.TextColumn("Filas ML", help="Filas comerciales de origen usadas para trazabilidad."),
            "Filas MP": st.column_config.TextColumn("Filas MP", help="Filas financieras de origen usadas para trazabilidad."),
        })
        if visibles:
            opciones = [clave_caso_revision(c) for c in visibles]
            casos_por_clave = {clave_caso_revision(c): c for c in visibles}
            limpiar_detalle_revision_si_obsoleto(st.session_state, set(opciones))
            elegida = st.selectbox("Seleccionar caso", opciones, key="revision_detalle", format_func=lambda clave: referencia_visible_caso(casos_por_clave[clave]))
            caso = casos_por_clave[elegida]
            st.subheader("Detalle de la revisión")
            st.write(f"**Qué se detectó:** {caso.nombre_visible}.")
            st.write(f"**Por qué no pudo resolverse automáticamente:** {caso.descripcion} La aplicación no puede resolverlo automáticamente con los datos disponibles.")
            st.write(f"**Qué debe revisar la clienta:** {caso.accion_recomendada}")
            st.write(f"**Archivos y columnas involucradas:** {', '.join(caso.columnas_utilizadas)}")
            st.write(f"**Filas de origen:** ML {', '.join(map(str, caso.filas_ml)) or '—'} · MP {', '.join(map(str, caso.filas_mp)) or '—'}")
            st.caption("Este detalle se vincula con el detalle de operación existente y no duplica cálculos financieros.")


def _column_config_control_consolidado() -> dict[str, Any]:
    return {
        "Grupo u orden": st.column_config.TextColumn("Grupo u orden", help="Identificador operativo del grupo u orden. No incluye datos del comprador ni contenido crudo."),
        "Estado": st.column_config.TextColumn("Estado", help="Estado consolidado definido por el motor de dominio para este grupo."),
        "Fuentes disponibles": st.column_config.TextColumn("Fuentes disponibles", help="Indica si el grupo tiene datos de ML oficial, Eccomapp y/o Mercado Pago."),
        "Venta ML oficial": st.column_config.TextColumn("Venta ML oficial", help="Importe de venta informado por el archivo oficial de Mercado Libre. Columna: Ingresos por productos (ARS). Universo: grupos con venta oficial."),
        "Cargos e impuestos ML": st.column_config.TextColumn("Cargos e impuestos ML", help="Cargos e impuestos informados por el archivo oficial de Mercado Libre. Columna: Cargo por venta e impuestos (ARS). Universo: grupos con venta oficial."),
        "Costo envío ML": st.column_config.TextColumn("Costo envío ML", help="Costo de envío informado por el archivo oficial de Mercado Libre. Columna: Costos de envío (ARS). Universo: grupos con venta oficial."),
        "Neto esperado ML": st.column_config.TextColumn("Neto esperado ML", help="Total informado directamente por Mercado Libre oficial. Columna: Total (ARS). No se reconstruye en Streamlit. Universo: grupos con venta oficial."),
        "Costo productos": st.column_config.TextColumn("Costo productos", help="Costo de productos informado por Eccomapp. Columna: Costo Total (Con IVA) ($). Universo: grupos con Eccomapp."),
        "Neto aprobado MP": st.column_config.TextColumn("Neto aprobado MP", help="Neto aprobado proveniente de Mercado Pago. Columna: MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO. Agrupado por el motor. Universo: grupos con movimientos MP aprobados."),
        "Neto financiero total MP": st.column_config.TextColumn("Neto financiero total MP", help="Total financiero agrupado por el motor desde Mercado Pago. Columna principal: MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO. Universo: grupos con movimientos MP."),
        "Diferencia ML–MP": st.column_config.TextColumn("Diferencia ML–MP", help="Diferencia calculada por el dominio entre neto aprobado MP y Total (ARS) de ML oficial. Universo: grupos con ambos datos."),
        "Utilidad preliminar": st.column_config.TextColumn("Utilidad preliminar", help="Utilidad preliminar de control calculada por el dominio desde Total (ARS) ML oficial y Costo Total (Con IVA) ($) Eccomapp. No es resultado contable o fiscal definitivo."),
        "Requiere revisión": st.column_config.TextColumn("Requiere revisión", help="Indicador prudente definido por el dominio cuando hay diferencias, fuentes faltantes o ambigüedad."),
        "Motivo principal": st.column_config.TextColumn("Motivo principal", help="Motivo visible de revisión; los motivos internos quedan en trazabilidad técnica."),
        "Qué revisar": st.column_config.TextColumn("Qué revisar", help="Acción recomendada para interpretar el caso sin asumir causas contables no evidenciadas."),
    }


def _periodo_ventas_ml_normalizadas() -> tuple[Any, Any]:
    normalizacion = st.session_state.get("normalizacion", {})
    ventas = tuple(getattr(normalizacion.get("Ventas oficiales ML"), "ventas", ()))
    fechas = [v.fecha_venta for v in ventas if getattr(v, "fecha_venta", None) is not None]
    if not fechas:
        return None, None
    return min(fechas), max(fechas)


def _fechas_mp_por_fila_normalizadas() -> dict[int, Any]:
    normalizacion = st.session_state.get("normalizacion", {})
    movimientos = tuple(getattr(normalizacion.get("Mercado Pago"), "movimientos", ()))
    return {m.numero_fila_origen: m.fecha_origen_local for m in movimientos if getattr(m, "numero_fila_origen", None) is not None}


def _fila_temporal(nombre: str, item: Any) -> dict[str, Any]:
    return {
        "Categoría temporal": nombre,
        "Cantidad": item.cantidad,
        "Neto aprobado MP": formato_importe(item.neto_aprobado_mp),
        "Neto financiero total MP": formato_importe(item.neto_financiero_total_mp),
    }

def _mostrar_resultados() -> None:
    reporte = st.session_state["reporte_consolidado"]
    with st.expander("Cómo se calcula el control consolidado", expanded=True):
        st.write(
            "El XLSX oficial de Mercado Libre aporta venta, cargos, envíos y Total (ARS) informado por la fuente. "
            "El CSV de Eccomapp aporta costos de productos y rentabilidad informada. Mercado Pago aporta movimientos, "
            "netos aprobados, liquidaciones, devoluciones y reclamos. ML oficial y Eccomapp se vinculan con la API de dominio "
            "por IDs de carrito/orden; Mercado Pago se vincula por ID DE LA ORDEN mediante la conciliación existente. "
            "Diferencia ML–MP = Neto aprobado MP menos Total (ARS) ML oficial. Utilidad preliminar de control = Total (ARS) "
            "ML oficial menos Costo Total (Con IVA) Eccomapp. Un importe queda vacío cuando falta la fuente o campo necesario. "
            "El control es operativo y no es resultado contable o fiscal definitivo."
        )
    if "cobertura_consolidada" in st.session_state:
        st.header("Cobertura de los archivos")
        cobertura = st.session_state["cobertura_consolidada"]
        cols = st.columns(len(cobertura))
        for col, item in zip(cols, cobertura, strict=False):
            col.metric(item.nombre, f"{item.minimo} a {item.maximo}", help="Fechas normalizadas informadas por la fuente; no se recortan archivos automáticamente.")
            if item.extra: col.caption(item.extra)
        st.caption("Las liquidaciones de Mercado Pago pueden extenderse fuera del período de venta; se muestran como cobertura financiera y no disparan por sí solas la advertencia de períodos de origen.")
        if advertir_periodos_distintos(cobertura):
            st.warning("Los períodos de origen de ML oficial, Eccomapp y Mercado Pago no coinciden. Esto requiere revisión, pero no implica por sí mismo un error.")

    st.header("Resumen ejecutivo consolidado")
    inicio_ml, fin_ml = _periodo_ventas_ml_normalizadas()
    diagnostico = diagnosticar_control_consolidado(reporte, inicio_ml, fin_ml, _fechas_mp_por_fila_normalizadas())
    st.info(conclusion_ejecutiva_consolidada(reporte, diagnostico))
    if not diagnostico.particion.cierra_exactamente or not diagnostico.diferencias.identidad_cierra_exactamente:
        st.error("Error de consistencia en diagnósticos: no se presentan KPIs como confiables hasta revisar la partición o la identidad de diferencias.")
    st.subheader("Cobertura monetaria entre fuentes")
    st.warning("No se comparan importes de universos distintos: cada fila muestra su universo y el motivo de exclusión antes de interpretar diferencias.")
    st.table([{
        "Fuente": c.fuente, "Universo": c.universo, "Cantidad total": c.cantidad_total, "Importe total del archivo": formato_importe(c.importe_total),
        "Cantidad usada": c.cantidad_usada, "Importe usado": formato_importe(c.importe_usado), "Cantidad excluida": c.cantidad_excluida,
        "Importe excluido": formato_importe(c.importe_excluido), "Motivo de exclusión": c.motivo_exclusion,
    } for c in diagnostico.cobertura_monetaria])
    st.subheader("Utilidad preliminar auditable")
    st.table([{
        "Neto ML del universo calculable": formato_importe(diagnostico.utilidad.neto_ml_universo_utilidad),
        "Costo Eccomapp del universo calculable": formato_importe(diagnostico.utilidad.costo_productos_universo_utilidad),
        "Utilidad preliminar": formato_importe(diagnostico.utilidad.utilidad_preliminar),
        "Costo Eccomapp fuera del universo calculable": formato_importe(diagnostico.utilidad.costo_eccomapp_fuera_universo_calculable),
        "Grupos excluidos": diagnostico.utilidad.grupos_excluidos,
        "Motivos": "; ".join(f"{k}: {v}" for k, v in diagnostico.utilidad.motivos_exclusion.items() if v),
        "Identidad": "utilidad_preliminar = neto_ml_universo_calculable - costo_eccomapp_universo_calculable",
        "Cierra": "Sí" if diagnostico.utilidad.identidad_cierra_exactamente else "No",
    }])
    st.subheader("Residual oficial de Mercado Libre")
    st.table([{
        "Nombre visible": diagnostico.residual_ml.nombre_visible, "Fórmula": diagnostico.residual_ml.formula,
        "Importe": formato_importe(diagnostico.residual_ml.importe), "Universo": diagnostico.residual_ml.universo,
        "Columnas utilizadas": ", ".join(diagnostico.residual_ml.columnas_utilizadas),
        "Universo ML oficial": diagnostico.residual_ml.grupos_universo_ml_oficial,
        "Grupos calculables": diagnostico.residual_ml.grupos_calculables,
        "Grupos excluidos": diagnostico.residual_ml.grupos_excluidos,
        "Suma Total (ARS)": formato_importe(diagnostico.residual_ml.suma_total_ars),
        "Suma Ingresos por productos (ARS)": formato_importe(diagnostico.residual_ml.suma_ingresos_productos),
        "Suma Cargo por venta e impuestos (ARS)": formato_importe(diagnostico.residual_ml.suma_cargo_venta_impuestos),
        "Suma Costos de envío (ARS)": formato_importe(diagnostico.residual_ml.suma_costos_envio),
        "Motivos de exclusión": "; ".join(f"{k}: {v}" for k, v in diagnostico.residual_ml.motivos_exclusion.items() if v),
        "Identidad": "suma Total (ARS) = suma Ingresos por productos + suma Cargos e impuestos + suma Costos de envío + residual",
        "Cierra": "Sí" if diagnostico.residual_ml.identidad_cierra_exactamente else "No",
    }])
    st.subheader("Puente de importes entre fuentes")
    st.caption("Universo triple: grupos con Neto ML, Neto Eccomapp y Neto aprobado MP. No oculta excluidos ni atribuye causas sin evidencia.")
    st.table([{
        "Universo triple": diagnostico.puente.universo_neto_esperado,
        "Neto ML": formato_importe(diagnostico.puente.neto_oficial_ml),
        "Neto Eccomapp": formato_importe(diagnostico.puente.neto_informado_eccomapp),
        "Neto aprobado MP": formato_importe(diagnostico.puente.neto_aprobado_mp),
        "Eccomapp − ML": formato_importe(diagnostico.puente.eccomapp_menos_ml),
        "MP − Eccomapp": formato_importe(diagnostico.puente.mp_menos_eccomapp),
        "MP − ML": formato_importe(diagnostico.puente.mp_menos_ml),
        "Identidad cierra": "Sí" if diagnostico.puente.identidad_cierra_exactamente else "No",
    }])
    if diagnostico.puente.grupos_excluidos_universo_triple:
        st.caption("Grupos excluidos del puente triple y aporte a la diferencia general ML–MP cuando ambos importes existen.")
        st.table([{
            "Grupo": g.grupo, "Motivo": g.motivo, "Neto ML": formato_importe(g.neto_ml), "Neto Eccomapp": formato_importe(g.neto_eccomapp),
            "Neto aprobado MP": formato_importe(g.neto_aprobado_mp), "Aporte MP − ML": formato_importe(g.aporte_diferencia_ml_mp),
        } for g in diagnostico.puente.grupos_excluidos_universo_triple])
    if not (diagnostico.particion.cierra_exactamente and diagnostico.diferencias.identidad_cierra_exactamente and diagnostico.puente.identidad_cierra_exactamente and diagnostico.utilidad.motivos_cierran_exactamente and diagnostico.utilidad.identidad_cierra_exactamente and diagnostico.temporal_mp_sin_venta.particion_cierra_exactamente and diagnostico.residual_ml.identidad_cierra_exactamente):
        st.error("Error de consistencia: al menos una identidad de diagnóstico no cierra exactamente. Revisar partición, diferencias, puente, utilidad o temporalidad antes de confiar en el bloque afectado.")
    st.subheader("Movimientos MP sin venta oficial: distribución temporal")
    st.caption(diagnostico.temporal_mp_sin_venta.aclaracion)
    st.caption("El neto aprobado representa pagos aprobados comparables con ventas. El neto financiero total incorpora además devoluciones, reclamos, disputas y otros impactos; por eso ambos totales no tienen que coincidir.")
    st.table([
        _fila_temporal("Anteriores al período ML", diagnostico.temporal_mp_sin_venta.anteriores),
        _fila_temporal("Dentro del período ML", diagnostico.temporal_mp_sin_venta.dentro),
        _fila_temporal("Posteriores al período ML", diagnostico.temporal_mp_sin_venta.posteriores),
        _fila_temporal("Sin fecha", diagnostico.temporal_mp_sin_venta.sin_fecha),
        _fila_temporal("Fechas mixtas", diagnostico.temporal_mp_sin_venta.fechas_mixtas),
    ])
    st.subheader("Revisiones del control consolidado")
    st.caption(diagnostico.revisiones.aclaracion)
    st.table([{"Motivo visible": r.motivo_visible, "Cantidad": r.cantidad, "Importe afectado": formato_importe(r.importe_afectado), "Acción recomendada": r.accion_recomendada, "Grupos involucrados": ", ".join(r.grupos_involucrados[:20])} for r in diagnostico.revisiones.revisiones_multietiqueta])
    for titulo, kpis in kpis_consolidados(reporte).items():
        st.subheader(titulo)
        cols = st.columns(len(kpis))
        for col, kpi in zip(cols, kpis, strict=False):
            col.metric(kpi.nombre, kpi.valor, help=kpi.ayuda)

    st.header("Control consolidado por operación")
    vista = st.radio("Vista", options=["Pendientes, diferencias y datos faltantes", "Todas las operaciones"], horizontal=True, key="vista_resultados", on_change=_limpiar_filtros_por_cambio_de_vista)
    resultados = reporte.resultados if vista == "Todas las operaciones" else tuple(r for r in reporte.resultados if r.requiere_revision or r.diferencia_ml_mp not in (None, Decimal("0")) or not (r.tiene_mercado_libre_oficial and r.tiene_eccomapp and r.tiene_mercado_pago))
    filas = filas_tabla_consolidada(resultados)
    estados = sorted({f.estado_codigo: f.estado for f in filas}.items(), key=lambda x: x[1])
    c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
    seleccion = c1.multiselect("Estado consolidado", options=[c for c, _ in estados], format_func=dict(estados).get, key="filtro_estados")
    busqueda = c2.text_input("Buscar grupo u orden", key="filtro_busqueda_orden")
    solo_revision = c3.checkbox("Solo requieren revisión", key="filtro_solo_revision")
    solo_diferencia = c4.checkbox("Solo con diferencia", key="filtro_solo_diferencia")
    solo_faltantes = c5.checkbox("Solo con datos faltantes", key="filtro_solo_faltantes")
    visibles = filtrar_filas_consolidadas(filas, set(seleccion), busqueda, solo_revision, solo_diferencia, solo_faltantes)
    columnas = ["Grupo u orden", "Estado", "Fuentes disponibles", "Venta ML oficial", "Cargos e impuestos ML", "Costo envío ML", "Neto esperado ML", "Costo productos", "Neto aprobado MP", "Neto financiero total MP", "Diferencia ML–MP", "Utilidad preliminar", "Requiere revisión", "Motivo principal", "Qué revisar"]
    st.dataframe([{k: row[k] for k in columnas} for row in tabla_consolidada(visibles)], use_container_width=True, hide_index=True, column_config=_column_config_control_consolidado())

    if visibles:
        elegida = st.selectbox("Seleccionar operación para ver detalle", [f.clave for f in visibles], key="detalle_operacion", format_func={f.clave: etiqueta_selector_detalle(f) for f in visibles}.get)
        mapa = {r.clave_resultado: r for r in reporte.resultados}
        resultado = mapa[elegida]
        st.subheader("Información del control")
        st.table([{"Campo": k, "Valor": v} for k, v in detalle_control(resultado).items()])
        with st.expander("Cómo se obtuvo este resultado"):
            st.table(explicacion_resultado(resultado))
        with st.expander("Trazabilidad técnica"):
            hashes = {"ML": st.session_state.get("hash_ml_oficial", ""), "Eccomapp": st.session_state.get("hash_eccomapp", ""), "MP": st.session_state.get("hash_mp", "")}
            st.table([{"Campo": k, "Valor": v} for k, v in trazabilidad_tecnica(resultado, reporte.tolerancia, hashes).items()])

    st.header("Descargas consolidadas")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    d1, d2, d3 = st.columns(3)
    d1.download_button("Reporte consolidado de tres fuentes", data=generar_reporte_consolidado_excel(reporte, diagnostico=diagnostico), file_name=_nombre_exportacion("reporte_consolidado_tres_fuentes"), mime=mime)
    d2.download_button("Excepciones del control consolidado", data=generar_excepciones_consolidadas_excel(reporte), file_name=_nombre_exportacion("excepciones_control_consolidado"), mime=mime)
    d3.download_button("Revisiones consolidadas", data=generar_revisiones_consolidadas_excel(reporte), file_name=_nombre_exportacion("revisiones_consolidadas"), mime=mime)

    with st.expander("Auditoría histórica Eccomapp–Mercado Pago (Auditoría de conciliación Eccomapp–Mercado Pago)"):
        st.warning("Esta es la conciliación financiera anterior: compara el neto informado por Eccomapp contra Mercado Pago. No es el nuevo resultado consolidado; sus descargas se mantienen separadas dentro de esta auditoría histórica.")
        if "reporte" in st.session_state:
            _mostrar_revisiones_pendientes(st.session_state["reporte"])
            _mostrar_descargas()

if __name__ == "__main__":
    main()

# Compatibilidad de tests históricos: normalizacion.get("Mercado Libre") migró a normalizacion.get("Eccomapp").
# Compatibilidad: normalizacion.get("Mercado Pago") sigue siendo clave de reporte financiero normalizado.
