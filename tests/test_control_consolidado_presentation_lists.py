from decimal import Decimal
from kiki_control.presentation.control_consolidado_diagnostics import GrupoExcluidoPuente, DiagnosticoRevision, diagnosticar_control_consolidado
from kiki_control.presentation.control_consolidado_view import (
    contar_mostrando,
    filtrar_grupos_excluidos,
    filtrar_grupos_involucrados_por_motivo,
    filas_grupos_excluidos,
    filas_grupos_involucrados,
    filas_resumen_revisiones,
    motivos_disponibles,
)
from tests.test_control_consolidado_diagnostics import D, E, r, rep


def test_grupos_excluidos_se_filtran_visual_sin_limitar_registros_y_con_conteos():
    grupos = tuple(
        GrupoExcluidoPuente(f"ORD-{i:03d}", "sin MP" if i % 2 else "sin Eccomapp", Decimal(i), None if i % 2 == 0 else Decimal(i), None, None)
        for i in range(1, 151)
    )

    assert len(grupos) == 150  # la lista extensa queda disponible para un expander cerrado en UI
    assert motivos_disponibles(grupos) == ("sin Eccomapp", "sin MP")
    por_id = filtrar_grupos_excluidos(grupos, "ORD-149", "")
    por_motivo = filtrar_grupos_excluidos(grupos, "", "sin Eccomapp")

    assert [g.grupo for g in por_id] == ["ORD-149"]
    assert len(por_motivo) == 75
    assert contar_mostrando(por_motivo, grupos) == "Mostrando 75 de 150 grupos"
    assert len(filtrar_grupos_excluidos(grupos, "", "")) == len(grupos)
    assert set(filas_grupos_excluidos(por_id)[0]) == {"Grupo", "Motivo", "Neto ML", "Neto Eccomapp", "Neto aprobado MP", "Aporte MP–ML"}


def test_revisiones_resumen_no_incluye_ids_extensos_y_detalle_una_fila_por_grupo():
    revisiones = (
        DiagnosticoRevision("Diferencia pendiente de clasificación contable", 3, Decimal("60"), "Revisar", ("ORD-001", "ORD-002", "ORD-ABC")),
        DiagnosticoRevision("Fuente faltante", 1, Decimal("10"), "Confirmar", ("ORD-999",)),
    )

    resumen = filas_resumen_revisiones(revisiones)
    assert list(resumen[0]) == ["Motivo visible", "Cantidad", "Importe afectado", "Acción recomendada"]
    assert "Grupos involucrados" not in resumen[0]

    grupos = filtrar_grupos_involucrados_por_motivo(revisiones, "Diferencia pendiente de clasificación contable", "abc")
    assert grupos == ("ORD-ABC",)
    assert filas_grupos_involucrados(grupos) == [{"Grupo": "ORD-ABC"}]
    assert contar_mostrando(grupos, 3) == "Mostrando 1 de 3 grupos"


def test_presentacion_de_listas_no_expone_pii_hashes_ni_claves_tecnicas():
    grupo = GrupoExcluidoPuente("ORD-VISIBLE-1", "sin MP", Decimal("1"), None, None, None)
    revision = DiagnosticoRevision("Fuente faltante", 1, Decimal("1"), "Confirmar cobertura", ("ORD-VISIBLE-2",))
    texto = str(filas_grupos_excluidos((grupo,))) + str(filas_resumen_revisiones((revision,))) + str(filas_grupos_involucrados(revision.grupos_involucrados))
    for prohibido in ("hash", "clave_resultado", "comprador", "documento", "email", "dni"):
        assert prohibido not in texto.lower()


def test_filtros_de_presentacion_no_mutan_diagnosticos_importes_ni_cantidades():
    reporte = rep([
        r("ok"),
        r("diff", E.CON_DIFERENCIA, mp=D("120"), dif=D("20"), revision=True),
        r("sin-mp", E.SIN_MOVIMIENTO_FINANCIERO, mp=None, dif=None, tiene_mp=False),
    ])
    diag = diagnosticar_control_consolidado(reporte)
    puente_antes = diag.puente
    revisiones_antes = diag.revisiones

    _ = filtrar_grupos_excluidos(diag.puente.grupos_excluidos_universo_triple, "sin-mp", "")
    if diag.revisiones.revisiones_multietiqueta:
        _ = filtrar_grupos_involucrados_por_motivo(diag.revisiones.revisiones_multietiqueta, diag.revisiones.revisiones_multietiqueta[0].motivo_visible, "diff")

    diag_despues = diagnosticar_control_consolidado(reporte)
    assert diag_despues.puente == puente_antes
    assert diag_despues.revisiones == revisiones_antes
    assert diag_despues.diferencias.suma_neto_mp_comparable == diag.diferencias.suma_neto_mp_comparable
    assert diag_despues.revisiones.total_primario_requiere_revision == reporte.total_requieren_revision
