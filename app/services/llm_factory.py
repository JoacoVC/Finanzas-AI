import json
import re
from typing import Optional, Dict
from google import genai
from google.genai import types
from app.core.config import settings

class LLMFactory:
    def __init__(self):
        self.client = None
        if settings.gemini_api_key:
            self.client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=15000) # Máximo 15 segundos de espera
            )

    def parsear_transaccion(self, texto: str) -> Optional[Dict]:
        """
        Analiza el texto de entrada y devuelve un JSON con la estructura de la transacción.
        """
        if not self.client:
            raise ValueError("No hay un modelo de IA configurado. Verifica tus API Keys.")

        categorias = ['Trabajo', 'Otros', 'Servicios', 'Gastos', 'Deudas', 'Ahorro', 'Préstamo']
        
        prompt = f'''
        Eres un asistente financiero. Analiza este mensaje en español:

        "{texto}"

        Reglas de clasificación (importante):
        - 'Préstamo' y 'Deudas' pueden aparecer tanto en Ingreso como en Egreso.
        - Si la persona RECIBE un préstamo (ej: "me prestaron", "me prestó") -> tipo="Ingreso", categoria="Préstamo".
        - Si la persona PAGA préstamo/deuda (ej: "pagué la cuota", "aboné préstamo") -> tipo="Egreso", categoria="Deudas".
        - Si la persona PRESTA dinero a alguien (ej: "le presté") -> tipo="Egreso", categoria="Préstamo".
        - Si la persona RECIBE devolución de un préstamo que había hecho -> tipo="Ingreso", categoria="Deudas".
        - Caso contrario, usa las categorías normales:
            * Ingreso: "Trabajo", "Otros"
            * Egreso: "Servicios", "Gastos", "Ahorro"

        Devuelve SOLO un JSON con estos campos:
        - tipo: "Ingreso" o "Egreso"
        - categoria: una de {categorias}
        - concepto: resumen muy corto (<= 4 palabras)
        - monto: número entero en pesos (sin símbolos)
        '''

        try:
            resp = self.client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = resp.text.strip()
            
            m = re.search(r'\{.*\}', data, re.S)
            if m:
                return json.loads(m.group())
            else:
                print(f"La IA no devolvió un JSON válido: {data}")
                return None
        except Exception as e:
            print(f"Error procesando con IA: {e}")
            return None

llm_factory = LLMFactory()