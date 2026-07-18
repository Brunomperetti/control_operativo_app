# Control Operativo App

Aplicación profesional en Streamlit para conciliación financiera, análisis de rentabilidad y control operativo.

> La documentación oficial y completa del proyecto se encuentra en [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md).

---

## Descripción

Este repositorio será la base de una plataforma escalable de control financiero. La primera etapa funcional estará orientada a conciliar información entre Mercado Libre y Mercado Pago, pero el diseño del sistema contempla la incorporación futura de Tienda Nube, bancos, ventas del local, dashboards financieros, KPIs, reportes, base histórica y automatizaciones.

El proyecto no debe entenderse como una herramienta para cruzar dos archivos Excel, sino como una plataforma profesional para centralizar, validar, conciliar y analizar información financiera de múltiples fuentes.

---

## Objetivo

Construir una aplicación mantenible y extensible que permita:

- Conciliar operaciones comerciales con movimientos financieros.
- Identificar diferencias, pendientes, duplicados y movimientos no reconocidos.
- Analizar rentabilidad por operación, canal, producto y período.
- Generar reportes y dashboards para toma de decisiones.
- Mantener trazabilidad entre datos originales, transformaciones y resultados.

---

## Tecnologías previstas

| Tecnología | Uso previsto |
|---|---|
| Python | Lenguaje principal de desarrollo. |
| Streamlit | Interfaz web y dashboards internos. |
| Pandas | Procesamiento tabular inicial. |
| SQLite | Persistencia local posible en etapas tempranas. |
| PostgreSQL | Persistencia robusta futura. |
| Pytest | Pruebas automatizadas futuras. |

Las dependencias todavía no deben instalarse. Este repositorio se encuentra en etapa documental.

---

## Estructura prevista

La estructura técnica todavía no debe crearse. La organización conceptual futura será:

```text
control_operativo_app/
├── app/                  # Aplicación Streamlit futura
├── src/                  # Lógica de negocio y módulos principales
├── tests/                # Pruebas automatizadas futuras
├── docs/                 # Documentación complementaria futura
├── DOCUMENTO_MAESTRO.md  # Especificación oficial
├── README.md             # Guía resumida para desarrolladores
└── AI_CONTEXT.md         # Contexto para asistentes de IA
```

---

## Cómo ejecutar la aplicación

La aplicación todavía no existe. En esta etapa no hay código Python, pantallas, dependencias ni comandos de ejecución.

Cuando comience la implementación, esta sección deberá documentar:

1. Requisitos del entorno.
2. Instalación de dependencias.
3. Variables de configuración.
4. Comando para ejecutar Streamlit.
5. Procedimiento de carga inicial de datos.

---

## Roadmap resumido

| Versión | Objetivo |
|---|---|
| 0.0 | Documentación fundacional del proyecto. |
| 0.1 | Prototipo controlado Mercado Libre / Mercado Pago. |
| 0.2 | Motor de conciliación robusto y trazable. |
| 0.3 | Análisis de rentabilidad por operación. |
| 0.4 | Persistencia histórica. |
| 0.5 | Dashboard financiero y KPIs. |
| 1.0 | Plataforma operativa estable. |

---

## Documentación principal

Antes de implementar cualquier funcionalidad, leer:

- [`DOCUMENTO_MAESTRO.md`](DOCUMENTO_MAESTRO.md): especificación oficial del proyecto.
- [`AI_CONTEXT.md`](AI_CONTEXT.md): contexto operativo para asistentes de IA y futuros colaboradores.
