from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from kiki_control.domain.financial_movement import TipoOperacionFinanciera
from kiki_control.domain.reconciliation import EstadoConciliacion
from kiki_control.presentation.formatters import formato_pesos_argentino
from kiki_control.presentation.reconciliation_view import ETIQUETAS_ESTADO, ENCABEZADOS_TABLA_CLIENTE, conclusion_ejecutiva, cobertura_archivos, detalle_cliente, detalle_presentacion, detalle_tecnico_seguro, es_excepcion_o_caso_especial, filas_presentacion, filtrar_filas, filtrar_resultados_por_vista, resultado_a_fila, resumen_kpis, tabla_principal
from kiki_control.reconciliation import reconciliar
from tests.test_reconciliation_engine import mov, op


def test_formato_monetario_argentino():
    assert formato_pesos_argentino(Decimal("13026524.25")) == "$ 13.026.524,25"
    assert formato_pesos_argentino(Decimal("-3199.9")) == "-$ 3.199,90"
    assert formato_pesos_argentino(Decimal("0")) == "$ 0,00"
    assert formato_pesos_argentino(None) == "—"


def test_etiquetas_de_todos_los_estados():
    assert set(ETIQUETAS_ESTADO) == set(EstadoConciliacion)
    assert ETIQUETAS_ESTADO[EstadoConciliacion.CONCILIADA] == "Conciliada"
    assert ETIQUETAS_ESTADO[EstadoConciliacion.MOVIMIENTO_DE_FONDOS] == "Movimiento de fondos"


def test_conversion_a_fila_sin_campos_personales_y_diferencia_con_signo():
    resultado = reconciliar([op(neto="100")], [mov(monto="90")]).resultados[0]
    fila = resultado_a_fila(resultado)
    assert fila.id_orden == "1"
    assert fila.estado == "Con diferencia"
    assert fila.diferencia == "-$ 10,00"
    assert fila.diferencia_valor == Decimal("-10")
    campos = set(fila.__dict__)
    assert "nombre_pagador" not in campos
    assert "numero_identificacion" not in campos
    assert "tarjeta" not in campos
    assert "json_original" not in campos


def test_filtros_estado_busqueda_revision_y_pago_dividido():
    reporte = reconciliar(
        [op(id_orden="A", neto="100"), op(id_orden="B", neto="50"), op(id_orden="C", neto="20")],
        [mov(id_orden="A", monto="100"), mov(id_orden="B", monto="10", id_mp="b1"), mov(id_orden="B", monto="40", id_mp="b2"), mov(id_orden="X", monto="1", id_mp="x")],
    )
    filas = filas_presentacion(reporte.resultados)
    assert [f.id_orden for f in filtrar_filas(filas, {EstadoConciliacion.CONCILIADA.value})] == ["A", "B"]
    assert [f.id_orden for f in filtrar_filas(filas, busqueda_id="c")] == ["C"]
    assert [f.id_orden for f in filtrar_filas(filas, solo_revision=True)] == ["C", "X"]
    assert [f.id_orden for f in filtrar_filas(filas, solo_pago_dividido=True)] == ["B"]


def test_resumen_kpis_orden_determinista_sin_id_y_totales_decimal():
    reporte = reconciliar(
        [op(id_orden="B", neto="50", utilidad="5"), op(id_orden="A", neto="100", utilidad="10")],
        [mov(id_orden="A", monto="101"), mov(id_orden="B", monto="50", id_mp="b"), mov(id_orden=None, tipo=TipoOperacionFinanciera.PAYOUT, monto="-20", id_mp="p", fila=7)],
    )
    filas = filas_presentacion(reporte.resultados)
    assert [f.id_orden for f in filas] == ["A", "B", "movimiento_de_fondos-fila-7"]
    assert filas[-1].estado == "Movimiento de fondos"
    kpis = resumen_kpis(reporte)
    assert kpis["Comparables"] == 2
    assert kpis["Movimientos de fondos"] == 1
    assert kpis["Neto ML comparable"] == "$ 150,00"
    assert kpis["Neto MP comparable"] == "$ 151,00"
    assert kpis["Diferencia comparable"] == "$ 1,00"
    assert "Neto de pagos aprobados" not in kpis
    assert "Diferencia total de control" not in kpis
    assert "Sin contraparte" not in kpis
    assert kpis["Utilidad informada ML"] == "$ 15,00"


def test_detalle_presentacion_completo():
    resultado = reconciliar([op(neto="100")], [mov(monto="40", id_mp="a"), mov(monto="60", id_mp="b", fila=11)]).resultados[0]
    detalle = detalle_presentacion(resultado)
    assert detalle["ID de orden"] == "1"
    assert detalle["Cantidad de pagos aprobados"] == 2
    assert detalle["Pago dividido"] == "Sí"
    assert detalle["Neto financiero total"] == "$ 100,00"
    assert "Neto de pagos aprobados" not in detalle


def test_resumen_separa_alcances_y_no_mezcla_exclusivos_mp_con_comparables():
    reporte = reconciliar(
        [op(id_orden="EXACTA", neto="100", utilidad="10"), op(id_orden="DIF", neto="50", utilidad="5"), op(id_orden="SINMOV", neto="30", utilidad="3")],
        [
            mov(id_orden="EXACTA", monto="100", id_mp="mp-exacta"),
            mov(id_orden="DIF", monto="60", id_mp="mp-dif"),
            mov(id_orden="SOLOMP", monto="70", id_mp="mp-solo"),
            mov(id_orden="DEV", monto="-25", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="mp-dev"),
            mov(id_orden="REC", monto="-15", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="mp-rec"),
            mov(id_orden=None, monto="-200", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="mp-payout", fila=20),
        ],
    )
    kpis = resumen_kpis(reporte)
    assert kpis["Comparables"] == 2
    assert kpis["Coincidencias exactas"] == 1
    assert kpis["Con diferencia"] == 1
    assert kpis["Sin venta en ML"] == 3
    assert kpis["Sin movimiento en MP"] == 1
    assert kpis["Movimientos de fondos"] == 1
    assert kpis["Neto ML comparable"] == "$ 150,00"
    assert kpis["Neto MP comparable"] == "$ 160,00"
    assert kpis["Diferencia comparable"] == "$ 10,00"
    assert kpis["Neto MP fuera del archivo ML"] == "$ 70,00"
    sin_operacion = [r for r in reporte.resultados if r.cantidad_operaciones_comerciales == 0 and r.estado != EstadoConciliacion.MOVIMIENTO_DE_FONDOS]
    assert {r.estado for r in sin_operacion} == {EstadoConciliacion.MOVIMIENTO_SIN_OPERACION_COMERCIAL, EstadoConciliacion.DEVUELTA, EstadoConciliacion.EN_RECLAMO}
    assert all(isinstance(v, Decimal) for r in reporte.resultados for v in (r.neto_financiero_total, r.impacto_devoluciones, r.impacto_reclamos_disputas, r.impacto_otros))
    assert not any(isinstance(v, float) for r in reporte.resultados for v in asdict(r).values())
    texto_presentacion = str(kpis) + str([f.__dict__ for f in filas_presentacion(reporte.resultados)])
    for pii in ("Persona", "DNI", "tarjeta", "email", "12345678"):
        assert pii not in texto_presentacion


def test_cobertura_archivos_periodos_iguales_diferentes_y_liquidaciones():
    operaciones = [op(id_orden="A", fila=1), op(id_orden="B", fila=2)]
    movimientos = [mov(id_orden="A", id_mp="a", liquidado=True), mov(id_orden="B", id_mp="b", liquidado=False)]
    cobertura = cobertura_archivos(operaciones, movimientos)
    assert cobertura.periodo_ventas_ml.texto == "01/01/2026"
    assert cobertura.periodo_origen_mp.texto == "01/01/2026"
    assert cobertura.periodo_liquidacion_mp.texto == "01/01/2026"
    assert cobertura.movimientos_sin_fecha_liquidacion == 1
    assert cobertura.origenes_coinciden is True
    assert cobertura.advertencia_origenes is None

    otra_fecha = datetime(2026, 1, 3, tzinfo=UTC)
    diferentes = cobertura_archivos([op(id_orden="C", fila=3)], [mov(id_orden="C", id_mp="c", hash_="h3")])
    assert diferentes.origenes_coinciden is True
    movimiento_fuera = mov(id_orden="Z", id_mp="z")
    movimiento_fuera = movimiento_fuera.__class__(**{**asdict(movimiento_fuera), "fecha_origen_utc": otra_fecha, "fecha_origen_local": otra_fecha})
    diferentes = cobertura_archivos([op(id_orden="C", fila=3)], [movimiento_fuera])
    assert diferentes.periodo_origen_mp.texto == "03/01/2026"
    assert diferentes.origenes_coinciden is False
    assert diferentes.advertencia_origenes is not None
    assert "no coinciden" in diferentes.advertencia_origenes
    assert "recortar" in diferentes.advertencia_origenes


def test_conclusion_ejecutiva_sin_excepciones_verde_y_sin_ganancia():
    reporte = reconciliar([op(id_orden="A", neto="100"), op(id_orden="B", neto="50")], [mov(id_orden="A", monto="100"), mov(id_orden="B", monto="50")])
    texto, severidad = conclusion_ejecutiva(reporte)
    assert severidad == "ok"
    assert "2 coinciden exactamente" in texto
    assert "0 presentan diferencias" in texto
    assert "0 resultados con excepciones o condiciones especiales" in texto
    assert "ganancia" not in texto.lower()


def test_conclusion_ejecutiva_con_diferencias_revision_y_solo_fuente():
    reporte = reconciliar([op(id_orden="A", neto="100"), op(id_orden="B", neto="20")], [mov(id_orden="A", monto="95"), mov(id_orden="SOLOMP", monto="10")])
    texto, severidad = conclusion_ejecutiva(reporte)
    assert severidad == "advertencia"
    assert "1 presenta diferencias" in texto
    assert "3 resultados con excepciones o condiciones especiales" in texto
    assert "2 requieren revisión manual" in texto
    assert "1 grupo presente solo en Mercado Pago" in texto
    assert "1 operación presente solo en Mercado Libre" in texto


def test_clasificacion_excepciones_incluye_devolucion_reclamo_pago_dividido_y_payout():
    reporte = reconciliar(
        [op(id_orden="OK", neto="100"), op(id_orden="DIV", neto="30")],
        [
            mov(id_orden="OK", monto="100"),
            mov(id_orden="DIV", monto="10", id_mp="d1"),
            mov(id_orden="DIV", monto="20", id_mp="d2"),
            mov(id_orden="DEV", monto="-5", tipo=TipoOperacionFinanciera.DEVOLUCION_DINERO, id_mp="dev"),
            mov(id_orden="REC", monto="-7", tipo=TipoOperacionFinanciera.RECLAMO, id_mp="rec"),
            mov(id_orden=None, monto="-50", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="payout", fila=99),
        ],
    )
    excepciones = filtrar_resultados_por_vista(reporte.resultados, "Excepciones y casos especiales")
    ids = {r.id_orden or r.estado.value for r in excepciones}
    assert "OK" not in ids
    assert {"DIV", "DEV", "REC", "MOVIMIENTO_DE_FONDOS"}.issubset(ids)
    assert all(es_excepcion_o_caso_especial(r) for r in excepciones)


def test_tabla_principal_encabezados_espanol_sin_tecnicos_ni_pii():
    reporte = reconciliar([op(id_orden="SYN-1", neto="100")], [mov(id_orden="SYN-1", monto="90")])
    fila = filas_presentacion(reporte.resultados)[0]
    tabla = tabla_principal([fila])
    assert list(tabla[0]) == list(ENCABEZADOS_TABLA_CLIENTE.values())
    texto = str(tabla)
    prohibidos = ["motivo_principal", "estado_codigo", "clave", "diferencia_valor", "hash", "contenido", "nombre", "email", "DNI", "12345678"]
    for prohibido in prohibidos:
        assert prohibido not in texto


def test_detalle_cliente_separa_trazabilidad_tecnica():
    resultado = reconciliar([op(neto="100")], [mov(monto="100")]).resultados[0]
    cliente = detalle_cliente(resultado)
    tecnico = detalle_tecnico_seguro(resultado)
    assert cliente["ID de orden"] == "1"
    assert "Motivos internos" not in cliente
    assert "Versión de regla" in tecnico
    assert tecnico["Motivos internos"]


def test_presentacion_no_modifica_estados_del_dominio():
    reporte = reconciliar([op(id_orden="A", neto="100")], [mov(id_orden="A", monto="95")])
    estados_antes = tuple(r.estado for r in reporte.resultados)
    _ = conclusion_ejecutiva(reporte)
    _ = filtrar_resultados_por_vista(reporte.resultados, "Excepciones y casos especiales")
    _ = tabla_principal(filas_presentacion(reporte.resultados))
    estados_despues = tuple(r.estado for r in reporte.resultados)
    assert estados_despues == estados_antes == (EstadoConciliacion.CONCILIADA_CON_DIFERENCIA,)


def test_conclusion_ejecutiva_pluraliza_cero_uno_y_varios():
    solo_una = reconciliar([op(id_orden="UNO", neto="10")], [mov(id_orden="UNO", monto="10")])
    texto_uno, _ = conclusion_ejecutiva(solo_una)
    assert "Se comparó 1 operación" in texto_uno
    assert "1 coincide exactamente" in texto_uno
    assert "0 presentan diferencias" in texto_uno
    assert "0 grupos presentes solo en Mercado Pago" in texto_uno
    assert "0 movimientos de fondos informados por separado" in texto_uno

    varios = reconciliar([op(id_orden="A", neto="10"), op(id_orden="B", neto="20")], [mov(id_orden="A", monto="10"), mov(id_orden="B", monto="21")])
    texto_varios, _ = conclusion_ejecutiva(varios)
    assert "Se compararon 2 operaciones" in texto_varios
    assert "1 coincide exactamente" in texto_varios
    assert "1 presenta diferencias" in texto_varios


def test_conclusion_ejecutiva_payout_separado_de_revision_manual():
    reporte = reconciliar([], [mov(id_orden=None, monto="-10", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="payout-sintetico", fila=30)])
    texto, severidad = conclusion_ejecutiva(reporte)
    assert severidad == "advertencia"
    assert "1 resultado con excepciones o condiciones especiales" in texto
    assert "0 requieren revisión manual" in texto
    assert "1 movimiento de fondos informado por separado" in texto


def test_detalle_cliente_usa_clave_segura_si_no_hay_id_orden():
    resultado = reconciliar([], [mov(id_orden=None, monto="-10", tipo=TipoOperacionFinanciera.PAYOUT, id_mp="payout-detalle", fila=77)]).resultados[0]
    detalle = detalle_cliente(resultado)
    assert detalle["ID de orden"] == "movimiento_de_fondos-fila-77"


def test_textos_visibles_no_exponen_diferencia_control_snake_case():
    reporte = reconciliar([op(id_orden="A", neto="10")], [mov(id_orden="A", monto="10")])
    texto, _ = conclusion_ejecutiva(reporte)
    detalle = detalle_cliente(reporte.resultados[0])
    tabla = tabla_principal(filas_presentacion(reporte.resultados))
    visible = texto + str(detalle) + str(tabla)
    assert "diferencia_control" not in visible
