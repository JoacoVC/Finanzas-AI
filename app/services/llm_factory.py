import os
import json
import time
from google import genai
from google.genai import types
from app.core.config import settings

PROMPT_TRANSACCION = """
Eres un asistente financiero experto en Colombia. Analiza la entrada (texto, audio o imagen de factura/comprobante de transferencia) y extrae la información de la transacción financiera en formato JSON estricto.

Reglas:
1. "tipo": Debe ser exactamente "Ingreso" o "Egreso". (Si es una factura de compra o transferencia enviada, es "Egreso". Si es dinero recibido o pago recibido, es "Ingreso").
2. "categoria":
   - Si "tipo" es "Egreso", elige exclusivamente una de: ["Comida", "Transporte", "Suscripciones", "Compras", "Servicios", "Ahorro", "Préstamo", "Deudas", "Otros"].
   - Si "tipo" es "Ingreso", elige exclusivamente una de: ["Trabajo", "Préstamo", "Deudas", "Otros"].
3. "concepto": Un resumen corto, claro y descriptivo (ej. "Mercado en D1", "Transferencia Nequi a Carlos", "Almuerzo", "Pago nómina"). Si es una factura de supermercado o tienda, incluye el nombre del comercio.
4. "monto": Un número entero sin puntos, comas ni signos de moneda (ej. 45000). Si es una factura, toma el TOTAL PAGADO final (ignora subtotales, IVA desglosado o devuelta/cambio). Si en Colombia dicen "20 barras", "20 lukas" o "20 mil", es 20000.

Responde ÚNICAMENTE con un objeto JSON válido:
{"tipo": "...", "categoria": "...", "concepto": "...", "monto": 0}
"""

PROMPT_COMPROMISO = """
Eres un asistente financiero. Analiza la entrada (texto o audio) donde el usuario describe un pago recurrente o una deuda a cuotas, y extrae la información en formato JSON estricto.

Reglas:
1. "nombre": Nombre corto del compromiso o deuda (ej. "Plan de Celular", "Crédito Banco", "Netflix", "Cultivo de Arroz").
2. "modalidad":
   - Usa "Cuotas" si menciona un número específico de cuotas, meses definidos o un plazo fijo para terminar de pagar.
   - Usa "Recurrente" si es un pago mensual indefinido sin fecha de fin (como servicios, arriendo, suscripciones).
3. "categoria": Elige exclusivamente una de: ["Deudas", "Servicios", "Suscripciones"].
4. "monto_cuota": El valor entero de CADA cuota mensual (sin puntos ni signos). Nota: Si el usuario dice "debo 3 millones a 10 cuotas" y no da el valor de la cuota, calcula 3000000 / 10 = 300000. Si dice "8 cuotas de 465 mil", el monto_cuota es 465000.
5. "cuotas_totales": Número entero de cuotas totales si modalidad es "Cuotas" (ej. 8). Si modalidad es "Recurrente", pon 0.

Responde ÚNICAMENTE con un objeto JSON válido:
{"nombre": "...", "modalidad": "...", "categoria": "...", "monto_cuota": 0, "cuotas_totales": 0}
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
                print(f"⚠️ Fallo con {modelo}: {e}. Probando siguiente modelo de respaldo...")
                ultimo_error = e
                time.sleep(0.5)
        
        raise RuntimeError(f"Todos los modelos de Gemini están ocupados en este momento. Detalle: {ultimo_error}")

    def parsear_transaccion(self, texto: str) -> dict | None:
        return self._generar_con_respaldo([PROMPT_TRANSACCION, f"Texto del usuario: {texto}"])

    def parsear_transaccion_multimodal(self, file_bytes: bytes, mime_type: str, nota_extra: str = "") -> dict | None:
        part_archivo = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        contenidos = [PROMPT_TRANSACCION, part_archivo]
        if nota_extra.strip():
            contenidos.append(f"Nota adicional del usuario: {nota_extra.strip()}")
        return self._generar_con_respaldo(contenidos)

    def parsear_compromiso(self, texto: str) -> dict | None:
        return self._generar_con_respaldo([PROMPT_COMPROMISO, f"Texto del usuario: {texto}"])

    def parsear_compromiso_multimodal(self, file_bytes: bytes, mime_type: str) -> dict | None:
        part_audio = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        return self._generar_con_respaldo([PROMPT_COMPROMISO, part_audio])

llm_factory = LLMFactory()