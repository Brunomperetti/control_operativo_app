# Control Operativo App

Kiki Control Financiero es una aplicación profesional en Streamlit para controlar la conciliación entre fuentes comerciales, costos operativos y movimientos financieros. Actualmente distingue el XLSX oficial de ventas de Mercado Libre, el CSV de rentabilidad de Eccomapp y el XLSX financiero de Mercado Pago.

> La documentación oficial y completa del proyecto se encuentra en [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md).

## Alcance actual

La versión actual permite ejecutar el flujo inicial de conciliación en memoria:

- Inspección estructural de tres fuentes: XLSX oficial de ventas de Mercado Libre (`MERCADO_LIBRE_VENTAS`), CSV de rentabilidad de Eccomapp (`ECCOMAPP_RENTABILIDAD`, antes tratado como Mercado Libre) y XLSX financiero de Mercado Pago (`MERCADO_PAGO`).
- Detección de fuente por firma de columnas, no por nombre de archivo.
- Normalización a modelos internos inmutables, incluyendo `VentaOficialMercadoLibre` para el XLSX oficial comercial sin datos personales.
- Conciliación por `ID Order` con el motor `ML_MP_ID_ORDER_NETO_V1`.
- Interfaz Streamlit para carga, validación, configuración, procesamiento, resumen ejecutivo, descargas Excel, filtros, detalle por operación y ciclo seguro de sesión.
- Pruebas unitarias e integrales sintéticas, sin datos reales.

No existe persistencia, historial, login, API, cálculo contable definitivo ni dashboard avanzado. La exportación disponible es XLSX en memoria del reporte vigente. Todavía no se implementó el cruce de tres fuentes entre Mercado Libre oficial, Eccomapp y Mercado Pago.

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

## Nota para Streamlit Community Cloud

`requirements.txt` existe exclusivamente como entrypoint de instalación para Streamlit Community Cloud. `pyproject.toml` continúa siendo la fuente oficial de metadatos y dependencias del paquete.

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

1. Cargar el CSV de rentabilidad de Eccomapp mediante el flujo histórico compatible.
2. Cargar el XLSX de movimientos de Mercado Pago.
3. El XLSX oficial de ventas de Mercado Libre ya puede detectarse y normalizarse por API pública, pero todavía no participa en la conciliación de la UI.
4. La app inspecciona los archivos de conciliación actuales y muestra metadatos seguros: fuente detectada, filas, columnas, tamaño, hash truncado, hoja usada y problemas estructurales.
5. Configurar la zona horaria operativa y la tolerancia monetaria.
6. Presionar **Procesar y conciliar** cuando ambos archivos sean válidos.
   - La aplicación firma el procesamiento con los hashes SHA-256 de ambos archivos, la zona horaria y la tolerancia monetaria normalizada como `Decimal`.
   - Si se elimina o reemplaza cualquiera de los archivos, o cambia la zona horaria o la tolerancia, se invalidan de inmediato normalizaciones, cobertura, reporte, filtros, detalle y firma anterior.
   - Nunca se muestra un reporte cuya firma no coincida con los archivos y la configuración actuales.
7. La app normaliza ambas fuentes, informa filas recibidas, normalizadas y rechazadas, y permite conciliación parcial si quedan registros válidos.
8. El motor de conciliación produce el reporte por operación.
9. La pantalla muestra la cobertura temporal de ambos archivos, conclusión ejecutiva, resumen ejecutivo, descargas Excel, tabla filtrable y detalle de cada resultado.


## Cobertura y alcance de métricas

La cobertura comercial y la cobertura financiera pueden ser distintas porque el CSV de Mercado Libre informa el período de ventas incluido, mientras que el XLSX de Mercado Pago informa movimientos por fecha de origen y por fecha de liquidación. La interfaz muestra esos tres rangos antes del resumen ejecutivo y cuenta los movimientos sin fecha de liquidación.

Cuando los períodos de origen no coinciden, la aplicación emite una advertencia informativa y continúa la conciliación sin inventar reglas de recorte. Un movimiento financiero sin contraparte comercial puede corresponder a otro período de archivo y requiere análisis manual; no se clasifica automáticamente como pérdida comercial ni como error.

La presentación para cliente usa etiquetas cortas y separa los alcances:

- **Comparables:** resultados con `diferencia_control` calculada. Sus métricas incluyen **Neto ML comparable**, **Neto MP comparable** y **Diferencia comparable** solo para ese universo.
- **Sin venta en ML:** grupos financieros sin operación comercial asociada, excluyendo `MOVIMIENTO_DE_FONDOS`. Pueden incluir devoluciones o reclamos aunque su estado final sea `DEVUELTA` o `EN_RECLAMO` por prioridad.
- **Sin movimiento en MP:** ventas presentes en Mercado Libre sin movimientos financieros asociados.
- **Movimientos de fondos:** se mantienen separados y no se tratan como pérdidas comerciales.

La conclusión ejecutiva se genera como transformación pura de presentación: no recalcula importes, no cambia estados del dominio, no llama ganancia a la utilidad informada y solo se muestra en verde cuando no existen diferencias ni casos especiales.

## Vista de resultados para cliente

La tabla principal inicia en **Excepciones y casos especiales** y permite cambiar a **Todas las operaciones**. La vista de excepciones incluye, solo como clasificación visual, resultados que requieren revisión, estados distintos de conciliada, diferencias de control, devoluciones, reclamos o disputas, liquidaciones pendientes, pagos divididos y movimientos de fondos.

Los encabezados visibles de la tabla principal están en español: ID de orden, Estado, Neto informado ML, Neto aprobado MP, Diferencia, Neto financiero total, Utilidad informada ML, Pago dividido, Devolución, Reclamo o disputa, Pendiente de acreditación y Requiere revisión. La tabla no muestra motivos internos, códigos de estado, claves internas, hashes, contenido crudo ni PII.

El detalle de operación se divide en:

- **Información de la operación:** estado, importes, diferencia, indicadores principales y explicación en español.
- **Trazabilidad técnica:** expander con motivos internos, filas comerciales y financieras de origen, versión de regla y datos técnicos seguros.

Las advertencias de normalización mantienen conteos visibles y despliegan el detalle en expanders cerrados.

## Exportaciones Excel

Después del resumen ejecutivo, la sección **Descargas** ofrece dos archivos XLSX generados exclusivamente en memoria, sin guardar copias en el servidor:

- **Descargar reporte completo:** incluye las hojas **Resumen**, **Todas las operaciones** y **Excepciones**.
- **Descargar solo excepciones:** incluye las hojas **Resumen** y **Excepciones**; no contiene la hoja de todas las operaciones.

Las hojas operativas usan encabezados visibles en español y un alcance controlado: ID de orden, estado, importes de control, utilidad informada ML, indicadores de revisión, explicación, motivos técnicos seguros, filas de origen, cantidad de pagos/movimientos, versión de regla y tolerancia aplicada. No exportan datos personales, pagador, documento, tarjeta, contenido crudo, metadatos sensibles, claves internas de Streamlit ni nombres de archivos originales.

Los ID se escriben como texto para conservar ceros iniciales y evitar notación científica. Los importes y la tolerancia se preparan con `Decimal`, se escriben como valores numéricos y reciben formato monetario argentino; los valores ausentes quedan vacíos y los importes negativos conservan su signo. Los indicadores booleanos se muestran como **Sí** o **No**.

Para prevenir inyección de fórmulas, cualquier texto exportado que comience con `=`, `+`, `-` o `@` se escribe de forma segura para que Excel no lo ejecute como fórmula. La utilidad mantiene siempre la etiqueta **informada** y no representa resultado contable definitivo. Los movimientos de fondos se informan separados y no se consideran pérdidas comerciales.

## Privacidad

Los archivos se reciben como bytes y se procesan únicamente en memoria durante la sesión de Streamlit. La aplicación no guarda archivos cargados ni resultados en disco o base de datos.

No deben incorporarse archivos reales de Mercado Libre, Mercado Pago, bancos u otras fuentes sensibles al repositorio. Los directorios `data/raw/`, `data/uploads/` y `private_data/` están excluidos para evitar cargas accidentales de datos privados.

La tabla y el detalle de interfaz evitan datos personales, documentos, tarjetas, JSON original y contenido crudo de filas financieras.

### Limpieza de sesión

La interfaz incluye el botón **Limpiar archivos y resultados**. Ese botón elimina del estado de sesión mantenido por la aplicación los archivos cargados, hashes, normalizaciones, cobertura temporal, reporte de conciliación, firma de procesamiento, filtros y selección de detalle.

Los archivos se transmiten al servidor privado de la aplicación para procesarse. La aplicación no los persiste en disco ni base de datos. Los datos normalizados y resultados permanecen únicamente en memoria de sesión, y la limpieza borra ese estado de aplicación para la sesión actual sin prometer controles de infraestructura ajenos a la app.

## Utilidad informada

La **utilidad informada por Mercado Libre** se muestra únicamente como valor provisto por la fuente comercial. No representa ganancia definitiva, resultado contable, resultado operativo definitivo ni métrica fiscal validada.

El sistema no recalcula impuestos, utilidad ni resultado operativo definitivo. Los componentes financieros de Mercado Pago se exhiben como impactos separados para control y revisión.

## Limitaciones actuales

- La conciliación actual sigue usando el CSV de Eccomapp y el XLSX de Mercado Pago; el XLSX oficial de ventas de Mercado Libre ya se detecta y normaliza, pero aún no se cruza con las otras dos fuentes.
- No hay persistencia, historial ni usuarios.
- No hay exportación CSV desde la interfaz.
- No hay gráficos avanzados ni integraciones por API.
- No hay cálculo contable definitivo.
- Tienda Nube, bancos y local físico quedan fuera de esta etapa.

## Uso básico del inspector

```python
from kiki_control.ingestion.file_inspector import inspeccionar_archivo

resultado = inspeccionar_archivo("archivo.csv", contenido_en_bytes)
```

El inspector no guarda archivos en disco y no expone contenidos financieros en mensajes de error.

## Uso mínimo de normalización del CSV de Eccomapp

La API histórica conserva el nombre `normalizar_mercado_libre` por compatibilidad, pero el CSV corresponde a `ECCOMAPP_RENTABILIDAD`: fuente de costos y rentabilidad informada/procesada.

## Uso mínimo de normalización del CSV histórico

```python
from kiki_control.adapters.mercado_libre import normalizar_mercado_libre

resultado = normalizar_mercado_libre(
    nombre_archivo="ventas.csv",
    contenido=contenido_csv_en_bytes,
)

for operacion in resultado.operaciones:
    print(operacion.id_orden, operacion.utilidad_neta_informada)
```


## Uso mínimo de normalización de ventas oficiales de Mercado Libre

```python
from kiki_control.adapters.mercado_libre_ventas import normalizar_ventas_mercado_libre

resultado = normalizar_ventas_mercado_libre(
    nombre_archivo="ventas-oficiales.xlsx",
    contenido=contenido_xlsx_en_bytes,
)

for venta in resultado.ventas:
    print(venta.id_venta, venta.total_informado_ml)
```

El normalizador procesa XLSX en memoria, localiza el encabezado que contiene `# de venta` aunque no esté en la primera fila, conserva hoja, hash, columnas originales y fila de origen, mantiene IDs como texto e importes como `Decimal`, y no expone datos personales. Reconoce el contrato confirmado de 64 columnas, incluidos encabezados repetidos que se desambiguan por posición (`Unidades`, `Unidades.1`, `Unidades.2`, `Forma de entrega`, `Forma de entrega.1`, etc.) antes de normalizar. Usa los encabezados externos exactos `Cargo por venta e impuestos (ARS)`, `Costo de envío basado en medidas y peso declarados`, `Cargo por diferencias en medidas y peso del paquete`, `Anulaciones y reembolsos (ARS)`, `Precio unitario de venta de la publicación (ARS)`, `Reclamo abierto`, `Reclamo cerrado` y `Con mediación`. No reconstruye `Total (ARS)`, no elimina ventas canceladas/devueltas/total cero ni calcula utilidad.

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

## Capa explicativa de resultados

La interfaz de Streamlit incluye una capa explicativa orientada a usuarias no técnicas. No cambia el motor de conciliación ni las reglas financieras: centraliza textos y definiciones en un módulo puro de presentación para que los tests verifiquen la trazabilidad y los límites.

### Qué agrega

- Tooltips en métricas de cobertura temporal y resumen ejecutivo.
- Tooltips en todas las columnas visibles de la tabla principal.
- Expander **Cómo se calculan los resultados** con guía general y diccionario de estados.
- Expander **Cómo se calculó esta operación** dentro del detalle de operación, con una tabla de pasos calculados desde modelos normalizados.

### Columnas documentadas

La guía y los tooltips citan las columnas externas necesarias para explicar el cálculo:

- Mercado Libre: `ID Order`, `Sku`, `Monto neto (en MP) ($)`, `Utilidades netas ($)`, `Fecha de venta` y `Hora`.
- Mercado Pago: `ID DE LA ORDEN`, `CÓDIGO DE PRODUCTO SKU`, `TIPO DE OPERACIÓN`, `MONTO NETO DE LA OPERACIÓN QUE IMPACTÓ TU DINERO`, `FECHA DE ORIGEN` y `FECHA DE LIQUIDACIÓN DEL DINERO`.

### Límites

- El ID de orden es la clave primaria; el SKU es validación secundaria.
- El neto aprobado MP suma solo movimientos normalizados como `PAGO_APROBADO`.
- El neto financiero total suma todos los movimientos MP asociados y puede diferir del neto aprobado MP.
- La utilidad ML se toma exclusivamente de `Utilidades netas ($)` y no se recalcula.
- La app no recorta automáticamente el XLSX si la cobertura temporal no coincide.
- Los `PAYOUT` sin orden se informan como movimientos de fondos, no como pérdidas comerciales.
- La explicación no debe mostrar datos personales, columnas sensibles de pagador o tarjeta, hashes completos ni contenido crudo de datos extra.

## Revisiones pendientes

La interfaz de Streamlit incluye una sección **Revisiones pendientes** para desagregar el KPI **Requieren revisión**. La clasificación vive en `src/kiki_control/presentation/review_cases.py` y es una transformación pura de presentación: no importa Streamlit, pandas ni openpyxl, y no modifica el motor de conciliación.

Categorías implementadas:

- Pago o movimiento MP sin ID de orden.
- Orden MP sin venta en el archivo ML.
- Venta ML sin movimiento MP.
- Reclamo o disputa.
- Movimiento desconocido o en revisión.
- Duplicación comercial.
- Duplicación financiera.
- Otra revisión.

Cada caso muestra motivo, acción recomendada, columnas utilizadas y filas de origen. También puede exportarse con **Descargar revisiones pendientes**, que genera un XLSX en memoria con hojas **Resumen** y **Revisiones pendientes**, solo con resultados `requiere_revision=True` y con las protecciones de exportación segura existentes: IDs como texto, importes `Decimal`, prevención de fórmulas y ausencia de PII.
