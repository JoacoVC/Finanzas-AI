import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from app.services.sheets_client import sheets_client
from app.services.llm_factory import llm_factory

app = FastAPI(title="Finanzas AI Backend", version="1.1.0")

# Asegurar que exista la carpeta static y montarla
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class MensajeRequest(BaseModel):
    texto: str

class TransaccionManualRequest(BaseModel):
    fecha: str          # Formato esperado: YYYY-MM-DD desde el input HTML
    tipo: str           # "Ingreso" o "Egreso"
    categoria: str
    concepto: str
    presupuesto: int = 0
    monto: int

def mes_espanol(mes_num: int) -> str:
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return meses[mes_num - 1]

@app.get("/", tags=["Frontend"])
def servir_frontend():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "API funcionando. Crea app/static/index.html para ver la interfaz."}

@app.get("/health", tags=["Estado"])
def health_check():
    return {"status": "ok", "message": "API funcionando."}

@app.get("/movimientos", tags=["Transacciones"])
def obtener_movimientos():
    try:
        registros = sheets_client.get_all_records()
        
        total_ingresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "ingreso")
        total_egresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "egreso")
        balance = total_ingresos - total_egresos

        # Devolvemos los más recientes primero
        registros_invertidos = list(reversed(registros))

        return {
            "status": "success",
            "resumen": {
                "ingresos": total_ingresos,
                "egresos": total_egresos,
                "balance": balance
            },
            "movimientos": registros_invertidos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-transaccion", tags=["Transacciones"])
def registrar_transaccion(req: MensajeRequest):
    try:
        info = llm_factory.parsear_transaccion(req.texto)
        if not info:
            raise HTTPException(status_code=400, detail="La IA no pudo interpretar el mensaje.")
        
        tipo = info.get("tipo", "Egreso")
        categoria = info.get("categoria", "Otros")
        concepto = info.get("concepto", "")
        monto = info.get("monto", 0)

        ahora = datetime.now()
        fecha = ahora.strftime("%d/%m/%Y")
        mes = mes_espanol(ahora.month)
        anio = ahora.year

        fila = [fecha, mes, anio, tipo, categoria, concepto, 0, monto]
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Transacción registrada con IA exitosamente",
            "data": {
                "id": registro_id,
                "fila_insertada": fila
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-manual", tags=["Transacciones"])
def registrar_manual(req: TransaccionManualRequest):
    try:
        # Convertir fecha YYYY-MM-DD (HTML) a DD/MM/YYYY (Google Sheets)
        dt = datetime.strptime(req.fecha, "%Y-%m-%d")
        fecha_formateada = dt.strftime("%d/%m/%Y")
        mes = mes_espanol(dt.month)
        anio = dt.year

        fila = [
            fecha_formateada,
            mes,
            anio,
            req.tipo,
            req.categoria,
            req.concepto,
            req.presupuesto,
            req.monto
        ]
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Transacción manual registrada exitosamente",
            "data": {
                "id": registro_id,
                "fila_insertada": fila
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))