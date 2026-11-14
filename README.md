# Finanzas AI — Dashboard Analítico Multimodal & Control de Compromisos

Aplicación web full-stack de finanzas personales potenciada con **Inteligencia Artificial (Google Gemini)** y sincronizada en tiempo real con **Google Sheets** como base de datos en la nube[cite: 4, 5].

Permite registrar ingresos, egresos, deudas a cuotas y pagos recurrentes mediante **lenguaje natural, notas de voz o fotografías de facturas y comprobantes**[cite: 2, 4, 5].

---

## Características Principales

- **Registro Rápido con IA (Multimodal):**
  - **Texto natural:** Escribe frases como *"Gasté 25 mil en almuerzo"* o *"Me pagaron el sueldo 3m"* y la IA clasifica automáticamente tipo, categoría, concepto y monto[cite: 2, 5].
  - **Dictado por voz:** Grabación de notas de voz directamente desde el navegador para registrar gastos o compromisos sin escribir[cite: 4, 5].
  - **Lectura de facturas y comprobantes (OCR + Visión):** Toma fotos de recibos físicos o sube capturas de transferencias (Nequi, Bancolombia, etc.) para extraer el comercio y valor total automáticamente[cite: 2, 5].
- **Gestión de Deudas y Pagos Recurrentes:**
  - Control de suscripciones mensuales fijas y deudas a cuotas con barra de progreso y cálculo de saldo restante[cite: 3, 5].
  - Botones de **Pagar cuota** (registra el gasto del mes y avanza el contador) y **Liquidar saldo** (salda la deuda completa en un clic)[cite: 3, 5].
- **Dashboard Analítico Interactivo:**
  - Filtros dinámicos por mes, año, tipo de movimiento (Todos / Egresos / Ingresos) y categoría[cite: 5].
  - Comparativa de **Presupuesto vs. Real** y gráficas interactivas (distribución porcentual, barras comparativas y balance por categoría)[cite: 5].
- **CRUD Completo:** Edición y eliminación sincronizada tanto de movimientos históricos como de compromisos activos[cite: 3, 4, 5].

---

##  Stack Tecnológico

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic[cite: 4].
- **Inteligencia Artificial:** Google GenAI SDK (`gemini-3.5-flash-lite` con respaldo automático a `gemini-3.8-flash`)[cite: 2, 12].
- **Base de Datos:** Google Sheets API & Google Drive API (`gspread`, `google-auth`)[cite: 3].
- **Frontend:** HTML5, Tailwind CSS, JavaScript Vanilla (MediaRecorder API & Canvas image compression), Chart.js[cite: 5].

---

## Estructura del Proyecto

```text
Finanzas AI/
├── app/
│   ├── core/
│   │   └── config.py           # Configuración y carga de variables de entorno
│   ├── services/
│   │   ├── llm_factory.py      # Integración multimodal con Google Gemini y fallback
│   │   └── sheets_client.py    # Operaciones CRUD con Google Sheets
│   ├── static/
│   │   └── index.html          # Interfaz web y lógica del dashboard
│   └── main.py                 # Endpoints de la API FastAPI
├── .env                        # Variables de entorno (no incluir en Git)
├── credentials.json            # Credenciales Service Account de Google (no incluir en Git)
├── requirements.txt            # Dependencias de Python
└── README.md
```