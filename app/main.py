import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.models.schemas import (
    MensajeRequest,
    TransaccionManualRequest,
    CompromisoManualRequest,
    CuentaRequest,
    PagoCompromisoRequest,
    LiquidarCompromisoRequest,
    PagoTarjetaDirectoRequest,
    TrasladoRequest
)
from app.services.sheets_client import sheets_client, mes_espanol
from app.services.llm_factory import llm_factory

app = FastAPI(title="Finanzas AI Backend", version="3.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- MANEJO CENTRALIZADO DE ERRORES ---
# Los endpoints NO necesitan try/except: cualquier ValueError (dato inválido,
# entidad no encontrada) responde 400 y cualquier error no controlado responde 500.

@app.exception_handler(ValueError)
async def manejar_value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def manejar_error_inesperado(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# --- HELPERS COMPARTIDOS ---

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

def concepto_pago_compromiso(res: dict) -> str:
    """Concepto estándar para el movimiento generado por un pago de compromiso."""
    ahora = datetime.now()
    if res["modalidad"] == "Cuotas":
        return f"{res['nombre']} (Cuota {res['cuotas_pagadas']}/{res['cuotas_totales']})"
    return f"{res['nombre']} ({mes_espanol(ahora.month)})"

def registrar_movimiento_pago(res: dict, cuenta: str, monto: int, concepto: str) -> str:
    """Inserta en la hoja de Movimientos el registro asociado a un pago de compromiso."""
    ahora = datetime.now()
    es_ingreso = res.get("flujo", "Egreso").lower() == "ingreso"
    fila = [
        ahora.strftime("%d/%m/%Y"),
        mes_espanol(ahora.month),
        ahora.year,
        "Ingreso" if es_ingreso else "Egreso",
        res["categoria"],
        concepto,
        monto
    ]
    return sheets_client.append_record(fila, cuenta=cuenta)

def procesar_respuesta_ia(info: dict, cuenta_override: str, cuentas: list[str]) -> dict:
    """Valida la respuesta de la IA y ejecuta todas las operaciones detectadas."""
    validar_respuesta_ia(info, es_transaccion=True)

    ejecutadas = [
        ejecutar_operacion_financiera(op, cuenta_override, cuentas)
        for op in info.get("operaciones", [])
    ]

    resumen_texto = info.get("resumen", "")
    if len(ejecutadas) == 1:
        mensaje_final = ejecutadas[0]["mensaje"]
    else:
        lineas = [f"✅ {resumen_texto or f'{len(ejecutadas)} operaciones procesadas'}:"]
        lineas += [f"• {ej['mensaje']}" for ej in ejecutadas]
        mensaje_final = "\n".join(lineas)

    return {
        "status": "success",
        "message": mensaje_final,
        "data": {
            "resumen": resumen_texto,
            "operaciones": ejecutadas
        }
    }

def ejecutar_operacion_financiera(op: dict, cuenta_override: str = "", cuentas_disponibles: list[str] = None) -> dict:
    override = (cuenta_override or "").strip()
    accion = op.get("accion", "transaccion").lower()

    if accion == "pago_tarjeta":
        tarjeta = op.get("tarjeta", "")
        cuenta_origen = override or op.get("cuenta_origen", "Efectivo")
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

    elif accion in ["transferencia", "traslado"]:
        origen = override or op.get("cuenta_origen", "Efectivo")
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
            "accion": "traslado",
            "detalle": resultado,
            "mensaje": resultado.get("mensaje", f"Traslado de ${monto:,} de {origen} a {destino} realizado.".replace(",", "."))
        }

    elif accion == "pago_compromiso":
        nombre_comp = op.get("nombre_compromiso", "")
        cuenta_origen = override or op.get("cuenta_origen", "Efectivo")
        es_liq = bool(op.get("es_liquidacion", False))
        monto_custom = int(op.get("monto", 0))

        compromisos = sheets_client.listar_compromisos_activos()
        objetivo = next((c for c in compromisos if c["nombre"].lower() == nombre_comp.lower()), None)
        if not objetivo:
            objetivo = next((c for c in compromisos if nombre_comp.lower() in c["nombre"].lower()), None)

        if not objetivo:
            raise ValueError(f"No se encontró el compromiso o deuda '{nombre_comp}'.")

        periodo = datetime.now().strftime("%Y-%m")

        if es_liq and objetivo["modalidad"] == "Cuotas":
            res = sheets_client.liquidar_compromiso(objetivo["id"], periodo, monto_real=monto_custom if monto_custom > 0 else None)
            monto_pago = res["monto_liquidacion"]
            concepto = f"Liquidación total crédito: {res['nombre']} ({res['cuotas_restantes']} cuotas)"
        else:
            res = sheets_client.registrar_pago_compromiso(objetivo["id"], periodo)
            monto_pago = monto_custom if monto_custom > 0 else res["monto_cuota"]
            concepto = concepto_pago_compromiso(res)

        reg_id = registrar_movimiento_pago(res, cuenta_origen, monto_pago, concepto)

        return {
            "accion": "pago_compromiso",
            "id": reg_id,
            "mensaje": f"✅ Pago registrado: {concepto} por ${monto_pago:,} ({cuenta_origen})".replace(",", ".")
        }

    else:
        # Transacción ordinaria (Ingreso o Egreso)
        tipo = op.get("tipo", "Egreso")
        categoria = op.get("categoria", "Otros")
        concepto = op.get("concepto", "Movimiento")
        monto = int(op.get("monto", 0))

        cuenta = override or op.get("cuenta", "Efectivo")
        if cuentas_disponibles and cuenta not in cuentas_disponibles:
            cuenta_match = next((c for c in cuentas_disponibles if c.lower() == cuenta.lower()), None)
            cuenta = cuenta_match if cuenta_match else (cuentas_disponibles[0] if cuentas_disponibles else "Efectivo")

        ahora = datetime.now()
        fila = [ahora.strftime("%d/%m/%Y"), mes_espanol(ahora.month), ahora.year, tipo, categoria, concepto, monto]
        registro_id = sheets_client.append_record(fila, cuenta=cuenta)

        signo = "+" if tipo.lower() == "ingreso" else ("=" if tipo.lower() == "traslado" else "-")
        emoji = "🟢" if tipo.lower() == "ingreso" else ("🔁" if tipo.lower() == "traslado" else "🔴")
        msg = f"{emoji} {tipo} ({cuenta}): {concepto} por {signo}${monto:,} [{categoria}]".replace(",", ".")
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
    return {"status": "success", "cuentas": sheets_client.listar_cuentas()}

@app.post("/cuentas", tags=["Cuentas"])
def crear_cuenta(req: CuentaRequest):
    creada = sheets_client.crear_cuenta(req.nombre, req.tipo, req.saldo, req.cupo_total, req.dia_pago)
    return {"status": "success", "cuenta": creada}

@app.put("/cuentas/{cuenta_id}", tags=["Cuentas"])
def actualizar_cuenta(cuenta_id: str, req: CuentaRequest):
    sheets_client.actualizar_cuenta(cuenta_id, req.nombre, req.tipo, req.saldo, req.cupo_total, req.dia_pago)
    return {"status": "success", "message": "Cuenta actualizada correctamente."}

@app.delete("/cuentas/{cuenta_id}", tags=["Cuentas"])
def eliminar_cuenta(cuenta_id: str):
    sheets_client.eliminar_cuenta(cuenta_id)
    return {"status": "success", "message": "Cuenta eliminada correctamente."}

@app.post("/cuentas/{cuenta_id}/pagar-tarjeta", tags=["Cuentas"])
def pagar_tarjeta_directo(cuenta_id: str, req: PagoTarjetaDirectoRequest = PagoTarjetaDirectoRequest()):
    cuentas = sheets_client.listar_cuentas()
    tarjeta = next((c for c in cuentas if c["id"] == cuenta_id), None)
    if not tarjeta:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada.")

    resultado = sheets_client.pagar_tarjeta(
        nombre_tarjeta=tarjeta["nombre"],
        cuenta_origen=req.cuenta_origen,
        monto=req.monto,
        es_total=req.es_total,
        concepto=req.concepto
    )
    return {"status": "success", "data": resultado, "message": resultado.get("mensaje")}

@app.post("/traslado", tags=["Cuentas"])
def realizar_traslado(req: TrasladoRequest):
    resultado = sheets_client.transferir_entre_cuentas(
        cuenta_origen=req.cuenta_origen,
        cuenta_destino=req.cuenta_destino,
        monto=req.monto,
        concepto=req.concepto
    )
    return {"status": "success", "data": resultado, "message": resultado.get("mensaje")}

@app.get("/deudas-resumen", tags=["Compromisos"])
def obtener_resumen_deudas():
    return {"status": "success", "data": sheets_client.obtener_resumen_deudas()}

# --- ENDPOINTS DE TRANSACCIONES / MOVIMIENTOS ---

@app.get("/movimientos", tags=["Transacciones"])
def obtener_movimientos():
    registros = sheets_client.get_all_records()

    # Traslados NO se suman ni a ingresos ni a egresos
    total_ingresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "ingreso")
    total_egresos = sum(r["monto"] for r in registros if r["tipo"].lower() == "egreso")
    balance = total_ingresos - total_egresos

    resumen_deudas = sheets_client.obtener_resumen_deudas()
    deuda_total = resumen_deudas.get("total_deuda_global", 0)

    # Saldo disponible en cuentas líquidas
    cuentas = sheets_client.listar_cuentas()
    saldo_disponible = sum(c["saldo"] for c in cuentas if c["tipo"] != "Tarjeta")

    return {
        "status": "success",
        "resumen": {
            "ingresos": total_ingresos,
            "egresos": total_egresos,
            "balance": balance,
            "deuda_total": deuda_total,
            "saldo_disponible": saldo_disponible
        },
        "movimientos": list(reversed(registros))
    }

@app.post("/registrar-transaccion", tags=["Transacciones"])
def registrar_transaccion(req: MensajeRequest):
    contexto = sheets_client.obtener_contexto_financiero()
    cuentas = [c["nombre"] for c in sheets_client.listar_cuentas()]
    info = llm_factory.parsear_operaciones(req.texto, contexto)
    return procesar_respuesta_ia(info, req.cuenta, cuentas)

@app.post("/registrar-transaccion-media", tags=["Transacciones"])
async def registrar_transaccion_media(
    archivo: UploadFile | None = File(None),
    archivos: list[UploadFile] | None = File(None),
    nota: str = Form(default=""),
    cuenta: str = Form(default="")
):
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
    return procesar_respuesta_ia(info, cuenta, cuentas)

@app.post("/registrar-manual", tags=["Transacciones"])
def registrar_manual(req: TransaccionManualRequest):
    dt = datetime.strptime(req.fecha, "%Y-%m-%d")

    if req.tipo.lower() == "traslado":
        resultado = sheets_client.transferir_entre_cuentas(
            cuenta_origen=req.cuenta,
            cuenta_destino=req.cuenta_destino,
            monto=req.monto,
            concepto=req.concepto
        )
        return {
            "status": "success",
            "message": resultado.get("mensaje", "Traslado registrado exitosamente."),
            "data": resultado
        }

    fila = [
        dt.strftime("%d/%m/%Y"), mes_espanol(dt.month), dt.year,
        req.tipo, req.categoria, req.concepto, req.monto
    ]
    registro_id = sheets_client.append_record(fila, cuenta=req.cuenta, cuenta_destino=req.cuenta_destino)

    return {
        "status": "success",
        "message": "Transacción manual registrada exitosamente",
        "data": {"id": registro_id, "fila_insertada": fila, "cuenta": req.cuenta}
    }

@app.put("/movimientos/{record_id}", tags=["Transacciones"])
def actualizar_movimiento(record_id: str, req: TransaccionManualRequest):
    dt = datetime.strptime(req.fecha, "%Y-%m-%d")
    fila = [
        dt.strftime("%d/%m/%Y"), mes_espanol(dt.month), dt.year,
        req.tipo, req.categoria, req.concepto, req.monto
    ]
    sheets_client.update_record(record_id, fila, cuenta=req.cuenta, cuenta_destino=req.cuenta_destino)
    return {"status": "success", "message": "Movimiento actualizado correctamente."}

@app.delete("/movimientos/{record_id}", tags=["Transacciones"])
def eliminar_movimiento(record_id: str):
    sheets_client.delete_record(record_id)
    return {"status": "success", "message": "Movimiento eliminado correctamente."}

# --- ENDPOINTS DE COMPROMISOS (DEUDAS, PAGOS E INGRESOS RECURRENTES) ---

@app.get("/compromisos", tags=["Compromisos"])
def listar_compromisos():
    activos = sheets_client.listar_compromisos_activos()
    periodo_actual = datetime.now().strftime("%Y-%m")
    for c in activos:
        c["pagado_este_mes"] = (c["ultimo_mes_pagado"] == periodo_actual)
    return {"status": "success", "periodo_actual": periodo_actual, "compromisos": activos}

@app.post("/compromisos/ia", tags=["Compromisos"])
def crear_compromiso_ia(req: MensajeRequest):
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

@app.post("/compromisos/ia-audio", tags=["Compromisos"])
async def crear_compromiso_ia_audio(audio: UploadFile = File(...)):
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

@app.post("/compromisos/manual", tags=["Compromisos"])
def crear_compromiso_manual(req: CompromisoManualRequest):
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

@app.put("/compromisos/{comp_id}", tags=["Compromisos"])
def editar_compromiso(comp_id: str, req: CompromisoManualRequest):
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

@app.post("/compromisos/{comp_id}/pagar", tags=["Compromisos"])
def pagar_compromiso(comp_id: str, req: PagoCompromisoRequest = PagoCompromisoRequest()):
    ahora = datetime.now()
    periodo_actual = ahora.strftime("%Y-%m")
    resultado = sheets_client.registrar_pago_compromiso(comp_id, periodo_actual)

    concepto = concepto_pago_compromiso(resultado)
    es_ingreso = resultado.get("flujo", "Egreso").lower() == "ingreso"
    monto_cuota = resultado["monto_cuota"]

    registrar_movimiento_pago(resultado, req.cuenta, monto_cuota, concepto)

    if es_ingreso:
        mensaje = f"✅ Ingreso registrado: {concepto} por +${monto_cuota:,} en {req.cuenta}".replace(",", ".")
    elif resultado["finalizado"]:
        mensaje = f"🎉 ¡Deuda finalizada! Pagaste la última cuota de '{resultado['nombre']}' (${monto_cuota:,}) desde {req.cuenta}."
    else:
        mensaje = f"✅ Pago registrado: {concepto} por ${monto_cuota:,} ({req.cuenta})".replace(",", ".")

    return {"status": "success", "finalizado": resultado["finalizado"], "message": mensaje}

@app.post("/compromisos/{comp_id}/marcar-pagado", tags=["Compromisos"])
def marcar_compromiso_pagado_sin_saldo(comp_id: str):
    """Marca el compromiso como al día en el mes sin registrar egreso ni alterar cuentas."""
    periodo_actual = datetime.now().strftime("%Y-%m")
    resultado = sheets_client.registrar_pago_compromiso(comp_id, periodo_actual)
    mensaje = f"✓ '{resultado['nombre']}' marcado como al día este mes (sin alterar saldos)."
    return {"status": "success", "message": mensaje}

@app.post("/compromisos/{comp_id}/liquidar", tags=["Compromisos"])
def liquidar_compromiso(comp_id: str, req: LiquidarCompromisoRequest = LiquidarCompromisoRequest()):
    """
    Saldar la totalidad de un crédito a cuotas con monto real negociable (descuento de intereses).
    Registra SIEMPRE el Egreso en la cuenta seleccionada y en la hoja de Movimientos.
    """
    ahora = datetime.now()
    periodo_actual = ahora.strftime("%Y-%m")
    resultado = sheets_client.liquidar_compromiso(comp_id, periodo_actual, monto_real=req.monto_real)

    monto_total = resultado["monto_liquidacion"]
    cuotas_restantes = resultado.get("cuotas_restantes", 0)
    concepto = f"Liquidación total: {resultado['nombre']} ({cuotas_restantes} cuotas)"

    # Registrar movimiento de Egreso en la hoja de Movimientos y descontar de cuenta
    rec_id = registrar_movimiento_pago(resultado, req.cuenta, monto_total, concepto)

    descuento_msg = ""
    monto_teorico = resultado.get("monto_teorico", monto_total)
    if monto_teorico > monto_total:
        ahorro = monto_teorico - monto_total
        descuento_msg = f" (¡Ahorraste ${ahorro:,} COP en intereses!)".replace(",", ".")

    mensaje = f"🎉 ¡Deuda liquidada al 100%! Se registró el egreso de '{resultado['nombre']}' por ${monto_total:,} desde {req.cuenta}{descuento_msg}.".replace(",", ".")
    return {
        "status": "success",
        "message": mensaje,
        "data": {
            "record_id": rec_id,
            "monto_pagado": monto_total,
            "cuenta": req.cuenta,
            "finalizado": True
        }
    }

@app.delete("/compromisos/{comp_id}", tags=["Compromisos"])
def eliminar_compromiso(comp_id: str):
    sheets_client.eliminar_compromiso(comp_id)
    return {"status": "success", "message": "Compromiso eliminado correctamente."}
