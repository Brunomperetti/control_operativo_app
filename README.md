# Control Operativo App

Kiki Control Financiero: base técnica para una aplicación profesional de control financiero.

> La documentación oficial y completa del proyecto se encuentra en [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md).

---

## Alcance actual

La versión 0.1 ya comenzó su implementación con módulos ejecutables de **recepción, identificación, inspección estructural** y **normalización del CSV comercial de Mercado Libre**.

El código actual permite:

- Recibir archivos como `bytes`, sin depender de Streamlit.
- Leer CSV UTF-8, CSV UTF-8 con BOM y XLSX.
- Seleccionar la primera hoja no vacía de un XLSX.
- Calcular metadatos auditables: extensión, tamaño, SHA-256, hoja usada, cantidad de filas y columnas encontradas.
- Detectar fuente por firma de columnas, no por nombre de archivo.
- Validar columnas obligatorias iniciales para Mercado Libre y Mercado Pago.
- Aceptar columnas adicionales como advertencias, sin bloquear la inspección.
- Normalizar CSV comerciales sintéticos de Mercado Libre a un modelo interno inmutable de operación comercial.
- Parsear importes y porcentajes con `Decimal`, conservando identificadores como texto y trazabilidad por SHA-256 y número de fila original.
- Rechazar filas con errores críticos y conservar advertencias para campos opcionales o parámetros no interpretables.

Todavía **no existe interfaz Streamlit**, conciliación financiera, normalización de Mercado Pago, persistencia ni dashboard. La `utilidad_neta_informada` se conserva como valor provisto por Mercado Libre y no representa un resultado definitivo validado contablemente.

---

## Requisitos

- Python >= 3.11
- pandas
- openpyxl
- pytest para desarrollo y pruebas

---

## Instalación en modo desarrollo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

---

## Ejecutar tests

```bash
pytest
```

---

## Uso básico del inspector

```python
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

resultado = inspeccionar_archivo("archivo.csv", contenido_en_bytes)
```

El inspector no guarda archivos en disco y no expone contenidos financieros en mensajes de error.

---


## Uso mínimo de normalización de Mercado Libre

```python
from kiki_control.adapters.mercado_libre import normalizar_mercado_libre

resultado = normalizar_mercado_libre(
    nombre_archivo="ventas.csv",
    contenido=contenido_csv_en_bytes,
)

for operacion in resultado.operaciones:
    print(operacion.id_orden, operacion.utilidad_neta_informada)
```

La normalización usa `America/Argentina/Cordoba` como zona horaria predeterminada configurable, utiliza primero el inspector estructural y no expone DataFrames como contrato público de dominio.

## Estructura técnica actual

```text
control_operativo_app/
├── src/
│   └── kiki_control/
│       ├── adapters/
│       │   └── contracts.py
│       ├── domain/
│       │   ├── commercial_operation.py
│       │   ├── enums.py
│       │   └── models.py
│       ├── ingestion/
│       │   ├── file_inspector.py
│       │   └── metadata.py
│       ├── normalization/
│       │   ├── locale_ar.py
│       │   └── mercado_libre.py
│       └── validation/
│           └── results.py
├── tests/
├── pyproject.toml
├── DOCUMENTO_MAESTRO.md
├── README.md
└── AI_CONTEXT.md
```

---

## Privacidad

No deben incorporarse archivos reales de Mercado Libre, Mercado Pago, bancos u otras fuentes sensibles al repositorio. Los directorios `data/raw/`, `data/uploads/` y `private_data/` están excluidos para evitar cargas accidentales de datos privados.
