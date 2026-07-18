# Control Operativo App

Kiki Control Financiero es una aplicación profesional en Streamlit para controlar la conciliación entre ventas de Mercado Libre y movimientos financieros de Mercado Pago.

> La documentación oficial y completa del proyecto se encuentra en [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md).

## Alcance actual

La versión actual permite ejecutar el flujo inicial de conciliación en memoria:

- Inspección estructural de CSV de Mercado Libre y XLSX de Mercado Pago.
- Detección de fuente por firma de columnas, no por nombre de archivo.
- Normalización a modelos internos inmutables.
- Conciliación por `ID Order` con el motor `ML_MP_ID_ORDER_NETO_V1`.
- Interfaz Streamlit para carga, validación, configuración, procesamiento, resumen ejecutivo, filtros y detalle por operación.
- Pruebas unitarias e integrales sintéticas, sin datos reales.

No existe persistencia, historial, login, exportación, API, cálculo contable definitivo ni dashboard avanzado.

## Requisitos

- Python >= 3.11
- pandas
- openpyxl
- streamlit
- pytest para desarrollo y pruebas

## Instalación en modo desarrollo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

## Ejecutar tests

```bash
pytest
python -m compileall -q src tests app.py
```

## Iniciar la aplicación Streamlit

```bash
streamlit run app.py
```

`app.py` es un entrypoint delgado. La interfaz vive en `src/kiki_control/ui/streamlit_app.py` y delega la lógica de presentación pura a `src/kiki_control/presentation/`.

## Flujo de carga y conciliación

1. Cargar el CSV de ventas de Mercado Libre.
2. Cargar el XLSX de movimientos de Mercado Pago.
3. La app inspecciona ambos archivos y muestra metadatos seguros: fuente detectada, filas, columnas, tamaño, hash truncado, hoja usada y problemas estructurales.
4. Configurar la zona horaria operativa y la tolerancia monetaria.
5. Presionar **Procesar y conciliar** cuando ambos archivos sean válidos.
6. La app normaliza ambas fuentes, informa filas recibidas, normalizadas y rechazadas, y permite conciliación parcial si quedan registros válidos.
7. El motor de conciliación produce el reporte por operación.
8. La pantalla muestra resumen ejecutivo, tabla filtrable y detalle de cada resultado.

## Privacidad

Los archivos se reciben como bytes y se procesan únicamente en memoria durante la sesión de Streamlit. La aplicación no guarda archivos cargados ni resultados en disco o base de datos.

No deben incorporarse archivos reales de Mercado Libre, Mercado Pago, bancos u otras fuentes sensibles al repositorio. Los directorios `data/raw/`, `data/uploads/` y `private_data/` están excluidos para evitar cargas accidentales de datos privados.

La tabla y el detalle de interfaz evitan datos personales, documentos, tarjetas, JSON original y contenido crudo de filas financieras.

## Utilidad informada

La **utilidad informada por Mercado Libre** se muestra únicamente como valor provisto por la fuente comercial. No representa ganancia definitiva, resultado contable ni métrica fiscal validada.

El sistema no recalcula impuestos, utilidad ni resultado operativo definitivo. Los componentes financieros de Mercado Pago se exhiben como impactos separados para control y revisión.

## Limitaciones actuales

- Solo se procesan archivos manuales CSV de Mercado Libre y XLSX de Mercado Pago.
- No hay persistencia, historial ni usuarios.
- No hay exportación Excel/CSV desde la interfaz.
- No hay gráficos avanzados ni integraciones por API.
- No hay cálculo contable definitivo.
- Tienda Nube, bancos y local físico quedan fuera de esta etapa.

## Uso básico del inspector

```python
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

resultado = inspeccionar_archivo("archivo.csv", contenido_en_bytes)
```

El inspector no guarda archivos en disco y no expone contenidos financieros en mensajes de error.

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

## Motor de conciliación Mercado Libre / Mercado Pago

```python
from decimal import Decimal
from kiki_control.reconciliation import reconciliar

reporte = reconciliar(operaciones_comerciales, movimientos_financieros, tolerancia=Decimal("0.01"))
```

El motor recibe modelos normalizados, no lee archivos externos y no depende de Streamlit.
