import os
import json
import uuid
import gspread
from google.oauth2.service_account import Credentials
from app.core.config import settings

class SheetsClient:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.sheet = None
        self.compromisos_sheet = None
        self.cuentas_sheet = None

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
        self.sheet = self.spreadsheet.worksheet(settings.worksheet_name)
        return self.sheet

    def _limpiar_numero(self, val) -> int:
        limpio = str(val).replace("$", "").replace(",", "").replace(".", "").strip()
        try:
            return int(float(limpio)) if limpio else 0
        except ValueError:
            return 0

    # --- HOJA DE CUENTAS Y TARJETAS DE CRÉDITO ---

    def _get_cuentas_sheet(self):
        if self.spreadsheet is None:
            self.connect()
        if self.cuentas_sheet is None:
            try:
                self.cuentas_sheet = self.spreadsheet.worksheet("Cuentas")
            except gspread.WorksheetNotFound:
                self.cuentas_sheet = self.spreadsheet.add_worksheet(title="Cuentas", rows=50, cols=8)
                encabezados = ["ID", "Nombre", "Tipo", "Saldo", "CupoTotal"]
                self.cuentas_sheet.append_row(encabezados, value_input_option="USER_ENTERED")
                self.cuentas_sheet.append_row([str(uuid.uuid4())[:8], "Efectivo", "Efectivo", 0, 0], value_input_option="USER_ENTERED")
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
            # En Tarjeta de Crédito: saldo = deuda usada actual; cupo_disponible = cupo_total - saldo
            cupo_disponible = max(0, cupo_total - saldo) if tipo == "Tarjeta" else saldo
            cuentas.append({
                "row_index": idx,
                "id": fila[0].strip(),
                "nombre": fila[1].strip(),
                "tipo": tipo,
                "saldo": saldo,
                "cupo_total": cupo_total,
                "cupo_disponible": cupo_disponible
            })
        return cuentas

    def crear_cuenta(self, nombre: str, tipo: str, saldo: int, cupo_total: int = 0) -> dict:
        ws = self._get_cuentas_sheet()
        cuenta_id = str(uuid.uuid4())[:8]
        cupo = cupo_total if tipo == "Tarjeta" else 0
        ws.append_row([cuenta_id, nombre, tipo, saldo, cupo], value_input_option="USER_ENTERED")
        return {
            "id": cuenta_id, "nombre": nombre, "tipo": tipo,
            "saldo": saldo, "cupo_total": cupo,
            "cupo_disponible": max(0, cupo - saldo) if tipo == "Tarjeta" else saldo
        }

    def actualizar_cuenta(self, cuenta_id: str, nombre: str, tipo: str, saldo: int, cupo_total: int):
        ws = self._get_cuentas_sheet()
        cuentas = self.listar_cuentas()
        obj = next((c for c in cuentas if c["id"] == cuenta_id), None)
        if not obj:
            raise ValueError("Cuenta no encontrada.")
        cupo = cupo_total if tipo == "Tarjeta" else 0
        ws.update(f"B{obj['row_index']}:E{obj['row_index']}", [[nombre, tipo, saldo, cupo]], value_input_option="USER_ENTERED")

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
        cuentas = self.listar_cuentas()
        obj = next((c for c in cuentas if c["nombre"].lower() == nombre_cuenta.lower()), None)
        if not obj:
            return

        es_ingreso = tipo_movimiento.lower() == "ingreso"
        nuevo_saldo = obj["saldo"]
        if obj["tipo"] == "Tarjeta":
            # Egreso con tarjeta aumenta lo usado; Ingreso/abono a tarjeta reduce lo usado
            nuevo_saldo = max(0, obj["saldo"] - monto) if es_ingreso else (obj["saldo"] + monto)
        else:
            # Efectivo o Cuenta bancaria
            nuevo_saldo = (obj["saldo"] + monto) if es_ingreso else (obj["saldo"] - monto)

        ws.update(f"D{obj['row_index']}", [[nuevo_saldo]], value_input_option="USER_ENTERED")

    # --- HOJA DE COMPROMISOS (DEUDAS, PAGOS E INGRESOS RECURRENTES) ---

    def _get_compromisos_sheet(self):
        if self.spreadsheet is None:
            self.connect()
        if self.compromisos_sheet is None:
            try:
                self.compromisos_sheet = self.spreadsheet.worksheet("Compromisos")
            except gspread.WorksheetNotFound:
                self.compromisos_sheet = self.spreadsheet.add_worksheet(title="Compromisos", rows=200, cols=12)
                encabezados = [
                    "ID", "Nombre", "Modalidad", "Categoria", "MontoCuota",
                    "CuotasTotales", "CuotasPagadas", "UltimoMesPagado", "Estado",
                    "DiaPago", "Flujo"
                ]
                self.compromisos_sheet.append_row(encabezados, value_input_option="USER_ENTERED")
        return self.compromisos_sheet

    # --- MÉTODOS DE TRANSACCIONES (HOJA PRINCIPAL) ---

    def append_record(self, record_data: list, cuenta: str = "Efectivo"):
        if self.sheet is None:
            self.connect()
        
        record_id = str(uuid.uuid4())[:8]
        # Estructura A:J -> Fecha, Mes, Anio, Tipo, Categoria, Concepto, Presupuesto, Monto, ID, Cuenta
        row_to_insert = record_data + [record_id, cuenta]
        self.sheet.append_row(row_to_insert, value_input_option="USER_ENTERED")

        # Ajustar saldo en hoja Cuentas
        tipo_mov = record_data[3]
        monto = int(record_data[7])
        self.ajustar_saldo_cuenta(cuenta, tipo_mov, monto)
        return record_id

    def get_all_records(self) -> list:
        if self.sheet is None:
            self.connect()
        
        filas = self.sheet.get_all_values()
        if len(filas) <= 1:
            return []

        registros = []
        for idx, fila in enumerate(filas[1:], start=2):
            if not fila or not fila[0].strip():
                continue

            rec_id = fila[8].strip() if len(fila) > 8 and fila[8].strip() else f"row_{idx}"
            cuenta = fila[9].strip() if len(fila) > 9 and fila[9].strip() else "Efectivo"

            registros.append({
                "row_index": idx,
                "fecha": fila[0] if len(fila) > 0 else "",
                "mes": fila[1] if len(fila) > 1 else "",
                "anio": fila[2] if len(fila) > 2 else "",
                "tipo": fila[3] if len(fila) > 3 else "",
                "categoria": fila[4] if len(fila) > 4 else "",
                "concepto": fila[5] if len(fila) > 5 else "",
                "presupuesto": self._limpiar_numero(fila[6]) if len(fila) > 6 else 0,
                "monto": self._limpiar_numero(fila[7]) if len(fila) > 7 else 0,
                "id": rec_id,
                "cuenta": cuenta
            })
        
        return registros

    def _buscar_fila_transaccion(self, record_id: str) -> dict:
        registros = self.get_all_records()
        objetivo = next((r for r in registros if r["id"] == record_id), None)
        if not objetivo:
            raise ValueError("Transacción no encontrada en Google Sheets.")
        return objetivo

    def update_record(self, record_id: str, updated_data: list, cuenta: str = "Efectivo"):
        objetivo = self._buscar_fila_transaccion(record_id)
        # Revertir impacto anterior en cuenta y aplicar el nuevo
        tipo_ant = "Ingreso" if objetivo["tipo"].lower() == "egreso" else "Egreso"
        self.ajustar_saldo_cuenta(objetivo["cuenta"], tipo_ant, objetivo["monto"])
        self.ajustar_saldo_cuenta(cuenta, updated_data[3], int(updated_data[7]))

        row_idx = objetivo["row_index"]
        final_id = record_id if not record_id.startswith("row_") else str(uuid.uuid4())[:8]
        fila_completa = updated_data + [final_id, cuenta]
        self.sheet.update(f"A{row_idx}:J{row_idx}", [fila_completa], value_input_option="USER_ENTERED")

    def delete_record(self, record_id: str):
        objetivo = self._buscar_fila_transaccion(record_id)
        # Revertir impacto en cuenta al eliminar
        tipo_inv = "Ingreso" if objetivo["tipo"].lower() == "egreso" else "Egreso"
        self.ajustar_saldo_cuenta(objetivo["cuenta"], tipo_inv, objetivo["monto"])
        self.sheet.delete_rows(objetivo["row_index"])

    # --- MÉTODOS PARA COMPROMISOS ---

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

    def liquidar_compromiso(self, comp_id: str, periodo_actual: str) -> dict:
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado o ya finalizado.")
        if objetivo["modalidad"] != "Cuotas" or objetivo["cuotas_totales"] <= 0:
            raise ValueError("Solo se pueden liquidar deudas con un número de cuotas definido.")

        cuotas_restantes = max(1, objetivo["cuotas_totales"] - objetivo["cuotas_pagadas"])
        monto_liquidacion = cuotas_restantes * objetivo["monto_cuota"]

        row_idx = objetivo["row_index"]
        ws.update(f"G{row_idx}:I{row_idx}", [[objetivo["cuotas_totales"], periodo_actual, "Finalizado"]])

        objetivo["cuotas_restantes"] = cuotas_restantes
        objetivo["monto_liquidacion"] = monto_liquidacion
        objetivo["cuotas_pagadas"] = objetivo["cuotas_totales"]
        objetivo["estado"] = "Finalizado"
        return objetivo

    def eliminar_compromiso(self, comp_id: str):
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado.")
        ws.delete_rows(objetivo["row_index"])

sheets_client = SheetsClient()