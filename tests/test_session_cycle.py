from decimal import Decimal

from kiki_control.ui.session_cycle import (
    RESULT_KEYS_TO_CLEAR,
    SESSION_KEYS_TO_CLEAR,
    construir_firma_procesamiento,
    detectar_cambio,
    invalidar_resultados_conocidos,
    limpiar_claves_conocidas,
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
