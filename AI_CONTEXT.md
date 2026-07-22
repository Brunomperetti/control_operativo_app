# AI Context

Este documento está escrito específicamente para que una IA pueda comprender el proyecto rápidamente antes de proponer o escribir código.

---

## Resumen del proyecto

El repositorio corresponde a una futura aplicación profesional en Streamlit para conciliación financiera, análisis de rentabilidad y control operativo.

La versión 0.1 queda aprobada para implementación incremental después de la actualización documental inicial. La primera funcionalidad será conciliar información entre Mercado Libre y Mercado Pago. Sin embargo, el objetivo real es construir una plataforma escalable de control financiero capaz de incorporar múltiples fuentes como Tienda Nube, bancos, ventas del local, reportes, dashboards, KPIs, base histórica y automatizaciones.

No es una aplicación simple para cruzar dos Excel. Debe tratarse como una plataforma financiera modular, auditable y mantenible.

---

## Objetivo principal

Construir progresivamente una herramienta que permita:

- Centralizar datos comerciales y financieros.
- Normalizar información proveniente de distintas fuentes.
- Conciliar ventas, cobros, comisiones, impuestos y acreditaciones.
- Detectar diferencias, pendientes, duplicados y movimientos no identificados.
- Analizar rentabilidad por operación, producto, canal y período.
- Generar dashboards y reportes confiables.
- Mantener trazabilidad completa entre dato original, transformación y resultado.

---

## Decisiones arquitectónicas ya tomadas

- La interfaz futura será desarrollada con Streamlit.
- Python será el lenguaje principal.
- La arquitectura debe organizarse por capas.
- La lógica de negocio no debe mezclarse con la interfaz.
- El dominio interno no debe depender directamente de columnas o formatos externos.
- Cada fuente debe integrarse mediante adaptadores o módulos independientes.
- Mercado Libre y Mercado Pago son las fuentes iniciales.
- Tienda Nube, bancos y ventas del local deben contemplarse como extensiones futuras.
- La trazabilidad y auditabilidad son requisitos centrales.
- La documentación precede a la implementación; desde esta actualización, la implementación de la versión 0.1 queda habilitada para tareas posteriores.

---

## Filosofía de desarrollo

Toda IA o persona que continúe el desarrollo debe priorizar:

1. Claridad financiera.
2. Arquitectura simple pero extensible.
3. Separación de responsabilidades.
4. Trazabilidad de datos.
5. Reglas explícitas y documentadas.
6. Evolución incremental.
7. Pruebas para reglas críticas cuando exista código.
8. Mantenibilidad por encima de soluciones rápidas.

No se deben introducir atajos que comprometan la evolución futura del sistema.

---

## Módulos previstos

Los módulos futuros esperados son:

| Módulo | Responsabilidad |
|---|---|
| Ingesta | Recibir archivos, APIs o datos externos. |
| Adaptadores | Traducir formatos de cada fuente al modelo interno. |
| Normalización | Estandarizar nombres, tipos, fechas, importes y estados. |
| Validación | Detectar faltantes, duplicados, inconsistencias y errores. |
| Conciliación | Relacionar operaciones comerciales con movimientos financieros. |
| Análisis | Calcular rentabilidad, costos, impuestos, comisiones y KPIs. |
| Persistencia | Guardar datos originales, normalizados, conciliados e históricos. |
| Exportaciones | Generar reportes y archivos controlados. |
| Interfaz | Presentar carga, filtros, resultados, dashboards y alertas. |

---

## Funcionalidades futuras

- Carga de archivos de Mercado Libre.
- Carga de archivos de Mercado Pago.
- Validación de estructuras de datos.
- Normalización de operaciones y movimientos.
- Conciliación por identificadores, fechas, importes y reglas de agrupación.
- Estados de conciliación.
- Manejo de diferencias y tolerancias.
- Rentabilidad por operación.
- Configuración de IVA.
- Reportes exportables.
- Dashboard financiero.
- KPIs comerciales, financieros y operativos.
- Base histórica.
- Integración con Tienda Nube.
- Integración con bancos.
- Incorporación de ventas del local.
- Automatizaciones de carga y control.

---

## Restricciones actuales

La etapa puramente fundacional terminó con la aprobación documental de la versión 0.1. A partir de tareas posteriores, se podrá implementar incrementalmente el alcance Mercado Libre / Mercado Pago siempre que cada cambio respete `DOCUMENTO_MAESTRO.md`.

Durante esta actualización documental específica estuvo prohibido, y no debe hacerse salvo tarea futura explícita:

- Crear código Python.
- Crear `app.py`.
- Crear archivos de dependencias.
- Instalar paquetes.
- Crear pantallas de Streamlit.
- Implementar lógica de conciliación.
- Crear estructura de carpetas técnica.
- Crear tests.
- Conectar APIs.
- Generar automatizaciones.
- Incorporar archivos reales financieros, comerciales o con datos personales al repositorio.

---

## Cosas que nunca deben romperse

- La documentación oficial debe seguir siendo la fuente principal de verdad.
- La lógica financiera debe ser auditable.
- Los datos originales no deben perderse ni sobrescribirse de forma destructiva.
- Las reglas de conciliación deben ser explícitas.
- El modelo interno debe permanecer independiente de cada proveedor externo.
- La interfaz no debe contener lógica financiera crítica.
- Las diferencias financieras no deben ocultarse.
- Los estados ambiguos deben quedar como pendientes o en revisión, no forzarse como conciliados.
- Los cálculos fiscales deben ser configurables y validados por responsables contables.
- No se deben inventar reglas fiscales ni fórmulas de resultado operativo definitivo.
- Las conciliaciones no deben forzarse cuando falte contraparte o exista ambigüedad.

---

## Forma esperada de trabajar

Antes de cada tarea, y especialmente antes de escribir código, cualquier IA debe:

1. Leer `DOCUMENTO_MAESTRO.md` completo.
2. Leer este archivo completo.
3. Verificar el estado actual del repositorio.
4. Confirmar que la tarea solicitada no contradiga restricciones existentes.
5. Modificar solo los archivos necesarios.
6. Mantener documentación sincronizada con cambios técnicos o funcionales.
7. Evitar crear estructuras o dependencias no solicitadas.
8. Proponer cambios incrementales y revisables.
9. Confirmar que no se incorporen al repositorio archivos reales de Mercado Libre, Mercado Pago, bancos u otras fuentes sensibles.

Durante el desarrollo futuro:

- Cada Pull Request debe tener un objetivo claro.
- Las modificaciones deben ser pequeñas y coherentes.
- Las reglas financieras nuevas deben documentarse.
- Los cambios de arquitectura deben justificarse.
- Las pruebas deben cubrir reglas críticas cuando exista código.
- No deben mezclarse refactors amplios con funcionalidades nuevas sin necesidad.

---

## Estándares para futuros Pull Requests

Cada PR futuro debería incluir:

- Resumen de cambios.
- Archivos modificados.
- Motivación funcional o técnica.
- Impacto en arquitectura.
- Impacto en documentación.
- Pruebas ejecutadas o motivo por el cual no aplican.
- Riesgos o limitaciones conocidas.
- Próximos pasos recomendados.

Si el PR agrega o modifica reglas de conciliación, también debe incluir:

- Descripción de la regla.
- Fuente de datos afectada.
- Campos utilizados.
- Estados posibles.
- Ejemplos de casos esperados.
- Criterios para diferencias o tolerancias.

---

## Cómo debe comportarse una IA que continúe el desarrollo

Una IA que continúe este proyecto debe actuar como asistente de ingeniería de software profesional, no como generador rápido de scripts.

Debe:

- Respetar el alcance exacto pedido por el usuario.
- No implementar funcionalidades no solicitadas.
- No instalar dependencias sin autorización explícita.
- No crear archivos innecesarios.
- No asumir reglas financieras sin documentarlas.
- Preguntar o dejar explícitos los supuestos cuando falte información crítica.
- Preferir diseños simples, testeables y extensibles.
- Mantener lenguaje, nombres y documentación en español salvo instrucción contraria.
- Actualizar `DOCUMENTO_MAESTRO.md` cuando cambie la visión, arquitectura o reglas oficiales.
- Mantener este archivo actualizado si cambian las instrucciones relevantes para IA.

---

## Referencia obligatoria

La especificación oficial del proyecto está en `DOCUMENTO_MAESTRO.md`. Este archivo resume el contexto para IA, pero no reemplaza el documento maestro.

## Actualización: tres fuentes iniciales diferenciadas

Antes de modificar reglas futuras, considerar esta separación como oficial:

1. `MERCADO_LIBRE_VENTAS`: reporte XLSX oficial descargado de Mercado Libre. Es la fuente comercial oficial de ventas, estados, unidades e importes informados por Mercado Libre.
2. `ECCOMAPP_RENTABILIDAD`: CSV previamente tratado como Mercado Libre. Queda confirmado que proviene de Eccomapp, sistema de facturación, stock y costos; su rol es fuente de costos y rentabilidad informada/procesada.
3. `MERCADO_PAGO`: XLSX financiero de cobros, liquidaciones, comisiones, impuestos, retenciones, devoluciones, reclamos y movimientos de dinero.

La API histórica `normalizar_mercado_libre` se conserva por compatibilidad para el CSV de Eccomapp, pero las implementaciones nuevas deben nombrar explícitamente `ECCOMAPP_RENTABILIDAD` cuando hablen de ese archivo. El reporte comercial oficial nuevo se normaliza con `normalizar_ventas_mercado_libre(nombre_archivo, contenido, zona_horaria=...)` y no depende del nombre del archivo.

Esta actualización solo incorpora detección estructural y normalización segura del XLSX oficial de ventas de Mercado Libre. No modifica el motor de conciliación, la UI, las exportaciones ni las fórmulas financieras; no cruza todavía las tres fuentes; no calcula utilidad; y cualquier utilidad o resultado definitivo permanece pendiente de validación contable.

El modelo público `VentaOficialMercadoLibre` debe permanecer inmutable y sin datos personales. No puede exponer comprador, documentos, DNI, domicilio, ciudad, código postal, país, datos fiscales personales, condición fiscal, número IIBB, negocio, URLs, números de seguimiento ni datos de empresa/persona no necesarios para conciliación. Los tests deben seguir usando datos sintéticos generados en memoria y nunca archivos reales.

El XLSX oficial confirmado tiene 64 columnas y encabezados repetidos. La frontera de entrada debe conservar los encabezados externos exactos, entre ellos `Cargo por venta e impuestos (ARS)`, `Costo de envío basado en medidas y peso declarados`, `Cargo por diferencias en medidas y peso del paquete`, `Anulaciones y reembolsos (ARS)`, `Precio unitario de venta de la publicación (ARS)`, `Reclamo abierto`, `Reclamo cerrado` y `Con mediación`. Antes de armar filas normalizables, los duplicados deben resolverse de manera estable por posición (`Unidades`, `Unidades.1`, `Unidades.2`, etc.) para no sobrescribir valores. Las celdas opcionales vacías pueden ser `None`, pero valores no vacíos inválidos deben generar `ProblemaValidacion` con columna y fila sin filtrar contenido sensible en mensajes.

## Actualización: motor de vinculación comercial ML oficial / Eccomapp

Existe un motor puro de dominio para vincular `VentaOficialMercadoLibre` con `OperacionComercial` antes de cualquier cruce financiero. La API pública es `vincular_ventas_oficiales_con_eccomapp(ventas_oficiales, operaciones_eccomapp)` y devuelve un `ReporteVinculacionComercial` inmutable.

Regla canónica: en Eccomapp, el grupo comercial es `id_carrito` cuando existe y `id_orden` cuando el carrito está vacío. `id_orden` identifica cada operación individual; `id_carrito` agrupa operaciones. El `# de venta` oficial puede ser cabecera de carrito, orden individual, detalle dentro de carrito o venta sin contraparte.

La vinculación solo usa identificadores: ID Carrito e ID Order. SKU es validación secundaria agregada por grupo y nunca clave primaria. `COINCIDE` exige igualdad exacta entre conjuntos no vacíos; cualquier diferencia entre conjuntos no vacíos es `DIFIERE`. No se deben usar fechas, producto ni importes para forzar coincidencias. Los casos ambiguos, IDs duplicados o IDs asociados a más de un carrito deben quedar en revisión sin elección automática.

El reporte debe conservar una partición exacta de registros: cada venta oficial `(hash_importacion, fila_origen)` y cada operación Eccomapp `(hash_importacion, numero_fila_origen)` aparece exactamente una vez, sin omisiones ni repeticiones, aunque existan conflictos. Las ventas `SOLO_MERCADO_LIBRE` activas, entregadas o con importe no cero requieren revisión; las claramente canceladas/devueltas/reembolsadas con total cero pueden quedar sin revisión manual.

Estados creados: `VINCULADA`, `VINCULADA_CON_OBSERVACIONES`, `SOLO_MERCADO_LIBRE`, `SOLO_ECCOMAPP`, `AMBIGUA` y `DUPLICADA`. Métodos: `ID_CARRITO`, `ID_ORDER`, `ID_ORDER_DENTRO_DE_CARRITO` y `SIN_VINCULO`. SKU: `COINCIDE`, `NO_DISPONIBLE_EN_AMBAS`, `FALTA_EN_MERCADO_LIBRE`, `FALTA_EN_ECCOMAPP` y `DIFIERE`.

Esta etapa no incorpora Mercado Pago, no modifica el motor de conciliación financiera, no recalcula utilidad, no cambia Streamlit, no cambia exportaciones y no altera fórmulas. Los tests deben ser sintéticos, sin archivos reales ni datos personales.

## Actualización: motor consolidado de control financiero de tres fuentes

Existe una API pública pura de dominio: `consolidar_control_financiero(reporte_comercial: ReporteVinculacionComercial, reporte_financiero: ReporteConciliacion) -> ReporteControlConsolidado`. Reutiliza la vinculación comercial ML oficial / Eccomapp y el reporte de conciliación Mercado Pago; no lee archivos, no usa DataFrames y no depende de Streamlit, pandas ni openpyxl.

Jerarquía oficial: Mercado Libre oficial es fuente primaria de importes de venta, cargos, envíos, descuentos, anulaciones y `Total (ARS)`; Eccomapp es fuente primaria de costo de productos y conserva sus importes informados como diagnóstico; Mercado Pago es fuente financiera para neto aprobado MP, neto financiero total, impactos e indicadores. El `Total (ARS)` de Mercado Libre nunca se reconstruye ni se reemplaza por fórmulas propias.

La unión con Mercado Pago es exclusivamente por `id_orden`. No se debe unir por fecha, importe, SKU, producto ni aproximación. Si un ID Order es ambiguo entre resultados comerciales, el resultado financiero queda separado y en revisión. Los movimientos sin orden y PAYOUT se conservan como movimientos financieros independientes; PAYOUT sin orden se clasifica como movimiento de fondos, no como pérdida de una venta.

Fórmulas permitidas con `Decimal`: diferencia de venta ML vs Eccomapp, diferencia de neto ML vs Eccomapp, diferencia ML vs MP (`neto_aprobado_mp - total_informado_ml`) y utilidad preliminar de control (`total_informado_ml - costo_productos_eccomapp`). Esta última no es utilidad contable, ganancia definitiva ni resultado fiscal. No calcular IVA, IIBB, retenciones, percepciones ni reglas fiscales propias.

Estados consolidados por prioridad: `DUPLICADA_O_AMBIGUA`, `SOLO_MOVIMIENTO_FINANCIERO`, `SIN_VENTA_OFICIAL`, `SIN_COSTO_PRODUCTO`, `SIN_MOVIMIENTO_FINANCIERO`, `EN_REVISION_FINANCIERA`, `CON_DIFERENCIA`, `COMPLETA`. Un resultado completo puede requerir revisión por SKU, devolución, reclamo, duplicado, liquidación pendiente u otra condición heredada.

El reporte consolidado valida compatibilidad de hashes Eccomapp con hashes comerciales del reporte financiero y garantiza partición exacta: cada resultado comercial y cada resultado financiero de entrada aparece exactamente una vez. Esta etapa no modifica Streamlit, carga visual de tres archivos, presentación, exportaciones Excel, normalizadores, persistencia ni el motor histórico de conciliación.

### Corrección: ResultadoConciliacion y presencia real de Mercado Pago

No asumir que la existencia de un `ResultadoConciliacion` implica presencia de Mercado Pago. La evidencia de movimiento financiero real es `cantidad_movimientos_financieros > 0`. Un resultado `OPERACION_SIN_MOVIMIENTO_FINANCIERO` debe conservarse en la partición, pero no aporta importes MP, impactos ni indicadores, y `tiene_mercado_pago` debe ser `False`. Un movimiento real con neto cero sí es Mercado Pago presente y debe conservar `Decimal("0")`.

Para unir Mercado Pago con grupos comerciales, usar `ResultadoVinculacionComercial.ids_orden` cuando existan. Si el resultado comercial es `SOLO_MERCADO_LIBRE` y contiene exactamente una venta oficial no ambigua, se puede usar `venta.id_venta` como candidato de ID Order para vincular MP aunque falte Eccomapp. No hacer esto para `AMBIGUA` o `DUPLICADA`, ni agregar cabeceras de carrito como ID Order cuando existen órdenes internas.

La compatibilidad de hashes Eccomapp entre reporte comercial y reporte financiero es igualdad exacta de conjuntos. Ambos vacíos es válido si no existe Eccomapp; subconjuntos, diferencias o vacío contra no vacío son errores de dominio.

## Actualización: Streamlit consolida tres fuentes

La interfaz Streamlit ahora carga tres archivos separados: ventas oficiales de Mercado Libre (`archivo_ml_oficial`), costos/rentabilidad de Eccomapp (`archivo_eccomapp`) y movimientos de Mercado Pago (`archivo_mp`). Cada carga se inspecciona en memoria y debe coincidir con su `TipoFuente` esperado. No se deben guardar bytes originales en sesión después del procesamiento.

El procesamiento obligatorio en UI reutiliza exclusivamente estas APIs: `normalizar_ventas_mercado_libre`, `normalizar_mercado_libre` para Eccomapp, `normalizar_mercado_pago`, `vincular_ventas_oficiales_con_eccomapp`, `reconciliar` y `consolidar_control_financiero`. Streamlit no debe reconstruir reglas financieras ni incorporar fórmulas críticas; las transformaciones de presentación viven en `src/kiki_control/presentation/control_consolidado_view.py` y son puras.

La vista muestra cobertura temporal de ML oficial, Eccomapp, origen MP y liquidaciones MP; resumen ejecutivo; KPIs con universos comparables; tabla “Control consolidado por operación”; detalle seguro; explicación prudente; y trazabilidad técnica limitada. La utilidad se denomina siempre “utilidad preliminar de control” y no debe presentarse como ganancia definitiva, resultado contable ni fiscal.

La auditoría financiera anterior Eccomapp–Mercado Pago permanece en un expander secundario con sus descargas Excel existentes. Todavía no existe exportación Excel del resultado consolidado.
