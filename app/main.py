import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from app.services.sheets_client import sheets_client
from app.services.llm_factory import llm_factory

app = FastAPI(title="Finanzas AI Backend", version="1.5.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class MensajeRequest(BaseModel):
    texto: str

class TransaccionManualRequest(BaseModel):
    fecha: str
    tipo: str
    categoria: str
    concepto: str
    presupuesto: int = 0
    monto: int

class CompromisoManualRequest(BaseModel):
    nombre: str
    modalidad: str
    categoria: str
    monto_cuota: int
    cuotas_totales: int = 0
    cuotas_pagadas: int = 0

def mes_espanol(mes_num: int) -> str:
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return meses[mes_num - 1]

@app.get("/", tags=["Frontend"])
def servir_frontend():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "API funcionando."}

# --- ENDPOINTS DE TRANSACCIONES ---

@app.get("/movimientos", tags=["Transacciones"])
def obtener_movimientos():
    try:
        registros = sheets_client.get_all_records()
        total_ingresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "ingreso")
        total_egresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "egreso")
        balance = total_ingresos - total_egresos

        return {
            "status": "success",
            "resumen": {
                "ingresos": total_ingresos,
                "egresos": total_egresos,
                "balance": balance
            },
            "movimientos": list(reversed(registros))
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
        fila = [ahora.strftime("%d/%m/%Y"), mes_espanol(ahora.month), ahora.year, tipo, categoria, concepto, 0, monto]
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Transacción registrada con IA exitosamente",
            "data": {"id": registro_id, "fila_insertada": fila}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-transaccion-media", tags=["Transacciones"])
async def registrar_transaccion_media(
    archivo: UploadFile = File(...),
    nota: str = Form(default="")
):
    try:
        contenido = await archivo.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo recibido está vacío.")

        mime_type = archivo.content_type or "image/jpeg"
        info = llm_factory.parsear_transaccion_multimodal(contenido, mime_type, nota)
        if not info:
            raise HTTPException(status_code=400, detail="La IA no pudo extraer datos del archivo.")

        tipo = info.get("tipo", "Egreso")
        categoria = info.get("categoria", "Otros")
        concepto = info.get("concepto", "Movimiento multimedia")
        monto = int(info.get("monto", 0))

        ahora = datetime.now()
        fila = [ahora.strftime("%d/%m/%Y"), mes_espanol(ahora.month), ahora.year, tipo, categoria, concepto, 0, monto]
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Movimiento extraído y guardado exitosamente",
            "data": {"id": registro_id, "fila_insertada": fila}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-manual", tags=["Transacciones"])
def registrar_manual(req: TransaccionManualRequest):
    try:
        dt = datetime.strptime(req.fecha, "%Y-%m-%d")
        fila = [
            dt.strftime("%d/%m/%Y"), mes_espanol(dt.month), dt.year,
            req.tipo, req.categoria, req.concepto, req.presupuesto, req.monto
        ]
        registro_id = sheets_client.append_record(fila)

        return {
            "status": "success",
            "message": "Transacción manual registrada exitosamente",
            "data": {"id": registro_id, "fila_insertada": fila}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/movimientos/{record_id}", tags=["Transacciones"])
def actualizar_movimiento(record_id: str, req: TransaccionManualRequest):
    try:
        dt = datetime.strptime(req.fecha, "%Y-%m-%d")
        fila = [
            dt.strftime("%d/%m/%Y"), mes_espanol(dt.month), dt.year,
            req.tipo, req.categoria, req.concepto, req.presupuesto, req.monto
        ]
        sheets_client.update_record(record_id, fila)
        return {"status": "success", "message": "Movimiento actualizado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/movimientos/{record_id}", tags=["Transacciones"])
def eliminar_movimiento(record_id: str):
    try:
        sheets_client.delete_record(record_id)
        return {"status": "success", "message": "Movimiento eliminado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- ENDPOINTS DE COMPROMISOS Y DEUDAS RECURRENTES ---

@app.get("/compromisos", tags=["Compromisos"])
def listar_compromisos():
    try:
        activos = sheets_client.listar_compromisos_activos()
        periodo_actual = datetime.now().strftime("%Y-%m")
        for c in activos:
            c["pagado_este_mes"] = (c["ultimo_mes_pagado"] == periodo_actual)
        return {"status": "success", "periodo_actual": periodo_actual, "compromisos": activos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compromisos/ia", tags=["Compromisos"])
def crear_compromiso_ia(req: MensajeRequest):
    try:
        info = llm_factory.parsear_compromiso(req.texto)
        if not info:
            raise HTTPException(status_code=400, detail="La IA no pudo interpretar el compromiso.")
        
        creado = sheets_client.crear_compromiso(
            nombre=info.get("nombre", "Compromiso"),
            modalidad=info.get("modalidad", "Recurrente"),
            categoria=info.get("categoria", "Deudas"),
            monto_cuota=int(info.get("monto_cuota", 0)),
            cuotas_totales=int(info.get("cuotas_totales", 0))
        )
        return {"status": "success", "compromiso": creado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compromisos/ia-audio", tags=["Compromisos"])
async def crear_compromiso_ia_audio(audio: UploadFile = File(...)):
    try:
        contenido = await audio.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El audio recibido está vacío.")

        mime_type = audio.content_type or "audio/webm"
        info = llm_factory.parsear_compromiso_multimodal(contenido, mime_type)
        if not info:
            raise HTTPException(status_code=400, detail="La IA no pudo interpretar el audio del compromiso.")

        creado = sheets_client.crear_compromiso(
            nombre=info.get("nombre", "Compromiso"),
            modalidad=info.get("modalidad", "Recurrente"),
            categoria=info.get("categoria", "Deudas"),
            monto_cuota=int(info.get("monto_cuota", 0)),
            cuotas_totales=int(info.get("cuotas_totales", 0))
        )
        return {"status": "success", "compromiso": creado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compromisos/manual", tags=["Compromisos"])
def crear_compromiso_manual(req: CompromisoManualRequest):
    try:
        cuotas = req.cuotas_totales if req.modalidad == "Cuotas" else 0
        creado = sheets_client.crear_compromiso(
            nombre=req.nombre,
            modalidad=req.modalidad,
            categoria=req.categoria,
            monto_cuota=req.monto_cuota,
            cuotas_totales=cuotas
        )
        return {"status": "success", "compromiso": creado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/compromisos/{comp_id}", tags=["Compromisos"])
def editar_compromiso(comp_id: str, req: CompromisoManualRequest):
    try:
        sheets_client.actualizar_compromiso(
            comp_id=comp_id,
            nombre=req.nombre,
            modalidad=req.modalidad,
            categoria=req.categoria,
            monto_cuota=req.monto_cuota,
            cuotas_totales=req.cuotas_totales,
            cuotas_pagadas=req.cuotas_pagadas
        )
        return {"status": "success", "message": "Compromiso actualizado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/compromisos/{comp_id}/pagar", tags=["Compromisos"])
def pagar_compromiso(comp_id: str):
    try:
        ahora = datetime.now()
        periodo_actual = ahora.strftime("%Y-%m")
        resultado = sheets_client.registrar_pago_compromiso(comp_id, periodo_actual)

        if resultado["modalidad"] == "Cuotas":
            concepto = f"{resultado['nombre']} (Cuota {resultado['cuotas_pagadas']}/{resultado['cuotas_totales']})"
        else:
            concepto = f"{resultado['nombre']} ({mes_espanol(ahora.month)})"

        fila = [
            ahora.strftime("%d/%m/%Y"),
            mes_espanol(ahora.month),
            ahora.year,
            "Egreso",
            resultado["categoria"],
            concepto,
            resultado["monto_cuota"],
            resultado["monto_cuota"]
        ]
        sheets_client.append_record(fila)

        mensaje = (
            f"🎉 ¡Deuda finalizada! Pagaste la última cuota de '{resultado['nombre']}'."
            if resultado["finalizado"]
            else f"✅ Pago registrado: {concepto} por ${resultado['monto_cuota']:,}".replace(",", ".")
        )

        return {"status": "success", "finalizado": resultado["finalizado"], "message": mensaje}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/compromisos/{comp_id}/liquidar", tags=["Compromisos"])
def liquidar_compromiso(comp_id: str):
    try:
        ahora = datetime.now()
        periodo_actual = ahora.strftime("%Y-%m")
        resultado = sheets_client.liquidar_compromiso(comp_id, periodo_actual)

        monto_total = resultado["monto_liquidacion"]
        concepto = f"{resultado['nombre']} (Liquidación total - {resultado['cuotas_restantes']} cuotas)"

        fila = [
            ahora.strftime("%d/%m/%Y"),
            mes_espanol(ahora.month),
            ahora.year,
            "Egreso",
            resultado["categoria"],
            concepto,
            monto_total,
            monto_total
        ]
        sheets_client.append_record(fila)

        mensaje = f"🎉 ¡Deuda liquidada! Se registró el pago final de '{resultado['nombre']}' por ${monto_total:,}".replace(",", ".")
        return {"status": "success", "message": mensaje}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/compromisos/{comp_id}", tags=["Compromisos"])
def eliminar_compromiso(comp_id: str):
    try:
        sheets_client.eliminar_compromiso(comp_id)
        return {"status": "success", "message": "Compromiso eliminado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))