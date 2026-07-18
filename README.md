# Control Operativo App

Kiki Control Financiero: base técnica para una aplicación profesional de control financiero.

> La documentación oficial y completa del proyecto se encuentra en [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md).

---

## Alcance actual

La versión 0.1 ya comenzó su implementación con módulos ejecutables de **recepción, identificación, inspección estructural** y **normalización del CSV comercial de Mercado Libre** y **normalización del XLSX financiero de Mercado Pago**.

El código actual permite:

- Recibir archivos como `bytes`, sin depender de Streamlit.
- Leer CSV UTF-8, CSV UTF-8 con BOM y XLSX.
- Seleccionar la primera hoja no vacía de un XLSX.
- Calcular metadatos auditables: extensión, tamaño, SHA-256, hoja usada, cantidad de filas y columnas encontradas.
- Detectar fuente por firma de columnas, no por nombre de archivo.
- Validar columnas obligatorias iniciales para Mercado Libre y Mercado Pago.
- Aceptar columnas adicionales como advertencias, sin bloquear la inspección.
- Normalizar CSV comerciales sintéticos de Mercado Libre a un modelo interno inmutable de operación comercial.
- Normalizar XLSX financieros sintéticos de Mercado Pago a un modelo interno inmutable de movimiento financiero.
- Parsear importes y porcentajes con `Decimal`, conservando identificadores como texto y trazabilidad por SHA-256 y número de fila original.
- Rechazar filas con errores críticos y conservar advertencias para campos opcionales o parámetros no interpretables.

Todavía **no existe interfaz Streamlit**, conciliación financiera, persistencia ni dashboard. La `utilidad_neta_informada` se conserva como valor provisto por Mercado Libre y no representa un resultado definitivo validado contablemente.

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
│       │   ├── contracts.py
│       │   ├── mercado_libre.py
│       │   └── mercado_pago.py
│       ├── domain/
│       │   ├── commercial_operation.py
│       │   ├── financial_movement.py
│       │   ├── enums.py
│       │   └── models.py
│       ├── ingestion/
│       │   ├── file_inspector.py
│       │   └── metadata.py
│       ├── normalization/
│       │   ├── locale_ar.py
│       │   ├── mercado_libre.py
│       │   ├── mercado_pago.py
│       │   └── values.py
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

## Uso mínimo de normalización de Mercado Pago

```python
from kiki_control.adapters.mercado_pago import normalizar_mercado_pago

resultado = normalizar_mercado_pago(
    nombre_archivo="movimientos.xlsx",
    contenido=contenido_xlsx_en_bytes,
)

for movimiento in resultado.movimientos:
    print(movimiento.id_operacion_mercado_pago, movimiento.tipo_operacion, movimiento.monto_neto_impactado)
```

La normalización financiera de Mercado Pago procesa XLSX en memoria, reutiliza `inspeccionar_archivo`, conserva el hash SHA-256 y la hoja inspeccionada, y entrega modelos internos inmutables sin exponer DataFrames como contrato público.

### Alcance actual de Mercado Pago

El adaptador normaliza movimientos financieros individuales, sin agruparlos por orden y sin ejecutar conciliación. Conserva importes positivos, negativos y cero con `Decimal`, mantiene identificadores como texto y registra timestamps originales junto con sus representaciones UTC y en la zona operativa configurable (`America/Argentina/Cordoba` por defecto).

Tipos de movimientos reconocidos inicialmente:

- `PAGO_APROBADO`
- `PAGO_ENVIO`
- `DEVOLUCION_DINERO`
- `DISPUTA_ENVIO`
- `RECLAMO`
- `DEVOLUCION_ENVIO`
- `PAYOUT`
- `CASHBACK`
- `DESCONOCIDA`

El `ID DE OPERACIÓN EN MERCADO PAGO` es obligatorio. El `ID DE LA ORDEN`, el SKU, la fecha de liquidación y otros identificadores complementarios pueden estar vacíos; el movimiento se conserva y se generan advertencias cuando corresponde. Esto permite aceptar PAYOUTS, cashback, operaciones de Point u otros movimientos que no pertenecen a una orden de Mercado Libre.

### Privacidad en Mercado Pago

El modelo público de movimiento financiero no incluye nombre del pagador, número de identificación del pagador, número inicial de tarjeta ni otros datos personales innecesarios. Los campos complementarios como impuestos desagregados, datos extra y operation tags se conservan de manera acotada para trazabilidad, y solo se extrae `refund_id` cuando está disponible.

> Todavía no existe conciliación entre Mercado Libre y Mercado Pago, persistencia, dashboard, Streamlit ni exportaciones de resultados.
