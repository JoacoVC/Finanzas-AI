import os
import json
import uuid
from datetime import datetime
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
from app.core.config import settings

def mes_espanol(mes_num: int) -> str:
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return meses[mes_num - 1]

class SheetsClient:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.sheet = None
        self.compromisos_sheet = None
        self.cuentas_sheet = None
        self._registros_has_presupuesto = False

    def connect(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_env:
            credentials = Credentials.from_service_account_info(
                json.loads(creds_env), scopes=scopes
            )
        elif os.path.exists(settings.google_credentials_path):
            credentials = Credentials.from_service_account_file(
                settings.google_credentials_path, scopes=scopes
            )
        else:
            raise FileNotFoundError(f"Falta el archivo: {settings.google_credentials_path}")

        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(settings.sheet_id)

        # 1. Asegurar o crear la hoja principal de Movimientos
        try:
            self.sheet = self.spreadsheet.worksheet(settings.worksheet_name)
        except gspread.WorksheetNotFound:
            self.sheet = self.spreadsheet.add_worksheet(title=settings.worksheet_name, rows=500, cols=12)

        # Autogenerar encabezados en la hoja de Movimientos si está vacía
        filas_mov = self.sheet.get_all_values()
        if not filas_mov:
            encabezados_mov = ["Fecha", "Mes", "Anio", "Tipo", "Categoria", "Concepto", "Monto", "ID", "Cuenta", "CuentaDestino"]
            self.sheet.append_row(encabezados_mov, value_input_option="USER_ENTERED")
            self._registros_has_presupuesto = False
        else:
            header = [h.strip().lower() for h in filas_mov[0]]
            self._registros_has_presupuesto = ("presupuesto" in header)

        # 2. Inicializar hojas de Cuentas y Compromisos (autogenerando si faltan)
        self._get_cuentas_sheet()
        self._get_compromisos_sheet()

        return self.sheet

    def _limpiar_numero(self, val) -> int:
        limpio = str(val).replace("$", "").replace(",", "").replace(".", "").strip()
        try:
            return int(float(limpio)) if limpio else 0
        except ValueError:
            return 0

    # --- HOJA DE CUENTAS Y TARJETAS DE CRÉDITO ---

    def _asegurar_conexion(self):
        self._asegurar_conexion()

    def _buscar_cuenta(self, nombre: str, tipo: Optional[str] = None, liquida: bool = False, parcial: bool = False) -> Optional[dict]:
        """
        Busca una cuenta por nombre sin distinguir mayúsculas.
        - tipo: exige ese tipo exacto ("Tarjeta", "Banco", ...).
        - liquida=True: solo cuentas líquidas (excluye tarjetas).
        - parcial=True: acepta coincidencia parcial (el nombre contiene el texto).
        """
        objetivo = (nombre or "").strip().lower()
        if not objetivo:
            return None

        def coincide(c: dict) -> bool:
            if tipo and c["tipo"] != tipo:
                return False
            if liquida and c["tipo"] == "Tarjeta":
                return False
            nombre_c = c["nombre"].lower()
            return objetivo in nombre_c if parcial else objetivo == nombre_c

        return next((c for c in self.listar_cuentas() if coincide(c)), None)

    def _get_cuentas_sheet(self):
        if self.spreadsheet is None:
            self.connect()
        if self.cuentas_sheet is None:
            try:
                self.cuentas_sheet = self.spreadsheet.worksheet("Cuentas")
            except gspread.WorksheetNotFound:
                self.cuentas_sheet = self.spreadsheet.add_worksheet(title="Cuentas", rows=50, cols=8)
            
            filas = self.cuentas_sheet.get_all_values()
            if not filas:
                encabezados = ["ID", "Nombre", "Tipo", "Saldo", "CupoTotal", "DiaPago"]
                self.cuentas_sheet.append_row(encabezados, value_input_option="USER_ENTERED")
                self.cuentas_sheet.append_row([str(uuid.uuid4())[:8], "Efectivo", "Efectivo", 0, 0, 0], value_input_option="USER_ENTERED")
        return self.cuentas_sheet

    def listar_cuentas(self) -> list:
        ws = self._get_cuentas_sheet()
        filas = ws.get_all_values()
        if len(filas) <= 1:
            return []
        cuentas = []
        for idx, fila in enumerate(filas[1:], start=2):
            if not fila or not fila[0].strip():
                continue
            tipo = fila[2].strip() if len(fila) > 2 else "Efectivo"
            saldo = self._limpiar_numero(fila[3]) if len(fila) > 3 else 0
            cupo_total = self._limpiar_numero(fila[4]) if len(fila) > 4 else 0
            dia_pago = self._limpiar_numero(fila[5]) if len(fila) > 5 else 0

            # En Tarjeta de Crédito: saldo = deuda usada actual; cupo_disponible = cupo_total - saldo
            cupo_disponible = max(0, cupo_total - saldo) if tipo == "Tarjeta" else saldo
            cuentas.append({
                "row_index": idx,
                "id": fila[0].strip(),
                "nombre": fila[1].strip(),
                "tipo": tipo,
                "saldo": saldo,
                "cupo_total": cupo_total,
                "cupo_disponible": cupo_disponible,
                "dia_pago": dia_pago
            })
        return cuentas

    def crear_cuenta(self, nombre: str, tipo: str, saldo: int, cupo_total: int = 0, dia_pago: int = 0) -> dict:
        ws = self._get_cuentas_sheet()
        cuenta_id = str(uuid.uuid4())[:8]
        cupo = cupo_total if tipo == "Tarjeta" else 0
        dia = dia_pago if tipo == "Tarjeta" else 0
        ws.append_row([cuenta_id, nombre, tipo, saldo, cupo, dia], value_input_option="USER_ENTERED")
        return {
            "id": cuenta_id, "nombre": nombre, "tipo": tipo,
            "saldo": saldo, "cupo_total": cupo,
            "cupo_disponible": max(0, cupo - saldo) if tipo == "Tarjeta" else saldo,
            "dia_pago": dia
        }

    def actualizar_cuenta(self, cuenta_id: str, nombre: str, tipo: str, saldo: int, cupo_total: int, dia_pago: int = 0):
        ws = self._get_cuentas_sheet()
        cuentas = self.listar_cuentas()
        obj = next((c for c in cuentas if c["id"] == cuenta_id), None)
        if not obj:
            raise ValueError("Cuenta no encontrada.")
        cupo = cupo_total if tipo == "Tarjeta" else 0
        dia = dia_pago if tipo == "Tarjeta" else 0
        ws.update(f"B{obj['row_index']}:F{obj['row_index']}", [[nombre, tipo, saldo, cupo, dia]], value_input_option="USER_ENTERED")

    def eliminar_cuenta(self, cuenta_id: str):
        ws = self._get_cuentas_sheet()
        cuentas = self.listar_cuentas()
        obj = next((c for c in cuentas if c["id"] == cuenta_id), None)
        if not obj:
            raise ValueError("Cuenta no encontrada.")
        ws.delete_rows(obj["row_index"])

    def ajustar_saldo_cuenta(self, nombre_cuenta: str, tipo_movimiento: str, monto: int):
        if not nombre_cuenta or monto <= 0:
            return
        ws = self._get_cuentas_sheet()
        obj = self._buscar_cuenta(nombre_cuenta)
        if not obj:
            return

        es_ingreso = tipo_movimiento.lower() == "ingreso"
        if obj["tipo"] == "Tarjeta":
            # Egreso con tarjeta aumenta deuda usada; Ingreso/abono reduce deuda usada
            nuevo_saldo = max(0, obj["saldo"] - monto) if es_ingreso else (obj["saldo"] + monto)
        else:
            # Efectivo o Banco
            nuevo_saldo = (obj["saldo"] + monto) if es_ingreso else (obj["saldo"] - monto)

        ws.update(f"D{obj['row_index']}", [[nuevo_saldo]], value_input_option="USER_ENTERED")

    def transferir_entre_cuentas(self, cuenta_origen: str, cuenta_destino: str, monto: int, concepto: str = "") -> dict:
        """
        Traslado entre dos cuentas propias.
        Resta monto de cuenta origen y suma monto a cuenta destino.
        NO es ingreso ni egreso (tipo = 'Traslado').
        """
        self._asegurar_conexion()
        ws = self._get_cuentas_sheet()

        src = self._buscar_cuenta(cuenta_origen)
        dst = self._buscar_cuenta(cuenta_destino)

        if not src or not dst:
            raise ValueError(f"Cuentas no válidas para traslado ({cuenta_origen} -> {cuenta_destino}).")

        if src["nombre"].lower() == dst["nombre"].lower():
            raise ValueError("La cuenta de origen y de destino no pueden ser la misma.")

        # Si el destino es Tarjeta de Crédito, redirigir a pagar_tarjeta (no es un simple traslado, es pago de deuda)
        if dst["tipo"] == "Tarjeta":
            return self.pagar_tarjeta(
                nombre_tarjeta=dst["nombre"],
                cuenta_origen=src["nombre"],
                monto=monto,
                es_total=False,
                concepto=concepto or f"Pago tarjeta {dst['nombre']} desde {src['nombre']}"
            )

        # 1. Descontar de cuenta origen
        if src["tipo"] == "Tarjeta":
            nuevo_src = src["saldo"] + monto
        else:
            nuevo_src = src["saldo"] - monto
        ws.update(f"D{src['row_index']}", [[nuevo_src]], value_input_option="USER_ENTERED")

        # 2. Sumar a cuenta destino
        nuevo_dst = dst["saldo"] + monto
        ws.update(f"D{dst['row_index']}", [[nuevo_dst]], value_input_option="USER_ENTERED")

        # 3. Registrar movimiento con Tipo = 'Traslado'
        ahora = datetime.now()
        concepto_final = concepto.strip() or f"Traslado de {src['nombre']} a {dst['nombre']}"
        record_id = str(uuid.uuid4())[:8]

        self._insert_movimiento_fila(
            fecha_str=ahora.strftime("%d/%m/%Y"),
            mes=mes_espanol(ahora.month),
            anio=ahora.year,
            tipo="Traslado",
            categoria="Traslado",
            concepto=concepto_final,
            monto=monto,
            record_id=record_id,
            cuenta=src["nombre"],
            cuenta_destino=dst["nombre"]
        )

        return {
            "accion": "traslado",
            "origen": src["nombre"],
            "destino": dst["nombre"],
            "monto": monto,
            "record_id": record_id,
            "mensaje": f"🔁 Traslado completado: ${monto:,} COP de {src['nombre']} a {dst['nombre']}.".replace(",", ".")
        }

    def pagar_tarjeta(self, nombre_tarjeta: str, cuenta_origen: str, monto: int = 0, es_total: bool = False, concepto: str = "") -> dict:
        """
        Pago total o abono a una tarjeta de crédito.
        Resta saldo de la cuenta líquida de origen y reduce la deuda viva de la tarjeta.
        Registra un movimiento de tipo 'Egreso' en la categoría 'Deudas'.
        """
        self._asegurar_conexion()
        ws = self._get_cuentas_sheet()

        tarjeta = (self._buscar_cuenta(nombre_tarjeta, tipo="Tarjeta")
                   or self._buscar_cuenta(nombre_tarjeta, tipo="Tarjeta", parcial=True)
                   or self._buscar_cuenta(nombre_tarjeta))
        if not tarjeta:
            tarjetas_disp = [c["nombre"] for c in self.listar_cuentas() if c["tipo"] == "Tarjeta"]
            raise ValueError(f"No se encontró la tarjeta '{nombre_tarjeta}'. Disponibles: {', '.join(tarjetas_disp) if tarjetas_disp else 'Ninguna'}")

        # Buscar cuenta de origen (líquida)
        cuenta_src = self._buscar_cuenta(cuenta_origen, liquida=True) if cuenta_origen else None
        if not cuenta_src:
            cuenta_src = self._buscar_cuenta(cuenta_origen, liquida=True, parcial=True)

        if not cuenta_src:
            cuenta_src = next((c for c in self.listar_cuentas() if c["tipo"] != "Tarjeta"), None)

        nombre_src = cuenta_src["nombre"] if cuenta_src else "Efectivo"
        saldo_deuda_actual = tarjeta["saldo"]

        if es_total or monto <= 0:
            monto_pago = saldo_deuda_actual
        else:
            monto_pago = min(monto, saldo_deuda_actual) if saldo_deuda_actual > 0 else monto

        if monto_pago <= 0 and saldo_deuda_actual == 0:
            return {
                "tarjeta": tarjeta["nombre"],
                "cuenta_origen": nombre_src,
                "monto_pagado": 0,
                "saldo_restante_tarjeta": 0,
                "mensaje": f"La tarjeta {tarjeta['nombre']} ya tiene saldo en cero ($0 deuda)."
            }

        # 1. Actualizar saldo usado en Tarjeta
        nuevo_saldo_tarjeta = max(0, saldo_deuda_actual - monto_pago)
        ws.update(f"D{tarjeta['row_index']}", [[nuevo_saldo_tarjeta]], value_input_option="USER_ENTERED")

        # 2. Descontar dinero de la cuenta origen
        if cuenta_src:
            nuevo_saldo_src = cuenta_src["saldo"] - monto_pago
            ws.update(f"D{cuenta_src['row_index']}", [[nuevo_saldo_src]], value_input_option="USER_ENTERED")

        # 3. Registrar movimiento de Egreso en la hoja de Movimientos
        ahora = datetime.now()
        es_liquidacion = (es_total or nuevo_saldo_tarjeta == 0)
        concepto_final = concepto.strip() if concepto.strip() else (
            f"Pago total tarjeta {tarjeta['nombre']} con {nombre_src}" if es_liquidacion
            else f"Abono tarjeta {tarjeta['nombre']} con {nombre_src}"
        )

        record_id = str(uuid.uuid4())[:8]
        self._insert_movimiento_fila(
            fecha_str=ahora.strftime("%d/%m/%Y"),
            mes=mes_espanol(ahora.month),
            anio=ahora.year,
            tipo="Egreso",
            categoria="Deudas",
            concepto=concepto_final,
            monto=monto_pago,
            record_id=record_id,
            cuenta=nombre_src,
            cuenta_destino=tarjeta["nombre"]
        )

        msg = (
            f"💳 Pago total completado: Se saldó la tarjeta {tarjeta['nombre']} (${monto_pago:,} COP) y su deuda quedó en $0. Descontado de {nombre_src}."
            if es_liquidacion
            else f"💳 Abono completado: Se pagaron ${monto_pago:,} COP a la tarjeta {tarjeta['nombre']}. Deuda restante: ${nuevo_saldo_tarjeta:,} COP. Descontado de {nombre_src}."
        ).replace(",", ".")

        return {
            "tarjeta": tarjeta["nombre"],
            "cuenta_origen": nombre_src,
            "monto_pagado": monto_pago,
            "saldo_restante_tarjeta": nuevo_saldo_tarjeta,
            "record_id": record_id,
            "concepto": concepto_final,
            "mensaje": msg
        }

    # --- MÉTODOS DE LA HOJA DE MOVIMIENTOS ---

    def _insert_movimiento_fila(self, fecha_str: str, mes: str, anio: int, tipo: str, categoria: str, concepto: str, monto: int, record_id: str, cuenta: str, cuenta_destino: str = ""):
        self._asegurar_conexion()

        # Si la hoja tiene columna 'Presupuesto' (formato anterior):
        # [Fecha, Mes, Anio, Tipo, Categoria, Concepto, Presupuesto, Monto, ID, Cuenta, CuentaDestino]
        # Si ya es el nuevo formato:
        # [Fecha, Mes, Anio, Tipo, Categoria, Concepto, Monto, ID, Cuenta, CuentaDestino]
        if self._registros_has_presupuesto:
            fila = [fecha_str, mes, anio, tipo, categoria, concepto, 0, monto, record_id, cuenta, cuenta_destino]
        else:
            fila = [fecha_str, mes, anio, tipo, categoria, concepto, monto, record_id, cuenta, cuenta_destino]

        self.sheet.append_row(fila, value_input_option="USER_ENTERED")

    def append_record(self, record_data: list, cuenta: str = "Efectivo", cuenta_destino: str = "") -> str:
        """
        Inserta un nuevo movimiento manual o de IA.
        record_data esperado: [Fecha, Mes, Anio, Tipo, Categoria, Concepto, Monto]
        """
        self._asegurar_conexion()

        record_id = str(uuid.uuid4())[:8]
        tipo_mov = record_data[3]
        monto = int(record_data[6]) if len(record_data) == 7 else int(record_data[7])

        if tipo_mov.lower() == "traslado":
            # Es un traslado manual
            self.transferir_entre_cuentas(
                cuenta_origen=cuenta,
                cuenta_destino=cuenta_destino or "Efectivo",
                monto=monto,
                concepto=record_data[5]
            )
            return record_id

        # Para Ingreso o Egreso
        self._insert_movimiento_fila(
            fecha_str=record_data[0],
            mes=record_data[1],
            anio=record_data[2],
            tipo=tipo_mov,
            categoria=record_data[4],
            concepto=record_data[5],
            monto=monto,
            record_id=record_id,
            cuenta=cuenta,
            cuenta_destino=cuenta_destino
        )

        # Ajustar saldo en la cuenta afectada
        self.ajustar_saldo_cuenta(cuenta, tipo_mov, monto)
        return record_id

    def get_all_records(self) -> list:
        self._asegurar_conexion()

        filas = self.sheet.get_all_values()
        if len(filas) <= 1:
            return []

        # Determinar si la primera fila contiene 'presupuesto'
        headers = [h.strip().lower() for h in filas[0]]
        has_ppto = ("presupuesto" in headers)
        self._registros_has_presupuesto = has_ppto

        registros = []
        for idx, fila in enumerate(filas[1:], start=2):
            if not fila or not fila[0].strip():
                continue

            if has_ppto:
                # Estructura antigua:
                # 0: Fecha, 1: Mes, 2: Anio, 3: Tipo, 4: Categoria, 5: Concepto, 6: Ppto, 7: Monto, 8: ID, 9: Cuenta, 10: CuentaDestino
                monto = self._limpiar_numero(fila[7]) if len(fila) > 7 else 0
                rec_id = fila[8].strip() if len(fila) > 8 and fila[8].strip() else f"row_{idx}"
                cuenta = fila[9].strip() if len(fila) > 9 and fila[9].strip() else "Efectivo"
                cuenta_dst = fila[10].strip() if len(fila) > 10 else ""
            else:
                # Estructura nueva (sin presupuesto):
                # 0: Fecha, 1: Mes, 2: Anio, 3: Tipo, 4: Categoria, 5: Concepto, 6: Monto, 7: ID, 8: Cuenta, 9: CuentaDestino
                monto = self._limpiar_numero(fila[6]) if len(fila) > 6 else 0
                rec_id = fila[7].strip() if len(fila) > 7 and fila[7].strip() else f"row_{idx}"
                cuenta = fila[8].strip() if len(fila) > 8 and fila[8].strip() else "Efectivo"
                cuenta_dst = fila[9].strip() if len(fila) > 9 else ""

            registros.append({
                "row_index": idx,
                "fecha": fila[0] if len(fila) > 0 else "",
                "mes": fila[1] if len(fila) > 1 else "",
                "anio": fila[2] if len(fila) > 2 else "",
                "tipo": fila[3] if len(fila) > 3 else "Egreso",
                "categoria": fila[4] if len(fila) > 4 else "Otros",
                "concepto": fila[5] if len(fila) > 5 else "",
                "monto": monto,
                "id": rec_id,
                "cuenta": cuenta,
                "cuenta_destino": cuenta_dst
            })

        return registros

    def _buscar_fila_transaccion(self, record_id: str) -> dict:
        registros = self.get_all_records()
        objetivo = next((r for r in registros if r["id"] == record_id), None)
        if not objetivo:
            raise ValueError("Transacción no encontrada en Google Sheets.")
        return objetivo

    def update_record(self, record_id: str, updated_data: list, cuenta: str = "Efectivo", cuenta_destino: str = ""):
        objetivo = self._buscar_fila_transaccion(record_id)
        row_idx = objetivo["row_index"]

        # Revertir saldo anterior si no era traslado
        if objetivo["tipo"].lower() != "traslado":
            tipo_ant = "Ingreso" if objetivo["tipo"].lower() == "egreso" else "Egreso"
            self.ajustar_saldo_cuenta(objetivo["cuenta"], tipo_ant, objetivo["monto"])

        # Aplicar nuevo impacto
        nuevo_tipo = updated_data[3]
        nuevo_monto = int(updated_data[6]) if len(updated_data) == 7 else int(updated_data[7])
        if nuevo_tipo.lower() != "traslado":
            self.ajustar_saldo_cuenta(cuenta, nuevo_tipo, nuevo_monto)

        final_id = record_id if not record_id.startswith("row_") else str(uuid.uuid4())[:8]

        if self._registros_has_presupuesto:
            fila_completa = [
                updated_data[0], updated_data[1], updated_data[2],
                nuevo_tipo, updated_data[4], updated_data[5],
                0, nuevo_monto, final_id, cuenta, cuenta_destino
            ]
            self.sheet.update(f"A{row_idx}:K{row_idx}", [fila_completa], value_input_option="USER_ENTERED")
        else:
            fila_completa = [
                updated_data[0], updated_data[1], updated_data[2],
                nuevo_tipo, updated_data[4], updated_data[5],
                nuevo_monto, final_id, cuenta, cuenta_destino
            ]
            self.sheet.update(f"A{row_idx}:J{row_idx}", [fila_completa], value_input_option="USER_ENTERED")

    def delete_record(self, record_id: str):
        objetivo = self._buscar_fila_transaccion(record_id)
        if objetivo["tipo"].lower() != "traslado":
            tipo_inv = "Ingreso" if objetivo["tipo"].lower() == "egreso" else "Egreso"
            self.ajustar_saldo_cuenta(objetivo["cuenta"], tipo_inv, objetivo["monto"])
        self.sheet.delete_rows(objetivo["row_index"])

    # --- HOJA DE COMPROMISOS (DEUDAS A CUOTAS Y PAGOS RECURRENTES) ---

    def _get_compromisos_sheet(self):
        if self.spreadsheet is None:
            self.connect()
        if self.compromisos_sheet is None:
            try:
                self.compromisos_sheet = self.spreadsheet.worksheet("Compromisos")
            except gspread.WorksheetNotFound:
                self.compromisos_sheet = self.spreadsheet.add_worksheet(title="Compromisos", rows=200, cols=12)

            filas = self.compromisos_sheet.get_all_values()
            if not filas:
                encabezados = [
                    "ID", "Nombre", "Modalidad", "Categoria", "MontoCuota",
                    "CuotasTotales", "CuotasPagadas", "UltimoMesPagado", "Estado",
                    "DiaPago", "Flujo"
                ]
                self.compromisos_sheet.append_row(encabezados, value_input_option="USER_ENTERED")
        return self.compromisos_sheet

    def crear_compromiso(self, nombre: str, modalidad: str, categoria: str, monto_cuota: int, cuotas_totales: int = 0, dia_pago: int = 1, flujo: str = "Egreso") -> dict:
        ws = self._get_compromisos_sheet()
        comp_id = str(uuid.uuid4())[:8]
        dia = max(1, min(31, int(dia_pago or 1)))
        flujo_val = "Ingreso" if flujo.lower() == "ingreso" else "Egreso"
        fila = [
            comp_id, nombre, modalidad, categoria, monto_cuota,
            cuotas_totales, 0, "", "Activo", dia, flujo_val
        ]
        ws.append_row(fila, value_input_option="USER_ENTERED")
        return {
            "id": comp_id, "nombre": nombre, "modalidad": modalidad,
            "categoria": categoria, "monto_cuota": monto_cuota,
            "cuotas_totales": cuotas_totales, "cuotas_pagadas": 0,
            "ultimo_mes_pagado": "", "estado": "Activo",
            "dia_pago": dia, "flujo": flujo_val
        }

    def listar_compromisos_activos(self) -> list:
        ws = self._get_compromisos_sheet()
        filas = ws.get_all_values()
        if len(filas) <= 1:
            return []

        activos = []
        for idx, fila in enumerate(filas[1:], start=2):
            if not fila or len(fila) < 9:
                continue
            estado = fila[8].strip()
            if estado != "Activo":
                continue

            dia_pago = int(float(fila[9])) if len(fila) > 9 and fila[9].strip() else 1
            flujo = fila[10].strip() if len(fila) > 10 and fila[10].strip() else "Egreso"

            activos.append({
                "row_index": idx,
                "id": fila[0],
                "nombre": fila[1],
                "modalidad": fila[2],
                "categoria": fila[3],
                "monto_cuota": self._limpiar_numero(fila[4]),
                "cuotas_totales": int(float(fila[5] or 0)),
                "cuotas_pagadas": int(float(fila[6] or 0)),
                "ultimo_mes_pagado": fila[7],
                "estado": estado,
                "dia_pago": dia_pago,
                "flujo": flujo
            })
        return sorted(activos, key=lambda x: x["dia_pago"])

    def actualizar_compromiso(self, comp_id: str, nombre: str, modalidad: str, categoria: str, monto_cuota: int, cuotas_totales: int, cuotas_pagadas: int, dia_pago: int = 1, flujo: str = "Egreso"):
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado.")

        row_idx = objetivo["row_index"]
        cuotas_tot = cuotas_totales if modalidad == "Cuotas" else 0
        cuotas_pag = min(cuotas_pagadas, cuotas_tot) if modalidad == "Cuotas" else cuotas_pagadas
        estado = "Finalizado" if (modalidad == "Cuotas" and cuotas_tot > 0 and cuotas_pag >= cuotas_tot) else "Activo"
        dia = max(1, min(31, int(dia_pago or 1)))
        flujo_val = "Ingreso" if flujo.lower() == "ingreso" else "Egreso"

        ws.update(
            f"B{row_idx}:K{row_idx}",
            [[nombre, modalidad, categoria, monto_cuota, cuotas_tot, cuotas_pag, objetivo["ultimo_mes_pagado"], estado, dia, flujo_val]],
            value_input_option="USER_ENTERED"
        )

    def registrar_pago_compromiso(self, comp_id: str, periodo_actual: str) -> dict:
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado o ya finalizado.")

        nuevas_pagadas = objetivo["cuotas_pagadas"] + 1
        finalizado = False
        nuevo_estado = "Activo"

        if objetivo["modalidad"] == "Cuotas" and objetivo["cuotas_totales"] > 0:
            if nuevas_pagadas >= objetivo["cuotas_totales"]:
                finalizado = True
                nuevo_estado = "Finalizado"

        row_idx = objetivo["row_index"]
        ws.update(f"G{row_idx}:I{row_idx}", [[nuevas_pagadas, periodo_actual, nuevo_estado]])

        objetivo["cuotas_pagadas"] = nuevas_pagadas
        objetivo["ultimo_mes_pagado"] = periodo_actual
        objetivo["estado"] = nuevo_estado
        objetivo["finalizado"] = finalizado
        return objetivo

    def liquidar_compromiso(self, comp_id: str, periodo_actual: str, monto_real: Optional[int] = None) -> dict:
        """
        Saldar crédito a cuotas por completo.
        Permite ingresar el monto real acordado (descuento de intereses).
        Marca todas las cuotas como pagadas y estado = 'Finalizado'.
        """
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado o ya finalizado.")
        if objetivo["modalidad"] != "Cuotas" or objetivo["cuotas_totales"] <= 0:
            raise ValueError("Solo se pueden liquidar deudas con un número de cuotas definido.")

        cuotas_restantes = max(1, objetivo["cuotas_totales"] - objetivo["cuotas_pagadas"])
        monto_teorico = cuotas_restantes * objetivo["monto_cuota"]
        monto_final = monto_real if (monto_real is not None and monto_real > 0) else monto_teorico

        row_idx = objetivo["row_index"]
        ws.update(f"G{row_idx}:I{row_idx}", [[objetivo["cuotas_totales"], periodo_actual, "Finalizado"]])

        objetivo["cuotas_restantes"] = cuotas_restantes
        objetivo["monto_teorico"] = monto_teorico
        objetivo["monto_liquidacion"] = monto_final
        objetivo["cuotas_pagadas"] = objetivo["cuotas_totales"]
        objetivo["estado"] = "Finalizado"
        return objetivo

    def eliminar_compromiso(self, comp_id: str):
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado.")
        ws.delete_rows(obj_idx := objetivo["row_index"])

    def obtener_resumen_deudas(self) -> dict:
        cuentas = self.listar_cuentas()
        compromisos = self.listar_compromisos_activos()

        tarjetas = [c for c in cuentas if c["tipo"] == "Tarjeta"]
        total_deuda_tarjetas = sum(t["saldo"] for t in tarjetas)

        deudas_cuotas = [c for c in compromisos if c.get("modalidad") == "Cuotas" and (c.get("flujo") or "Egreso") == "Egreso"]
        total_deuda_cuotas = sum(
            max(0, c["cuotas_totales"] - c["cuotas_pagadas"]) * c["monto_cuota"]
            for c in deudas_cuotas
        )

        return {
            "total_deuda_global": total_deuda_tarjetas + total_deuda_cuotas,
            "total_deuda_tarjetas": total_deuda_tarjetas,
            "total_deuda_cuotas": total_deuda_cuotas,
            "tarjetas": tarjetas,
            "deudas_cuotas": deudas_cuotas
        }

    def obtener_contexto_financiero(self) -> str:
        cuentas = self.listar_cuentas()
        compromisos = self.listar_compromisos_activos()

        lineas = ["ESTADO FINANCIERO Y CUENTAS DISPONIBLES:"]

        liquidas = [c for c in cuentas if c["tipo"] != "Tarjeta"]
        if liquidas:
            lineas.append("- Cuentas de dinero disponible / efectivo:")
            for c in liquidas:
                lineas.append(f"  * {c['nombre']} ({c['tipo']}): Saldo disponible ${c['saldo']:,} COP".replace(",", "."))
        else:
            lineas.append("- Cuentas de dinero disponible: Efectivo ($0)")

        tarjetas = [c for c in cuentas if c["tipo"] == "Tarjeta"]
        if tarjetas:
            lineas.append("- Tarjetas de Crédito (Deudas / Cupo usado):")
            for t in tarjetas:
                lineas.append(
                    f"  * {t['nombre']}: Deuda actual (saldo usado) = ${t['saldo']:,} COP | Cupo disponible = ${t['cupo_disponible']:,} COP | Cupo total = ${t['cupo_total']:,} COP | Día límite pago: {t.get('dia_pago', 0)}".replace(",", ".")
                )
        else:
            lineas.append("- Tarjetas de crédito registradas: Ninguna.")

        if compromisos:
            lineas.append("- Deudas a cuotas y pagos recurrentes activos:")
            for comp in compromisos:
                flujo = comp.get("flujo", "Egreso")
                if comp.get("modalidad") == "Cuotas":
                    restantes = max(0, comp["cuotas_totales"] - comp["cuotas_pagadas"])
                    saldo_deuda = restantes * comp["monto_cuota"]
                    lineas.append(
                        f"  * {comp['nombre']} (Deuda a Cuotas): Cuota mensual ${comp['monto_cuota']:,} COP ({comp['cuotas_pagadas']}/{comp['cuotas_totales']} pagadas, deuda restante ${saldo_deuda:,} COP)".replace(",", ".")
                    )
                else:
                    lineas.append(
                        f"  * {comp['nombre']} ({flujo} Recurrente): ${comp['monto_cuota']:,} COP (Día {comp.get('dia_pago', 1)} del mes)".replace(",", ".")
                    )

        return "\n".join(lineas)

sheets_client = SheetsClient()
