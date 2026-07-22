"""APIs públicas de vinculación entre fuentes comerciales y financieras."""

from kiki_control.linking.commercial import vincular_ventas_oficiales_con_eccomapp
from kiki_control.linking.control_financiero import consolidar_control_financiero

__all__ = ["vincular_ventas_oficiales_con_eccomapp", "consolidar_control_financiero"]
