# 💸 Finanzas AI — Dashboard Analítico Multimodal & Control de Compromisos



Aplicación web full-stack de finanzas personales potenciada con **Inteligencia Artificial (Google Gemini)** y sincronizada en tiempo real con **Google Sheets** como base de datos en la nube.



Permite registrar ingresos, egresos, deudas a cuotas y pagos recurrentes mediante **lenguaje natural, notas de voz o fotografías de facturas y comprobantes**.



---



## ✨ Características Principales



- **Registro Rápido con IA (Multimodal):**

  - **Texto natural:** Escribe frases como *"Gasté 25 mil en almuerzo"* o *"Me pagaron el sueldo 3m"* y la IA clasifica automáticamente tipo, categoría, concepto y monto.

  - **Dictado por voz:** Grabación de notas de voz directamente desde el navegador (o dictado por teclado en móvil) para registrar gastos o compromisos sin escribir.

  - **Lectura de facturas y comprobantes (OCR + Visión):** Toma fotos de recibos físicos o sube capturas de transferencias (Nequi, Bancolombia, etc.) para extraer el comercio y valor total automáticamente.

- **Gestión de Deudas y Pagos Recurrentes:**

  - Control de suscripciones mensuales fijas y deudas a cuotas con barra de progreso y cálculo de saldo restante.

  - Botones de **Pagar cuota** (registra el gasto del mes y avanza el contador) y **Liquidar saldo** (salda la deuda completa en un clic).

- **Dashboard Analítico Interactivo:**

  - Filtros dinámicos por mes, año, tipo de movimiento (Todos / Egresos / Ingresos) y categoría.

  - Comparativa de **Presupuesto vs. Real** y gráficas interactivas (distribución porcentual, barras comparativas y balance por categoría).

- **CRUD Completo:** Edición y eliminación sincronizada tanto de movimientos históricos como de compromisos activos.



---



## 🛠️ Stack Tecnológico



- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic.

- **Inteligencia Artificial:** Google GenAI SDK (`gemini-3.5-flash-lite` con respaldo automático a `gemini-3.8-flash`).

- **Base de Datos:** Google Sheets API & Google Drive API (`gspread`, `google-auth`).

- **Frontend:** HTML5, Tailwind CSS, JavaScript Vanilla (MediaRecorder API & Canvas image compression), Chart.js.



---



## 📁 Estructura del Proyecto



```text

Finanzas-AI/

├── app/

│   ├── core/

│   │   └── config.py           # Configuración y carga de variables de entorno

│   ├── services/

│   │   ├── llm_factory.py      # Integración multimodal con Google Gemini y fallback

│   │   └── sheets_client.py    # Operaciones CRUD con Google Sheets

│   ├── static/

│   │   └── index.html          # Interfaz web y lógica del dashboard

│   └── main.py                 # Endpoints de la API FastAPI

├── .env.example                # Plantilla de variables de entorno

├── .gitignore                  # Exclusión de credenciales y archivos temporales

├── requirements.txt            # Dependencias de Python

└── README.md

```



---



## 🔑 Guía de Configuración de Credenciales (Paso a Paso)



Para que la aplicación funcione con tu propia cuenta, necesitas configurar dos servicios gratuitos: la **API Key de Google Gemini** y las **credenciales de Google Sheets**.



### 1. Obtener la API Key de Google Gemini



1. Ingresa a [Google AI Studio](https://aistudio.google.com/) e inicia sesión con tu cuenta de Google.

2. En el menú lateral izquierdo, haz clic en **Get API key** (Obtener clave de API).

3. Haz clic en **Create API key** (Crear clave de API).

4. Selecciona un proyecto existente de Google Cloud o haz clic en **Create API key in new project** (Crear clave de API en un proyecto nuevo).

5. Copia la clave generada y guárdala; la usarás en la variable `GEMINI_API_KEY`.



### 2. Configurar Google Sheets y obtener `credentials.json`



#### Paso A: Crear el proyecto y activar las APIs

1. Ve a [Google Cloud Console](https://console.cloud.google.com/) e inicia sesión con tu cuenta de Google.

2. En la barra superior, haz clic en el selector de proyectos y selecciona **Proyecto nuevo** (*New Project*). Asígnale un nombre (por ejemplo, `Finanzas AI`) y haz clic en **Crear**.

3. Asegúrate de tener seleccionado el proyecto recién creado en la barra superior.

4. En el menú lateral izquierdo, ve a **APIs y servicios > Biblioteca** (*APIs & Services > Library*).

5. Busca y habilita las siguientes dos APIs (entra a cada una y haz clic en **Habilitar** / *Enable*):

   - **Google Sheets API**

   - **Google Drive API**



#### Paso B: Crear la Cuenta de Servicio (Service Account) y descargar el JSON

1. En el menú lateral izquierdo, ve a **APIs y servicios > Credenciales** (*APIs & Services > Credentials*).

2. Haz clic en **+ Crear credenciales** (*+ Create Credentials*) y elige **Cuenta de servicio** (*Service Account*).

3. Escribe un nombre (por ejemplo, `bot-finanzas`), haz clic en **Crear y continuar**, y luego en **Listo** (*Done*).

4. En la lista de *Cuentas de servicio*, haz clic sobre el correo electrónico recién creado (tendrá un formato similar a `bot-finanzas@tu-proyecto.iam.gserviceaccount.com`).

5. Ve a la pestaña **Claves** (*Keys*) en el menú superior de esa cuenta.

6. Haz clic en **Agregar clave > Crear clave nueva** (*Add Key > Create new key*), selecciona **JSON** y haz clic en **Crear**.

7. Se descargará automáticamente un archivo `.json` a tu computador. Renómbralo a `credentials.json` y muévelo a la carpeta raíz de este proyecto.



#### Paso C: Preparar y vincular tu hoja de Google Sheets

1. Abre el archivo `credentials.json` con cualquier editor de texto y copia el correo electrónico que aparece en el campo `"client_email"`.

2. Crea una hoja de cálculo nueva en [Google Sheets](https://sheets.google.com/).

3. Haz clic en el botón **Compartir** (arriba a la derecha), pega el correo `"client_email"` de tu cuenta de servicio, asegúrate de asignarle permiso de **Editor** y haz clic en **Enviar**.

4. Copia el **ID de tu hoja de cálculo** desde la URL del navegador. Es el código largo ubicado entre `/d/` y `/edit`:

   ```text

   https://docs.google.com/spreadsheets/d/ESTE_ES_EL_SHEET_ID/edit

   ```

5. Asegúrate de que la pestaña principal de tu hoja se llame `Registros` (o el nombre que definas en `WORKSHEET_NAME`).



---



## ⚙️ Instalación y Ejecución Local



1. **Clonar el repositorio:**

   ```bash

   git clone https://github.com/JoacoVC/Finanzas-AI.git

   cd Finanzas-AI

   ```



2. **Crear entorno virtual e instalar dependencias:**

   ```bash

   python -m venv venv

   source venv/bin/activate  # En Windows: venv\Scripts\activate

   pip install -r requirements.txt

   ```



3. **Configurar variables de entorno:**

   Duplica el archivo `.env.example`, renómbralo a `.env` en la raíz del proyecto y completa tus datos:

   ```env

   GEMINI_API_KEY=pega_aqui_tu_api_key_de_gemini

   SHEET_ID=pega_aqui_el_id_de_tu_google_sheet

   WORKSHEET_NAME=Registros

   CREDENTIALS_PATH=credentials.json

   ```



4. **Ejecutar el servidor:**

   ```bash

   uvicorn app.main:app --reload

   ```

   Abre `http://127.0.0.1:8000` en tu navegador.
