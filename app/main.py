from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.services.sheets_client import sheets_client
from app.services.llm_factory import llm_factory

app = FastAPI(title="Finanzas AI Backend", version="1.0.0")

class MensajeRequest(BaseModel):
    texto: str

def mes_espanol(mes_num: int) -> str:
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return meses[mes_num - 1]

@app.get("/", tags=["Estado"])
def health_check():
    return {"status": "ok", "message": "API funcionando."}

@app.post("/test-sheets", tags=["Pruebas"])
def test_sheets_connection():
    try:
        fila_prueba = ["13/11/2026", "Noviembre", 2026, "Egreso", "Gastos", "Prueba de API", 0, 15000]
        nuevo_id = sheets_client.append_record(fila_prueba)
        return {"status": "success", "message": "Fila insertada en Google Sheets", "id_generado": nuevo_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-transaccion", tags=["Transacciones"])
def registrar_transaccion(req: MensajeRequest):
    try:
        # 1. Procesar el texto en lenguaje natural con Gemini
        info = llm_factory.parsear_transaccion(req.texto)
        if not info:
            raise HTTPException(status_code=400, detail="La IA no pudo interpretar el mensaje.")
        
        # 2. Extraer datos del JSON de la IA
        tipo = info.get("tipo", "Egreso")
        categoria = info.get("categoria", "Otros")
        concepto = info.get("concepto", "")
        monto = info.get("monto", 0)

        # 3. Generar fechas automáticas
        ahora = datetime.now()
        fecha = ahora.strftime("%d/%m/%Y")
        mes = mes_espanol(ahora.month)
        anio = ahora.year

        # 4. Armar la fila (Fecha, Mes, Año, Tipo, Categoria, Concepto, Presupuesto, Monto)
        fila = [fecha, mes, anio, tipo, categoria, concepto, 0, monto]

        # 5. Guardar en Sheets y obtener el ID único
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Transacción registrada exitosamente",
            "data": {
                "id": registro_id,
                "fila_insertada": fila
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
