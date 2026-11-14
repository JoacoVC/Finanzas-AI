import json
import time
from google import genai
from google.genai import types
from app.core.config import settings

PROMPT_TRANSACCION = """
Eres un asistente financiero experto en Colombia. Analiza la entrada (texto, audio o imagen de factura/comprobante) y extrae la transacción en JSON estricto.

Reglas:
1. "valido": Si la entrada es un audio vacío, silencio, ruido sin palabras claras o no contiene ninguna intención financiera ni monto identificable, devuelve "valido": false y "monto": 0. De lo contrario, "valido": true.
2. "tipo": Debe ser exactamente "Ingreso" o "Egreso".
3. "categoria":
   - Si "tipo" es "Egreso", elige exclusivamente una de: ["Comida", "Transporte", "Suscripciones", "Compras", "Servicios", "Ahorro", "Préstamo", "Deudas", "Otros"].
   - Si "tipo" es "Ingreso", elige exclusivamente una de: ["Trabajo", "Préstamo", "Deudas", "Otros"].
4. "concepto": Resumen corto y claro (ej. "Mercado en D1", "Almuerzo", "Pago nómina"). NUNCA pongas "transcripción no disponible".
5. "monto": Número entero sin puntos ni signos (ej. 45000). En Colombia "20 barras", "20 lukas" o "20 mil" = 20000.
6. "cuenta": Si el usuario menciona cómo pagó o recibió el dinero, identifícalo comparando con las cuentas disponibles entregadas en el contexto (ej. "Rappicard", "Nu", "Bancolombia", "Nequi", "Efectivo"). Si no menciona ninguna, devuelve "Efectivo".

Responde ÚNICAMENTE con un objeto JSON válido:
{"valido": true, "tipo": "Egreso", "categoria": "Comida", "concepto": "...", "monto": 0, "cuenta": "Efectivo"}
"""

PROMPT_COMPROMISO = """
Eres un asistente financiero. Analiza la entrada (texto o audio) donde el usuario describe un pago recurrente, una deuda a cuotas o un ingreso recurrente (como salario), y extrae la información en JSON estricto.

Reglas:
1. "valido": Si el audio está vacío, en silencio o sin palabras comprensibles, devuelve "valido": false. De lo contrario, "valido": true.
2. "flujo": "Ingreso" si el usuario habla de un dinero que recibe periódicamente (ej. "salario", "sueldo", "quincena", "me pagan arriendo"). "Egreso" si es una deuda, factura, plan o suscripción que debe pagar.
3. "nombre": Nombre corto (ej. "Salario", "Plan de Celular", "Rappicard", "Netflix").
4. "modalidad":
   - "Cuotas" si menciona un número específico de cuotas o meses definidos.
   - "Recurrente" si es mensual indefinido sin fecha de fin (servicios, salario, suscripciones).
5. "categoria":
   - Si "flujo" es "Ingreso", elige entre: ["Trabajo", "Préstamo", "Otros"].
   - Si "flujo" es "Egreso", elige entre: ["Deudas", "Servicios", "Suscripciones"].
6. "monto_cuota": Valor entero de cada cuota/pago mensual.
7. "cuotas_totales": Entero de cuotas totales si modalidad es "Cuotas", o 0 si es "Recurrente".
8. "dia_pago": Día del mes (1 a 31) en que se paga o se recibe si lo menciona (ej. "los 15" -> 15). Si no lo menciona, pon 1.

Responde ÚNICAMENTE con un objeto JSON válido:
{"valido": true, "flujo": "Egreso", "nombre": "...", "modalidad": "...", "categoria": "...", "monto_cuota": 0, "cuotas_totales": 0, "dia_pago": 1}
"""

class LLMFactory:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.modelos = [
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash"
        ]

    def _limpiar_json(self, raw_text: str) -> dict | None:
        try:
            texto_limpio = raw_text.strip()
            if texto_limpio.startswith("```"):
                lineas = texto_limpio.splitlines()
                texto_limpio = "\n".join(lineas[1:-1]).strip()
            return json.loads(texto_limpio)
        except Exception as e:
            print(f"Error parseando JSON de Gemini: {e} | Respuesta cruda: {raw_text}")
            return None

    def _generar_con_respaldo(self, contenidos: list) -> dict | None:
        ultimo_error = None
        for modelo in self.modelos:
            try:
                response = self.client.models.generate_content(
                    model=modelo,
                    contents=contenidos,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                return self._limpiar_json(response.text)
            except Exception as e:
                print(f"⚠️ Fallo con {modelo}: {e}. Probando siguiente modelo...")
                ultimo_error = e
                time.sleep(0.5)
        
        raise RuntimeError(f"Todos los modelos de Gemini están ocupados. Detalle: {ultimo_error}")

    def parsear_transaccion(self, texto: str, cuentas_disponibles: list[str] = None) -> dict | None:
        ctx_cuentas = f"Cuentas/tarjetas disponibles del usuario: {', '.join(cuentas_disponibles or ['Efectivo'])}"
        return self._generar_con_respaldo([PROMPT_TRANSACCION, ctx_cuentas, f"Texto del usuario: {texto}"])

    def parsear_transaccion_multimodal(self, file_bytes: bytes, mime_type: str, nota_extra: str = "", cuentas_disponibles: list[str] = None) -> dict | None:
        part_archivo = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        ctx_cuentas = f"Cuentas/tarjetas disponibles del usuario: {', '.join(cuentas_disponibles or ['Efectivo'])}"
        contenidos = [PROMPT_TRANSACCION, ctx_cuentas, part_archivo]
        if nota_extra.strip():
            contenidos.append(f"Nota adicional del usuario: {nota_extra.strip()}")
        return self._generar_con_respaldo(contenidos)

    def parsear_compromiso(self, texto: str) -> dict | None:
        return self._generar_con_respaldo([PROMPT_COMPROMISO, f"Texto del usuario: {texto}"])

    def parsear_compromiso_multimodal(self, file_bytes: bytes, mime_type: str) -> dict | None:
        part_audio = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        return self._generar_con_respaldo([PROMPT_COMPROMISO, part_audio])

llm_factory = LLMFactory()