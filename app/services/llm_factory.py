import json
import time
from google import genai
from google.genai import types
from app.core.config import settings

PROMPT_FINANCIERO_MULTIMODAL = """
Eres un asistente de finanzas personales altamente inteligente, ágil y experto en Colombia.
Tu tarea es analizar la entrada del usuario (que puede ser texto libre, una nota de voz, una o múltiples fotos de comprobantes/facturas, o una combinación de ellos), teniendo en cuenta el contexto financiero actual del usuario (cuentas bancarias, efectivo, tarjetas de crédito, cupos y deudas).

Debes identificar TODAS las intenciones y movimientos financieros y devolver una lista estructurada de operaciones en formato JSON estricto.

### Tipos de Operaciones Soportadas:
1. "transaccion": Un gasto (Egreso) o entrada de dinero (Ingreso).
   - "tipo": "Ingreso" o "Egreso".
   - "categoria":
     * Si "tipo" es "Egreso": una de ["Comida", "Transporte", "Suscripciones", "Compras", "Servicios", "Ahorro", "Préstamo", "Deudas", "Otros"].
     * Si "tipo" es "Ingreso": una de ["Trabajo", "Préstamo", "Deudas", "Otros"].
   - "concepto": Resumen corto, conciso y claro (ej. "Almuerzo corriente", "Entrega domicilios", "Gasolina", "Mercado D1", "Compra en Éxito"). NUNCA pongas "transcripción no disponible".
   - "monto": Número entero positivo en pesos colombianos, sin puntos ni signos (ej. 25000).
     En Colombia: "25 lucas", "25 barras", "25 mil" o "25k" = 25000; "500 mil" = 500000; "1 millón" o "1m" = 1000000.
   - "cuenta": Nombre exacto de la cuenta o tarjeta utilizada según las cuentas disponibles en el contexto (ej. "Rappicard", "Bancolombia", "Efectivo", "Nequi"). Si no se menciona o no se deduce con claridad, usa "Efectivo".

2. "pago_tarjeta": Pago total o abono parcial a una tarjeta de crédito.
   - "tarjeta": Nombre exacto de la tarjeta de crédito a pagar (ej. "Rappicard").
   - "cuenta_origen": Nombre de la cuenta de dinero con que se paga (ej. "Bancolombia", "Efectivo", "Nequi"). Si no se especifica, usa "Efectivo".
   - "es_total": boolean.
     * true: Si el usuario dice "pagué el saldo de la tarjeta", "pagué toda la tarjeta", "pagué la tarjeta completa", "liquidé la tarjeta", "dejé la tarjeta en cero". El sistema tomará la deuda viva actual de la tarjeta y la dejará en $0.
     * false: Si el usuario da un monto específico para abonar (ej. "pagué 500.000 de la tarjeta").
   - "monto": Entero positivo del abono si es_total es false. Si es_total es true, pon 0 (el backend usará el saldo total adeudado).
   * REGLA CLAVE: Pagar una tarjeta de crédito desde una cuenta de ahorros o efectivo (ej. "pagué Rappicard desde Nequi") NUNCA es un traslado ordinario; es SIEMPRE "pago_tarjeta".

3. "transferencia" (o "traslado"): Movimiento de fondos entre dos cuentas propias líquidas (ej. de Bancolombia a Nequi, o de Efectivo a Daviplata).
   - "cuenta_origen": Cuenta desde donde sale el dinero.
   - "cuenta_destino": Cuenta a donde entra el dinero.
   - "monto": Entero positivo.
   - "concepto": Breve descripción (ej. "Traslado de Nequi a Rappi cuenta de ahorros").
   * REGLA CLAVE: Un traslado entre cuentas propias NO es ingreso ni egreso general de la persona; solo traslada saldo entre cuentas. Si la cuenta destino es una tarjeta de crédito, usa "pago_tarjeta".

4. "pago_compromiso": Pago de una cuota o liquidación de un compromiso recurrente o deuda registrada.
   - "nombre_compromiso": Nombre del compromiso activo según el contexto (ej. "Préstamo Moto", "Netflix", "Plan Celular").
   - "cuenta_origen": Cuenta con que se paga.
   - "es_liquidacion": boolean (true si liquida el total de cuotas pendientes).
   - "monto": Entero positivo de la cuota o 0 si toma el valor configurado.

### Reglas Críticas:
1. MULTI-MOVIMIENTO: Si el usuario menciona varios movimientos en un solo mensaje o audio (ejemplo: "me acabo de hacer 25.000 pesos en unos domicilios, pero me gasté 5.000 en una Coca-Cola"), o si se adjuntan varias fotos de recibos, debes extraer y agregar CADA MOVIMIENTO INDIVIDUAL en la lista "operaciones".
2. VALIDEZ: Si la entrada es un audio vacío, silencio absoluto, ruido incomprensible o no contiene ningún dato o intención financiera ("hola qué tal"), devuelve "valido": false y "operaciones": [].
3. MONTO: En transacciones normales, el monto DEBE ser mayor a 0.
4. RESUMEN: Una frase breve y humana que explique qué se procesará (ej. "Registrados 1 ingreso ($25.000) y 1 egreso ($5.000)" o "Pago de saldo total de Rappicard desde Bancolombia").

### Formato de Respuesta JSON (Únicamente este objeto JSON sin bloques extras):
{
  "valido": true,
  "resumen": "Resumen amigable de las operaciones",
  "operaciones": [
    {
      "accion": "transaccion",
      "tipo": "Ingreso",
      "categoria": "Trabajo",
      "concepto": "Domicilios",
      "monto": 25000,
      "cuenta": "Efectivo"
    },
    {
      "accion": "transaccion",
      "tipo": "Egreso",
      "categoria": "Comida",
      "concepto": "Coca-Cola",
      "monto": 5000,
      "cuenta": "Efectivo"
    }
  ]
}
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
            "gemini-3.8-flash",
            "gemini-2.5-flash"
        ]

    def _limpiar_json(self, raw_text: str) -> dict | None:
        try:
            texto_limpio = raw_text.strip()
            if texto_limpio.startswith("```"):
                lineas = texto_limpio.splitlines()
                if lineas[0].startswith("```"):
                    lineas = lineas[1:]
                if lineas and lineas[-1].startswith("```"):
                    lineas = lineas[:-1]
                texto_limpio = "\n".join(lineas).strip()
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
                time.sleep(0.4)
        
        raise RuntimeError(f"Todos los modelos de Gemini están ocupados o con límite temporal. Detalle: {ultimo_error}")

    def parsear_operaciones(self, texto: str, contexto_financiero: str = "") -> dict | None:
        contenidos = [PROMPT_FINANCIERO_MULTIMODAL]
        if contexto_financiero.strip():
            contenidos.append(contexto_financiero.strip())
        contenidos.append(f"Entrada del usuario: {texto}")
        return self._generar_con_respaldo(contenidos)

    def parsear_operaciones_multimodal(
        self,
        archivos: list[tuple[bytes, str]],
        nota_extra: str = "",
        contexto_financiero: str = ""
    ) -> dict | None:
        contenidos = [PROMPT_FINANCIERO_MULTIMODAL]
        if contexto_financiero.strip():
            contenidos.append(contexto_financiero.strip())
        
        for file_bytes, mime_type in archivos:
            part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            contenidos.append(part)

        if nota_extra.strip():
            contenidos.append(f"Nota o instrucción adicional del usuario: {nota_extra.strip()}")
            
        return self._generar_con_respaldo(contenidos)

    def parsear_compromiso(self, texto: str) -> dict | None:
        return self._generar_con_respaldo([PROMPT_COMPROMISO, f"Texto del usuario: {texto}"])

    def parsear_compromiso_multimodal(self, file_bytes: bytes, mime_type: str) -> dict | None:
        part_audio = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        return self._generar_con_respaldo([PROMPT_COMPROMISO, part_audio])

llm_factory = LLMFactory()
