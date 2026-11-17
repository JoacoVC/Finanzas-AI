from pydantic import BaseModel, Field
from typing import Optional

class MensajeRequest(BaseModel):
    texto: str
    cuenta: str = ""

class TransaccionManualRequest(BaseModel):
    fecha: str
    tipo: str  # "Egreso", "Ingreso", "Traslado"
    categoria: str = "Otros"
    concepto: str
    monto: int
    cuenta: str = "Efectivo"
    cuenta_destino: str = ""  # Para tipo "Traslado"
    presupuesto: int = 0  # Mantenido por retrocompatibilidad opcional

class CompromisoManualRequest(BaseModel):
    nombre: str
    modalidad: str  # "Recurrente", "Cuotas"
    categoria: str = "Deudas"
    monto_cuota: int
    cuotas_totales: int = 0
    cuotas_pagadas: int = 0
    dia_pago: int = 1
    flujo: str = "Egreso"  # "Egreso", "Ingreso"

class CuentaRequest(BaseModel):
    nombre: str
    tipo: str  # "Efectivo", "Banco", "Tarjeta"
    saldo: int = 0
    cupo_total: int = 0
    dia_pago: int = 0  # Día límite de pago para tarjetas (1-31 o 0 si no aplica)

class PagoCompromisoRequest(BaseModel):
    cuenta: str = "Efectivo"

class LiquidarCompromisoRequest(BaseModel):
    cuenta: str = "Efectivo"
    monto_real: Optional[int] = None  # Monto real pagado si hubo descuento de intereses

class PagoTarjetaDirectoRequest(BaseModel):
    cuenta_origen: str = "Efectivo"
    monto: int = 0
    es_total: bool = True
    concepto: str = ""

class TrasladoRequest(BaseModel):
    cuenta_origen: str
    cuenta_destino: str
    monto: int
    concepto: str = ""
