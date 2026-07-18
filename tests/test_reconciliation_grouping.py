from tests.test_reconciliation_engine import mov, op
from kiki_control.reconciliation.grouping import agrupar_por_id_orden


def test_agrupacion_por_orden_y_sin_orden_determinista():
    grupos = agrupar_por_id_orden((op(id_orden="2"), op(id_orden="1")), (mov(id_orden="2"), mov(id_orden=None, fila=9)))
    assert grupos.ids_orden == ("1", "2")
    assert len(grupos.operaciones_por_orden["2"]) == 1
    assert len(grupos.movimientos_por_orden["2"]) == 1
    assert len(grupos.movimientos_sin_orden) == 1
