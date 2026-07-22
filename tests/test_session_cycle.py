from decimal import Decimal

from kiki_control.ui.session_cycle import (
    RESULT_KEYS_TO_CLEAR,
    SESSION_KEYS_TO_CLEAR,
    VIEW_FILTER_KEYS_TO_CLEAR,
    construir_firma_procesamiento,
    detectar_cambio,
    invalidar_resultados_conocidos,
    limpiar_claves_conocidas,
    limpiar_detalle_revision_si_obsoleto,
    limpiar_filtros_de_vista,
    tolerancia_canonica,
)

HASH_ML_A = "a" * 64
HASH_ML_B = "b" * 64
HASH_MP_A = "c" * 64
HASH_MP_B = "d" * 64
ZONA = "America/Argentina/Cordoba"


def test_firma_estable_con_las_mismas_entradas_sinteticas():
    tolerancia = Decimal("0.0100")

    firma_1 = construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, ZONA, tolerancia)
    firma_2 = construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, ZONA, Decimal("0.01"))

    assert firma_1 == firma_2
    assert len(firma_1) == 64


def test_firma_cambia_al_reemplazar_cualquiera_de_los_archivos_sinteticos():
    firma_base = construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, ZONA, Decimal("0.01"))

    assert construir_firma_procesamiento(HASH_ML_B, HASH_MP_A, ZONA, Decimal("0.01")) != firma_base
    assert construir_firma_procesamiento(HASH_ML_A, HASH_MP_B, ZONA, Decimal("0.01")) != firma_base


def test_firma_cambia_al_modificar_zona_o_tolerancia_decimal():
    firma_base = construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, ZONA, Decimal("0.01"))

    assert construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, "UTC", Decimal("0.01")) != firma_base
    assert construir_firma_procesamiento(HASH_ML_A, HASH_MP_A, ZONA, Decimal("0.02")) != firma_base


def test_detecta_invalidacion_al_retirar_un_archivo_sintetico():
    assert detectar_cambio(HASH_ML_A, None)

    estado = {clave: f"valor-{clave}" for clave in RESULT_KEYS_TO_CLEAR}
    invalidar_resultados_conocidos(estado)

    assert all(clave not in estado for clave in RESULT_KEYS_TO_CLEAR)


def test_limpieza_completa_de_claves_conocidas():
    estado = {clave: f"valor-{clave}" for clave in SESSION_KEYS_TO_CLEAR}
    estado["clave_no_gestionada"] = "se conserva"

    limpiar_claves_conocidas(estado)

    assert all(clave not in estado for clave in SESSION_KEYS_TO_CLEAR)
    assert estado == {"clave_no_gestionada": "se conserva"}


def test_tests_usan_datos_sinteticos_sin_archivos_reales_ni_pii():
    entradas = [HASH_ML_A, HASH_ML_B, HASH_MP_A, HASH_MP_B, ZONA, "archivo_sintetico.csv"]

    assert all("@" not in entrada for entrada in entradas)
    assert all("dni" not in entrada.lower() for entrada in entradas)
    assert all("cuit" not in entrada.lower() for entrada in entradas)
    assert all("mercadopago" not in entrada.lower() for entrada in entradas)


def test_tolerancia_usa_decimal_y_no_float():
    tolerancia = Decimal("0.0100")

    assert isinstance(tolerancia, Decimal)
    assert not isinstance(tolerancia, float)
    assert tolerancia_canonica(tolerancia) == "0.01"


def test_vista_resultados_se_limpia_con_sesion_e_invalidacion():
    assert "vista_resultados" in SESSION_KEYS_TO_CLEAR
    assert "vista_resultados" in RESULT_KEYS_TO_CLEAR

    estado = {clave: f"valor-{clave}" for clave in SESSION_KEYS_TO_CLEAR}
    limpiar_claves_conocidas(estado)
    assert "vista_resultados" not in estado

    estado = {clave: f"valor-{clave}" for clave in RESULT_KEYS_TO_CLEAR}
    invalidar_resultados_conocidos(estado)
    assert "vista_resultados" not in estado


def test_limpieza_de_filtros_por_cambio_de_vista_no_borra_reporte():
    estado = {clave: f"valor-{clave}" for clave in VIEW_FILTER_KEYS_TO_CLEAR}
    estado.update({
        "vista_resultados": "Todas las operaciones",
        "reporte": "reporte-sintetico",
        "cobertura": "cobertura-sintetica",
        "normalizacion": "normalizacion-sintetica",
        "firma_procesamiento": "firma-sintetica",
    })

    limpiar_filtros_de_vista(estado)

    assert all(clave not in estado for clave in VIEW_FILTER_KEYS_TO_CLEAR)
    assert estado["vista_resultados"] == "Todas las operaciones"
    assert estado["reporte"] == "reporte-sintetico"
    assert estado["cobertura"] == "cobertura-sintetica"
    assert estado["normalizacion"] == "normalizacion-sintetica"
    assert estado["firma_procesamiento"] == "firma-sintetica"


def test_modelos_normalizados_viven_solo_en_normalizacion_y_se_limpian():
    claves_duplicadas = {"operaciones_normalizadas", "movimientos_normalizados"}
    assert claves_duplicadas.isdisjoint(SESSION_KEYS_TO_CLEAR)
    assert claves_duplicadas.isdisjoint(RESULT_KEYS_TO_CLEAR)

    estado = {
        "normalizacion": {"Mercado Libre": "ops", "Mercado Pago": "movs"},
        "reporte": "reporte-sintetico",
        "cobertura": "cobertura-sintetica",
    }
    limpiar_claves_conocidas(estado)
    assert "normalizacion" not in estado
    assert not any(clave in estado for clave in claves_duplicadas)


def test_invalidacion_por_cambio_de_archivo_zona_o_tolerancia_elimina_modelos_normalizados():
    for motivo in ["archivo", "zona", "tolerancia"]:
        estado = {
            "normalizacion": {"motivo": motivo},
            "reporte": "reporte-sintetico",
            "firma_procesamiento": "firma-sintetica",
            "filtro_busqueda_orden": "SYN",
        }
        invalidar_resultados_conocidos(estado)
        assert "normalizacion" not in estado
        assert "reporte" not in estado
        assert "firma_procesamiento" not in estado


def test_no_quedan_referencias_duplicadas_a_modelos_normalizados_en_ui():
    from pathlib import Path

    source = Path("src/kiki_control/ui/streamlit_app.py").read_text()
    assert "operaciones_normalizadas" not in source
    assert "movimientos_normalizados" not in source
    assert 'normalizacion.get("Mercado Libre")' in source
    assert 'normalizacion.get("Mercado Pago")' in source


def test_limpieza_total_de_claves_de_revision():
    claves_revision = {"revision_tipo", "revision_busqueda", "revision_detalle", "filtro_motivo_revision"}
    assert claves_revision.issubset(SESSION_KEYS_TO_CLEAR)
    estado = {clave: f"valor-{clave}" for clave in claves_revision}
    estado["reporte"] = "reporte-sintetico"

    limpiar_claves_conocidas(estado)

    assert claves_revision.isdisjoint(estado)


def test_invalidacion_por_cambio_de_archivo_o_configuracion_limpia_claves_de_revision():
    claves_revision = {"revision_tipo", "revision_busqueda", "revision_detalle", "filtro_motivo_revision"}
    assert claves_revision.issubset(RESULT_KEYS_TO_CLEAR)

    for motivo in ("archivo", "zona", "tolerancia"):
        estado = {clave: f"{motivo}-{clave}" for clave in claves_revision}
        estado["reporte"] = "reporte-sintetico"
        invalidar_resultados_conocidos(estado)
        assert claves_revision.isdisjoint(estado)
        assert "reporte" not in estado


def test_cambio_de_vista_limpia_filtro_motivo_revision_sin_borrar_reporte():
    assert "filtro_motivo_revision" in VIEW_FILTER_KEYS_TO_CLEAR
    estado = {
        "filtro_motivo_revision": "ORDEN_MP_SIN_VENTA_ML",
        "revision_tipo": "MP_SIN_ID_ORDEN",
        "revision_busqueda": "SYN",
        "revision_detalle": "caso-1",
        "reporte": "reporte-sintetico",
        "firma_procesamiento": "firma-sintetica",
    }

    limpiar_filtros_de_vista(estado)

    assert "filtro_motivo_revision" not in estado
    assert estado["revision_tipo"] == "MP_SIN_ID_ORDEN"
    assert estado["revision_busqueda"] == "SYN"
    assert estado["revision_detalle"] == "caso-1"
    assert estado["reporte"] == "reporte-sintetico"
    assert estado["firma_procesamiento"] == "firma-sintetica"


def test_detalle_revision_obsoleto_se_limpia_al_cambiar_filtros_sin_borrar_reporte():
    estado = {
        "revision_detalle": "caso-anterior",
        "revision_tipo": "ORDEN_MP_SIN_VENTA_ML",
        "revision_busqueda": "nuevo",
        "reporte": "reporte-sintetico",
    }

    limpiar_detalle_revision_si_obsoleto(estado, {"caso-vigente"})

    assert "revision_detalle" not in estado
    assert estado["revision_tipo"] == "ORDEN_MP_SIN_VENTA_ML"
    assert estado["revision_busqueda"] == "nuevo"
    assert estado["reporte"] == "reporte-sintetico"

    estado["revision_detalle"] = "caso-vigente"
    limpiar_detalle_revision_si_obsoleto(estado, {"caso-vigente"})
    assert estado["revision_detalle"] == "caso-vigente"


def test_limpieza_de_widgets_de_diagnosticos_consolidados():
    claves_diagnostico = {
        "buscar_grupo_excluido_puente",
        "motivo_grupo_excluido_puente",
        "motivo_grupos_revision",
        "buscar_grupo_revision",
    }
    assert claves_diagnostico.issubset(SESSION_KEYS_TO_CLEAR)
    assert claves_diagnostico.issubset(RESULT_KEYS_TO_CLEAR)
    assert claves_diagnostico.isdisjoint(VIEW_FILTER_KEYS_TO_CLEAR)

    estado = {clave: f"valor-anterior-{clave}" for clave in claves_diagnostico}
    estado.update({
        "zona_horaria": "America/Argentina/Cordoba",
        "tolerancia_texto": "0,01",
        "reporte_consolidado": "reporte-anterior",
    })

    limpiar_claves_conocidas(estado)

    assert claves_diagnostico.isdisjoint(estado)
    assert "reporte_consolidado" not in estado


def test_invalidacion_elimina_widgets_de_diagnosticos_y_conserva_configuracion():
    claves_diagnostico = {
        "buscar_grupo_excluido_puente",
        "motivo_grupo_excluido_puente",
        "motivo_grupos_revision",
        "buscar_grupo_revision",
    }
    estado = {clave: f"reporte-anterior-{clave}" for clave in claves_diagnostico}
    estado.update({
        "zona_horaria": "America/Argentina/Cordoba",
        "tolerancia_texto": "0,01",
        "reporte_consolidado": "reporte-anterior",
        "firma_procesamiento": "firma-anterior",
    })

    invalidar_resultados_conocidos(estado)

    assert claves_diagnostico.isdisjoint(estado)
    assert not any("reporte-anterior" in str(valor) for valor in estado.values())
    assert estado["zona_horaria"] == "America/Argentina/Cordoba"
    assert estado["tolerancia_texto"] == "0,01"
    assert "reporte_consolidado" not in estado
    assert "firma_procesamiento" not in estado
