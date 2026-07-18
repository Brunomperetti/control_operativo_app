from kiki_control.ingestion.file_inspector import inspeccionar_archivo
from tests.test_file_inspector import ML, csv_bytes


def test_mismo_contenido_produce_mismo_sha256():
    contenido = csv_bytes(ML)
    primero = inspeccionar_archivo("uno.csv", contenido)
    segundo = inspeccionar_archivo("dos.csv", contenido)
    assert primero.metadatos.sha256 == segundo.metadatos.sha256
    assert primero.metadatos.tamaño_bytes == len(contenido)
