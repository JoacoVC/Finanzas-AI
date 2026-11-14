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
                http_options=types.HttpOptions(timeout=15000)
            )

    def parsear_transaccion(self, texto: str) -> Optional[Dict]:
        if not self.client:
            raise ValueError("No hay un modelo de IA configurado. Verifica tus API Keys.")

        categorias = [
            'Trabajo', 'Comida', 'Transporte', 'Suscripciones', 
            'Compras', 'Servicios', 'Deudas', 'Ahorro', 'Préstamo', 'Otros'
        ]
        
        prompt = f'''
        Eres un asistente financiero personal. Analiza este mensaje en español:

        "{texto}"

        Reglas de clasificación (muy importante):
        - 'Préstamo' y 'Deudas' pueden aparecer tanto en Ingreso como en Egreso:
            * Si la persona RECIBE un préstamo (ej: "me prestaron", "me prestó") -> tipo="Ingreso", categoria="Préstamo".
            * Si la persona PAGA una deuda o cuota (ej: "pagué la cuota", "aboné deuda") -> tipo="Egreso", categoria="Deudas".
            * Si la persona PRESTA dinero a alguien (ej: "le presté") -> tipo="Egreso", categoria="Préstamo".
            * Si la persona RECIBE devolución de un préstamo que había hecho -> tipo="Ingreso", categoria="Deudas".
        - Para el resto de casos, clasifica con precisión:
            * Ingreso: "Trabajo" (sueldos, honorarios, ventas) o "Otros" (regalos, bonos, reembolsos).
            * Egreso:
                - "Comida": restaurantes, café, pan, mercado, domicilios de comida, almuerzos.
                - "Transporte": pasajes, bus, taxi, Uber, gasolina, peajes.
                - "Suscripciones": Spotify, Netflix, Disney+, gimnasio, apps mensuales, membresías.
                - "Compras": ropa, artículos del hogar, tecnología, Dollar City, compras varias.
                - "Servicios": luz, agua, gas, internet, plan de celular, arriendo.
                - "Ahorro": dinero guardado, inversiones, CDT, bolsillo de ahorro.
                - "Otros": cualquier egreso que no encaje en los anteriores.

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
            m = re.search(r'\{.*\}', resp.text.strip(), re.S)
            return json.loads(m.group()) if m else None
        except Exception as e:
            print(f"Error procesando con IA: {e}")
            return None

    def parsear_compromiso(self, texto: str) -> Optional[Dict]:
        if not self.client:
            raise ValueError("No hay un modelo de IA configurado.")

        prompt = f'''
        Analiza esta descripción de un pago recurrente o deuda a cuotas en español:
        "{texto}"

        Reglas:
        1. modalidad:
           - Usa "Cuotas" si menciona un monto total a pagar, un préstamo o un número definido de cuotas/meses (ej: "debo 2 millones en cuotas de 500 mil", "10 cuotas de 100 mil").
           - Usa "Recurrente" si es un pago fijo mensual sin fecha de fin (ej: "plan de celular 50 mil todos los meses", "internet 80 mil mensual", "Spotify").
        2. categoria: elige entre ["Deudas", "Servicios", "Suscripciones"].
           - Préstamos, tarjetas o deudas personales -> "Deudas".
           - Celular, internet, luz, agua, arriendo -> "Servicios".
           - Plataformas digitales, gimnasio, membresías -> "Suscripciones".
        3. monto_cuota: valor entero de cada pago mensual en pesos.
        4. cuotas_totales:
           - Si modalidad es "Recurrente", devuelve 0.
           - Si modalidad es "Cuotas", calcula o extrae el número entero de cuotas (ej: si debe 2.000.000 y paga 500.000 al mes, cuotas_totales = 4).
        5. nombre: nombre corto y claro del compromiso (<= 4 palabras, ej: "Plan de Celular", "Préstamo Banco").

        Devuelve SOLO un JSON con: nombre, modalidad, categoria, monto_cuota, cuotas_totales.
        '''

        try:
            resp = self.client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            m = re.search(r'\{.*\}', resp.text.strip(), re.S)
            return json.loads(m.group()) if m else None
        except Exception as e:
            print(f"Error parseando compromiso con IA: {e}")
            return None

llm_factory = LLMFactory()