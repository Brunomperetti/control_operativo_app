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

El normalizador procesa XLSX en memoria, localiza el encabezado que contiene `# de venta` aunque no esté en la primera fila, conserva hoja, hash, columnas originales y fila de origen, mantiene IDs como texto e importes como `Decimal`, y no expone datos personales. Reconoce el contrato confirmado de 64 columnas, incluidos encabezados repetidos que se desambiguan por posición (`Unidades`, `Unidades.1`, `Unidades.2`, `Forma de entrega`, `Forma de entrega.1`, etc.) antes de normalizar. Usa los encabezados externos exactos `Cargo por venta e impuestos (ARS)`, `Costo de envío basado en medidas y peso declarados`, `Cargo por diferencias en medidas y peso del paquete`, `Anulaciones y reembolsos (ARS)`, `Precio unitario de venta de la publicación (ARS)`, `Reclamo abierto`, `Reclamo cerrado` y `Con mediación`. Reconoce las fechas de `Fecha de venta` como datetime de Excel, formatos numéricos existentes (`YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD`, `DD/MM/YYYY HH:MM:SS`, `DD/MM/YYYY`), valores ISO compatibles con `datetime.fromisoformat` y el formato textual oficial confirmado, por ejemplo `20 de julio de 2026 20:29 hs.`. El formato textual se interpreta de forma determinística en la zona operativa `America/Argentina/Cordoba`, acepta día y hora de uno o dos dígitos, segundos opcionales, `hs` con punto opcional, mayúsculas/minúsculas y los meses `septiembre` y `setiembre` como equivalentes. No reconstruye `Total (ARS)`, no elimina ventas canceladas/devueltas/total cero ni calcula utilidad.

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

## Vinculación comercial Mercado Libre oficial / Eccomapp

La API pública para resolver identidad comercial entre el XLSX oficial de Mercado Libre y el CSV normalizado de Eccomapp es:

```python
from kiki_control.linking import vincular_ventas_oficiales_con_eccomapp

reporte = vincular_ventas_oficiales_con_eccomapp(
    ventas_oficiales=[venta_oficial_normalizada],
    operaciones_eccomapp=[operacion_eccomapp_normalizada],
)
```

La función es pura: no lee archivos, no usa pandas, no depende de Streamlit ni Mercado Pago, no muta entradas y devuelve dataclasses inmutables con colecciones públicas `tuple`.

Ejemplo sintético mínimo:

```python
reporte = vincular_ventas_oficiales_con_eccomapp(
    ventas_oficiales=[venta_ml_con_id_venta_igual_a_id_order],
    operaciones_eccomapp=[operacion_sin_carrito_con_mismo_id_order],
)
resultado = reporte.resultados[0]
assert resultado.estado.value == "VINCULADA"
assert resultado.metodos_vinculacion[0].value == "ID_ORDER"
```

Reglas principales:

- En Eccomapp, `id_grupo_canonico` es `id_carrito` cuando existe y `id_orden` cuando no existe carrito.
- `# de venta` del XLSX oficial puede ser cabecera de carrito, venta individual, detalle interno de carrito o venta sin contraparte.
- La vinculación se realiza por ID Carrito o ID Order; no se usan fechas, producto ni importes para forzar coincidencias.
- SKU se valida de manera secundaria por conjunto agregado de cabecera y detalles, pero nunca define la clave primaria; `COINCIDE` requiere igualdad exacta de conjuntos no vacíos.
- Cada venta oficial y cada operación Eccomapp aparece exactamente una vez en el reporte usando sus identidades de trazabilidad, incluso ante duplicados o ambigüedades.
- Los estados sin contraparte son prudentes: una venta solo Mercado Libre activa o con importe no cero requiere revisión porque puede faltar el costo de producto; una cancelada/devuelta/reembolsada con total cero puede quedar sin revisión manual; un grupo solo Eccomapp requiere revisión.

Limitaciones actuales:

- Este motor todavía no incorpora Mercado Pago.
- No calcula utilidad, resultado operativo, comisiones, impuestos, envío ni netos financieros.
- No modifica la conciliación financiera existente ni las exportaciones.
- La UI todavía utiliza el flujo de archivos existente y no expone esta vinculación comercial como pantalla nueva.

## Motor consolidado de control financiero de tres fuentes

La API pública `consolidar_control_financiero(reporte_comercial, reporte_financiero)` genera un `ReporteControlConsolidado` inmutable a partir de:

1. `ReporteVinculacionComercial`, producido por `vincular_ventas_oficiales_con_eccomapp(...)` entre Mercado Libre oficial y Eccomapp.
2. `ReporteConciliacion`, producido por el motor de conciliación Mercado Pago existente.

El motor es puro: trabaja con dataclasses en memoria, no lee archivos, no usa DataFrames y no depende de Streamlit, pandas ni openpyxl. En esta etapa no hay UI, exportación Excel ni persistencia para el consolidado.

### Responsabilidad de fuentes

- **Mercado Libre oficial**: fuente primaria de monto de venta (`Ingresos por productos (ARS)`), cargo por venta e impuestos, ingresos y costos de envío, descuentos, anulaciones y `Total (ARS)`. El `Total (ARS)` se conserva como informado y no se reconstruye.
- **Eccomapp**: fuente primaria de costo de productos por suma de `costo_total_con_iva`. También conserva como diagnóstico `monto_venta`, `costo_envio_vendedor`, `monto_neto_mercado_pago_informado` y `utilidad_neta_informada`.
- **Mercado Pago**: fuente financiera de neto aprobado MP, neto financiero total, impactos de envíos, devoluciones, reclamos/disputas, otros movimientos e indicadores financieros.

### Fórmulas permitidas

- `diferencia_venta_ml_eccomapp = monto_venta_ml - monto_venta_eccomapp_informado`.
- `diferencia_neto_ml_eccomapp = total_informado_ml - neto_mp_eccomapp_informado`.
- `diferencia_ml_mp = neto_aprobado_mp - total_informado_ml`; positivo significa que MP informa más que ML, negativo significa que informa menos.
- `utilidad_preliminar_control = total_informado_ml - costo_productos_eccomapp`.

Todas las fórmulas usan `Decimal`, solo se calculan cuando existen ambos operandos y no constituyen resultado contable o fiscal definitivo. No se calculan IVA, IIBB, retenciones ni percepciones.

### Unión y estados

La unión con Mercado Pago es solo por `id_orden`; no se usan fecha, importe, SKU, producto ni aproximaciones. Los movimientos sin orden, los financieros sin grupo comercial y los PAYOUT quedan como resultados financieros independientes. La prioridad de estados es: `DUPLICADA_O_AMBIGUA`, `SOLO_MOVIMIENTO_FINANCIERO`, `SIN_VENTA_OFICIAL`, `SIN_COSTO_PRODUCTO`, `SIN_MOVIMIENTO_FINANCIERO`, `EN_REVISION_FINANCIERA`, `CON_DIFERENCIA`, `COMPLETA`.

El reporte valida hashes compatibles entre Eccomapp y conciliación financiera, y garantiza partición exacta: cada resultado comercial y cada resultado financiero de entrada aparece exactamente una vez.

### Presencia real de Mercado Pago

Un `ResultadoConciliacion` puede representar una operación comercial sin movimientos financieros. Por eso `tiene_mercado_pago` se determina con `cantidad_movimientos_financieros > 0`, no por la existencia del resultado ni por el importe. Si todos los resultados asociados tienen cero movimientos, se conservan para partición y trazabilidad, pero los importes e impactos MP quedan en `None` y el estado esperado es `SIN_MOVIMIENTO_FINANCIERO`, salvo prioridades superiores.

Un movimiento real con neto cero sí cuenta como Mercado Pago presente y conserva `Decimal("0")`. Además, una venta `SOLO_MERCADO_LIBRE` con un `id_orden` coincidente puede vincularse con MP aunque falte Eccomapp: se puede comparar ML contra MP, pero el costo de productos y la utilidad preliminar quedan en `None`, por lo que el estado es `SIN_COSTO_PRODUCTO` con revisión.

Los hashes Eccomapp del reporte comercial y del reporte financiero deben coincidir exactamente como conjuntos; cualquier diferencia o subconjunto incompleto cancela el consolidado con un error de dominio en español.

## Control consolidado de tres fuentes en Streamlit

La pantalla principal permite cargar tres reportes sintéticos o exportados manualmente, siempre procesados en memoria:

1. **Ventas oficiales de Mercado Libre** (`.xlsx`): aporta ventas, cargos, envíos y `Total (ARS)` informado por Mercado Libre.
2. **Costos y rentabilidad de Eccomapp** (`.csv`): aporta costo de productos, monto de venta, costo de envío seller, neto informado en MP y utilidad informada por la fuente.
3. **Movimientos de Mercado Pago** (`.xlsx`): aporta pagos, liquidaciones, devoluciones, reclamos y netos financieros.

El botón **Procesar y consolidar** se habilita solo cuando los tres archivos son válidos, la zona horaria existe y la tolerancia monetaria no es negativa. El flujo reutiliza las APIs de dominio existentes de normalización, vinculación comercial, conciliación financiera y consolidación; la UI no duplica reglas financieras.

La vista consolidada incluye:

- **Cobertura de los archivos**, con rango de fechas por fuente y advertencia cuando los períodos no coinciden.
- **Resumen ejecutivo consolidado**, con cantidades de grupos completos, con diferencia, sin venta oficial, sin costo, sin MP, solo financieros, ambiguos y pendientes de revisión.
- **KPIs por bloque**, donde los importes comparables ML–MP solo mezclan resultados que tienen ambas fuentes, y el neto MP sin venta oficial asociada se informa aparte.
- **Utilidad preliminar de control**, calculada solo cuando existe `Total (ARS)` de ML oficial y `Costo Total (Con IVA) ($)` de Eccomapp, acompañada por cobertura “X de Y grupos”.
- **Control consolidado por operación**, con vista predeterminada de pendientes, diferencias y datos faltantes, filtros y detalle seguro.
- **Auditoría de conciliación Eccomapp–Mercado Pago**, separada del nuevo consolidado; las descargas Excel actuales corresponden todavía a esa auditoría histórica.

Privacidad y límites: la app no persiste archivos originales, no muestra datos personales ni contenido crudo, conserva signos negativos y usa lenguaje prudente. Los resultados son controles operativos informados por las fuentes y no constituyen resultado contable o fiscal definitivo. La exportación Excel consolidada todavía no está implementada.

## Diagnóstico auditable del control consolidado

El proyecto incluye una capa pura de diagnóstico para el control consolidado de Mercado Libre oficial, Eccomapp y Mercado Pago: `src/kiki_control/presentation/control_consolidado_diagnostics.py`. Esta capa no depende de Streamlit ni de DataFrames y usa `Decimal` para reconciliar importes.

### Universos e identidades

- **Partición primaria:** `total_resultados` debe ser igual a completos + con diferencia como estado principal + sin venta oficial + sin costo producto + sin movimiento financiero + solo movimiento financiero + en revisión financiera + duplicados o ambiguos.
- **Diferencia real ML–MP:** cuenta grupos comparables donde existen `total_informado_ml` y `neto_aprobado_mp`, y `abs(diferencia_ml_mp)` supera la tolerancia. No depende de `total_con_diferencia`, porque ese campo es un estado principal.
- **Identidad comparable:** `suma_diferencia_ml_mp = suma_neto_mp_comparable - suma_neto_ml_comparable`.
- **Puente de fuentes:** separa venta comercial, neto esperado y puente financiero; valida `MP − ML = (MP − Eccomapp) + (Eccomapp − ML)`.
- **Cobertura de utilidad:** calcula solo cuando existen `total_informado_ml` y `costo_productos_eccomapp`; valida `utilidad_preliminar = neto ML del universo - costo de productos del universo` y separa costo Eccomapp excluido.

La interfaz muestra estados en español, motivos visibles y acciones sugeridas; claves técnicas, hashes y motivos internos quedan restringidos a **Trazabilidad técnica**. Las revisiones consolidadas de tres fuentes se presentan separadas de la auditoría histórica Eccomapp–Mercado Pago, porque sus universos no son comparables directamente.

### Cero, netos MP y temporalidad

En el diagnóstico consolidado, cero es dato válido: `Decimal("0")` no se interpreta como ausencia. Las selecciones entre `neto_financiero_total_mp`, `neto_aprobado_mp` y cero explícito se hacen con `is None` para conservar movimientos financieros de importe cero.

`neto_aprobado_mp` identifica pagos aprobados comparables; `neto_financiero_total_mp` conserva el impacto total de movimientos financieros que pueden ser devoluciones, reclamos, disputas, PAYOUT o movimientos de fondos. Por eso un caso MP sin neto aprobado no se marca automáticamente como dato crítico faltante si tiene neto financiero total válido o indicadores financieros legítimos.

La app muestra la distribución temporal de movimientos MP sin venta oficial en categorías mutuamente excluyentes: anteriores, dentro, posteriores, sin fecha y fechas mixtas. La categoría fechas mixtas evita elegir silenciosamente la primera fecha cuando un grupo incluye movimientos de distintos períodos.

### Organización visual de listas extensas en control consolidado

Para evitar pantallas excesivamente largas sin perder auditabilidad, las listas extensas del diagnóstico consolidado se muestran detrás de expanders cerrados por defecto. El resumen del puente triple permanece siempre visible; la lista completa de grupos excluidos se consulta con la etiqueta dinámica “Ver N grupos excluidos del puente triple”, buscador por grupo, filtro por motivo, conteo “Mostrando X de N grupos” y tabla con scroll interno. Las revisiones consolidadas mantienen una tabla principal resumida con motivo visible, cantidad, importe afectado y acción recomendada; los grupos involucrados se consultan en un expander separado, seleccionando el motivo y viendo una fila por grupo. Esta organización es exclusivamente de presentación: no modifica normalización, vinculación, conciliación, diagnósticos, fórmulas, importes, estados, universos ni exportaciones Excel.

## Organización visual para presentación

La pantalla de resultados del control consolidado se organiza en tres pestañas de Streamlit: **Resumen ejecutivo**, **Control por operación** y **Auditoría y descargas**. El resumen prioriza cobertura temporal compacta, conclusión ejecutiva breve, KPIs agrupados por bloques y un resumen de revisiones sin abrir tablas técnicas extensas por defecto.

La pestaña **Control por operación** concentra filtros, tabla operativa ancha con scroll interno, selector de operación, explicación de resultado y trazabilidad técnica cerrada por defecto. La pestaña **Auditoría y descargas** conserva la auditabilidad completa en expanders cerrados y separa las descargas del control consolidado de tres fuentes del histórico Eccomapp–Mercado Pago.

Las descargas consolidadas usan prefijos `kiki_control_consolidado_3_fuentes_`, `kiki_control_excepciones_consolidadas_` y `kiki_control_revisiones_consolidadas_`. Las descargas históricas usan el prefijo `kiki_control_historico_eccomapp_mp_` y se muestran dentro de la auditoría histórica con la advertencia de que ese informe no es el control consolidado actual de tres fuentes.
