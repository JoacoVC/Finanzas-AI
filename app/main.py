import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from app.services.sheets_client import sheets_client
from app.services.llm_factory import llm_factory

app = FastAPI(title="Finanzas AI Backend", version="2.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class MensajeRequest(BaseModel):
    texto: str
    cuenta: str = ""

class TransaccionManualRequest(BaseModel):
    fecha: str
    tipo: str
    categoria: str
    concepto: str
    presupuesto: int = 0
    monto: int
    cuenta: str = "Efectivo"

class CompromisoManualRequest(BaseModel):
    nombre: str
    modalidad: str
    categoria: str
    monto_cuota: int
    cuotas_totales: int = 0
    cuotas_pagadas: int = 0
    dia_pago: int = 1
    flujo: str = "Egreso"

class CuentaRequest(BaseModel):
    nombre: str
    tipo: str  # "Efectivo", "Banco", "Tarjeta"
    saldo: int = 0
    cupo_total: int = 0

class PagoCompromisoRequest(BaseModel):
    cuenta: str = "Efectivo"

class PagoTarjetaDirectoRequest(BaseModel):
    cuenta_origen: str = "Efectivo"
    monto: int = 0
    es_total: bool = True

def mes_espanol(mes_num: int) -> str:
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return meses[mes_num - 1]

def validar_respuesta_ia(info: dict | None, es_transaccion: bool = True):
    if not info or info.get("valido") is False:
        raise HTTPException(
            status_code=400,
            detail="No se detectó audio comprensible ni información financiera clara. Intenta hablar más cerca del micrófono o detallar el gasto."
        )
    if es_transaccion:
        operaciones = info.get("operaciones", [])
        if not operaciones:
            raise HTTPException(
                status_code=400,
                detail="No se detectó un monto válido o la instrucción no contiene movimientos claros."
            )

def ejecutar_operacion_financiera(op: dict, cuenta_override: str = "", cuentas_disponibles: list[str] = None) -> dict:
    accion = op.get("accion", "transaccion")
    
    if accion == "pago_tarjeta":
        tarjeta = op.get("tarjeta", "")
        cuenta_origen = cuenta_override.strip() if cuenta_override.strip() else op.get("cuenta_origen", "Efectivo")
        monto = int(op.get("monto", 0))
        es_total = bool(op.get("es_total", False))
        resultado = sheets_client.pagar_tarjeta(
            nombre_tarjeta=tarjeta,
            cuenta_origen=cuenta_origen,
            monto=monto,
            es_total=es_total
        )
        return {
            "accion": "pago_tarjeta",
            "detalle": resultado,
            "mensaje": resultado.get("mensaje", f"Pago de tarjeta {tarjeta} aplicado.")
        }

    elif accion == "transferencia":
        origen = cuenta_override.strip() if cuenta_override.strip() else op.get("cuenta_origen", "Efectivo")
        destino = op.get("cuenta_destino", "Efectivo")
        monto = int(op.get("monto", 0))
        concepto = op.get("concepto", "")
        resultado = sheets_client.transferir_entre_cuentas(
            cuenta_origen=origen,
            cuenta_destino=destino,
            monto=monto,
            concepto=concepto
        )
        return {
            "accion": "transferencia",
            "detalle": resultado,
            "mensaje": resultado.get("mensaje", f"Transferencia de ${monto:,} de {origen} a {destino} realizada.".replace(",", "."))
        }

    else:
        # Transacción común (Ingreso o Egreso)
        tipo = op.get("tipo", "Egreso")
        categoria = op.get("categoria", "Otros")
        concepto = op.get("concepto", "Movimiento")
        monto = int(op.get("monto", 0))
        
        cuenta = cuenta_override.strip() if cuenta_override.strip() else op.get("cuenta", "Efectivo")
        if cuentas_disponibles and cuenta not in cuentas_disponibles:
            cuenta_match = next((c for c in cuentas_disponibles if c.lower() == cuenta.lower()), None)
            cuenta = cuenta_match if cuenta_match else (cuentas_disponibles[0] if cuentas_disponibles else "Efectivo")

        ahora = datetime.now()
        fila = [ahora.strftime("%d/%m/%Y"), mes_espanol(ahora.month), ahora.year, tipo, categoria, concepto, 0, monto]
        registro_id = sheets_client.append_record(fila, cuenta=cuenta)
        
        signo = "+" if tipo.lower() == "ingreso" else "-"
        msg = f"{'🟢' if tipo.lower() == 'ingreso' else '🔴'} {tipo} ({cuenta}): {concepto} por {signo}${monto:,} [{categoria}]".replace(",", ".")
        return {
            "accion": "transaccion",
            "id": registro_id,
            "fila_insertada": fila,
            "cuenta": cuenta,
            "monto": monto,
            "tipo": tipo,
            "mensaje": msg
        }

@app.get("/", tags=["Frontend"])
def servir_frontend():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "API funcionando."}

# --- ENDPOINTS DE CUENTAS Y TARJETAS ---

@app.get("/cuentas", tags=["Cuentas"])
def obtener_cuentas():
    try:
        cuentas = sheets_client.listar_cuentas()
        return {"status": "success", "cuentas": cuentas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cuentas", tags=["Cuentas"])
def crear_cuenta(req: CuentaRequest):
    try:
        creada = sheets_client.crear_cuenta(req.nombre, req.tipo, req.saldo, req.cupo_total)
        return {"status": "success", "cuenta": creada}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/cuentas/{cuenta_id}", tags=["Cuentas"])
def actualizar_cuenta(cuenta_id: str, req: CuentaRequest):
    try:
        sheets_client.actualizar_cuenta(cuenta_id, req.nombre, req.tipo, req.saldo, req.cupo_total)
        return {"status": "success", "message": "Cuenta actualizada correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/cuentas/{cuenta_id}", tags=["Cuentas"])
def eliminar_cuenta(cuenta_id: str):
    try:
        sheets_client.eliminar_cuenta(cuenta_id)
        return {"status": "success", "message": "Cuenta eliminada correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/cuentas/{cuenta_id}/pagar-tarjeta", tags=["Cuentas"])
def pagar_tarjeta_directo(cuenta_id: str, req: PagoTarjetaDirectoRequest = PagoTarjetaDirectoRequest()):
    try:
        cuentas = sheets_client.listar_cuentas()
        tarjeta = next((c for c in cuentas if c["id"] == cuenta_id), None)
        if not tarjeta:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada.")
        
        resultado = sheets_client.pagar_tarjeta(
            nombre_tarjeta=tarjeta["nombre"],
            cuenta_origen=req.cuenta_origen,
            monto=req.monto,
            es_total=req.es_total
        )
        return {"status": "success", "data": resultado, "message": resultado.get("mensaje")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/deudas-resumen", tags=["Compromisos"])
def obtener_resumen_deudas():
    try:
        resumen = sheets_client.obtener_resumen_deudas()
        return {"status": "success", "data": resumen}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        contexto = sheets_client.obtener_contexto_financiero()
        cuentas = [c["nombre"] for c in sheets_client.listar_cuentas()]
        info = llm_factory.parsear_operaciones(req.texto, contexto)
        validar_respuesta_ia(info, es_transaccion=True)
        
        operaciones = info.get("operaciones", [])
        ejecutadas = []
        for op in operaciones:
            res = ejecutar_operacion_financiera(op, cuenta_override=req.cuenta, cuentas_disponibles=cuentas)
            ejecutadas.append(res)

        resumen_texto = info.get("resumen", "")
        if len(ejecutadas) == 1:
            mensaje_final = ejecutadas[0]["mensaje"]
        else:
            lineas = [f"✅ {resumen_texto or f'{len(ejecutadas)} operaciones procesadas'}:"]
            for ej in ejecutadas:
                lineas.append(f"• {ej['mensaje']}")
            mensaje_final = "\n".join(lineas)

        return {
            "status": "success",
            "message": mensaje_final,
            "data": {
                "resumen": resumen_texto,
                "operaciones": ejecutadas
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/registrar-transaccion-media", tags=["Transacciones"])
async def registrar_transaccion_media(
    archivo: UploadFile | None = File(None),
    archivos: list[UploadFile] | None = File(None),
    nota: str = Form(default=""),
    cuenta: str = Form(default="")
):
    try:
        lista_archivos_raw = []
        if archivos:
            lista_archivos_raw.extend(archivos)
        if archivo:
            lista_archivos_raw.append(archivo)

        if not lista_archivos_raw:
            raise HTTPException(status_code=400, detail="No se recibió ningún archivo o audio para procesar.")

        archivos_bytes = []
        for arch in lista_archivos_raw:
            contenido = await arch.read()
            if contenido and len(contenido) >= 200:
                mime_type = arch.content_type or "image/jpeg"
                archivos_bytes.append((contenido, mime_type))

        if not archivos_bytes:
            raise HTTPException(status_code=400, detail="El archivo o audio recibido está vacío o es demasiado corto.")

        contexto = sheets_client.obtener_contexto_financiero()
        cuentas = [c["nombre"] for c in sheets_client.listar_cuentas()]
        
        info = llm_factory.parsear_operaciones_multimodal(
            archivos=archivos_bytes,
            nota_extra=nota,
            contexto_financiero=contexto
        )
        validar_respuesta_ia(info, es_transaccion=True)

        operaciones = info.get("operaciones", [])
        ejecutadas = []
        for op in operaciones:
            res = ejecutar_operacion_financiera(op, cuenta_override=cuenta, cuentas_disponibles=cuentas)
            ejecutadas.append(res)

        resumen_texto = info.get("resumen", "")
        if len(ejecutadas) == 1:
            mensaje_final = ejecutadas[0]["mensaje"]
        else:
            lineas = [f"✅ {resumen_texto or f'{len(ejecutadas)} operaciones procesadas'}:"]
            for ej in ejecutadas:
                lineas.append(f"• {ej['mensaje']}")
            mensaje_final = "\n".join(lineas)

        return {
            "status": "success",
            "message": mensaje_final,
            "data": {
                "resumen": resumen_texto,
                "operaciones": ejecutadas
            }
        }
    except HTTPException:
        raise
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
        registro_id = sheets_client.append_record(fila, cuenta=req.cuenta)

        return {
            "status": "success",
            "message": "Transacción manual registrada exitosamente",
            "data": {"id": registro_id, "fila_insertada": fila, "cuenta": req.cuenta}
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
        sheets_client.update_record(record_id, fila, cuenta=req.cuenta)
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

# --- ENDPOINTS DE COMPROMISOS (DEUDAS, PAGOS E INGRESOS RECURRENTES) ---

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
        validar_respuesta_ia(info, es_transaccion=False)
        
        creado = sheets_client.crear_compromiso(
            nombre=info.get("nombre", "Compromiso"),
            modalidad=info.get("modalidad", "Recurrente"),
            categoria=info.get("categoria", "Deudas"),
            monto_cuota=int(info.get("monto_cuota", 0)),
            cuotas_totales=int(info.get("cuotas_totales", 0)),
            dia_pago=int(info.get("dia_pago", 1)),
            flujo=info.get("flujo", "Egreso")
        )
        return {"status": "success", "compromiso": creado}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compromisos/ia-audio", tags=["Compromisos"])
async def crear_compromiso_ia_audio(audio: UploadFile = File(...)):
    try:
        contenido = await audio.read()
        if not contenido or len(contenido) < 800:
            raise HTTPException(status_code=400, detail="El audio recibido está vacío.")

        mime_type = audio.content_type or "audio/webm"
        info = llm_factory.parsear_compromiso_multimodal(contenido, mime_type)
        validar_respuesta_ia(info, es_transaccion=False)

        creado = sheets_client.crear_compromiso(
            nombre=info.get("nombre", "Compromiso"),
            modalidad=info.get("modalidad", "Recurrente"),
            categoria=info.get("categoria", "Deudas"),
            monto_cuota=int(info.get("monto_cuota", 0)),
            cuotas_totales=int(info.get("cuotas_totales", 0)),
            dia_pago=int(info.get("dia_pago", 1)),
            flujo=info.get("flujo", "Egreso")
        )
        return {"status": "success", "compromiso": creado}
    except HTTPException:
        raise
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
            cuotas_totales=cuotas,
            dia_pago=req.dia_pago,
            flujo=req.flujo
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
            cuotas_pagadas=req.cuotas_pagadas,
            dia_pago=req.dia_pago,
            flujo=req.flujo
        )
        return {"status": "success", "message": "Compromiso actualizado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/compromisos/{comp_id}/pagar", tags=["Compromisos"])
def pagar_compromiso(comp_id: str, req: PagoCompromisoRequest = PagoCompromisoRequest()):
    try:
        ahora = datetime.now()
        periodo_actual = ahora.strftime("%Y-%m")
        resultado = sheets_client.registrar_pago_compromiso(comp_id, periodo_actual)
        es_ingreso = resultado.get("flujo", "Egreso").lower() == "ingreso"

        if resultado["modalidad"] == "Cuotas":
            concepto = f"{resultado['nombre']} (Cuota {resultado['cuotas_pagadas']}/{resultado['cuotas_totales']})"
        else:
            concepto = f"{resultado['nombre']} ({mes_espanol(ahora.month)})"

        tipo_mov = "Ingreso" if es_ingreso else "Egreso"
        fila = [
            ahora.strftime("%d/%m/%Y"),
            mes_espanol(ahora.month),
            ahora.year,
            tipo_mov,
            resultado["categoria"],
            concepto,
            resultado["monto_cuota"],
            resultado["monto_cuota"]
        ]
        sheets_client.append_record(fila, cuenta=req.cuenta)

        if es_ingreso:
            mensaje = f"✅ Ingreso registrado: {concepto} por +${resultado['monto_cuota']:,} en {req.cuenta}".replace(",", ".")
        elif resultado["finalizado"]:
            mensaje = f"🎉 ¡Deuda finalizada! Pagaste la última cuota de '{resultado['nombre']}'."
        else:
            mensaje = f"✅ Pago registrado: {concepto} por ${resultado['monto_cuota']:,} ({req.cuenta})".replace(",", ".")

        return {"status": "success", "finalizado": resultado["finalizado"], "message": mensaje}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/compromisos/{comp_id}/marcar-pagado", tags=["Compromisos"])
def marcar_compromiso_pagado_sin_saldo(comp_id: str):
    """Marca el compromiso como pagado/cobrado este mes sin registrar movimiento ni alterar el saldo actual."""
    try:
        periodo_actual = datetime.now().strftime("%Y-%m")
        resultado = sheets_client.registrar_pago_compromiso(comp_id, periodo_actual)
        mensaje = f"✓ '{resultado['nombre']}' marcado como al día este mes (sin afectar tu saldo actual)."
        return {"status": "success", "message": mensaje}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/compromisos/{comp_id}/liquidar", tags=["Compromisos"])
def liquidar_compromiso(comp_id: str, req: PagoCompromisoRequest = PagoCompromisoRequest()):
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
        sheets_client.append_record(fila, cuenta=req.cuenta)

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