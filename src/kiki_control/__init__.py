"""Kiki Control Financiero."""

from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from kiki_control.linking.control_financiero import consolidar_control_financiero

__all__ = ["inspeccionar_archivo", "consolidar_control_financiero"]
