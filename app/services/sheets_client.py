import os
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

    def connect(self):
        if not os.path.exists(settings.google_credentials_path):
            raise FileNotFoundError(f"Falta el archivo: {settings.google_credentials_path}")
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(
            settings.google_credentials_path, scopes=scopes
        )
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(settings.sheet_id)
        self.sheet = self.spreadsheet.worksheet(settings.worksheet_name)
        return self.sheet

    def _get_compromisos_sheet(self):
        if self.spreadsheet is None:
            self.connect()
        if self.compromisos_sheet is None:
            try:
                self.compromisos_sheet = self.spreadsheet.worksheet("Compromisos")
            except gspread.WorksheetNotFound:
                self.compromisos_sheet = self.spreadsheet.add_worksheet(title="Compromisos", rows=200, cols=10)
                encabezados = [
                    "ID", "Nombre", "Modalidad", "Categoria", "MontoCuota",
                    "CuotasTotales", "CuotasPagadas", "UltimoMesPagado", "Estado"
                ]
                self.compromisos_sheet.append_row(encabezados, value_input_option="USER_ENTERED")
        return self.compromisos_sheet

    # --- MÉTODOS DE TRANSACCIONES (HOJA PRINCIPAL) ---

    def append_record(self, record_data: list):
        if self.sheet is None:
            self.connect()
        
        record_id = str(uuid.uuid4())[:8]
        row_to_insert = record_data + [record_id]
        self.sheet.append_row(row_to_insert, value_input_option="USER_ENTERED")
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
            
            def limpiar_numero(val):
                limpio = str(val).replace("$", "").replace(",", "").replace(".", "").strip()
                try:
                    return int(float(limpio)) if limpio else 0
                except ValueError:
                    return 0

            rec_id = fila[8].strip() if len(fila) > 8 and fila[8].strip() else f"row_{idx}"

            registros.append({
                "row_index": idx,
                "fecha": fila[0] if len(fila) > 0 else "",
                "mes": fila[1] if len(fila) > 1 else "",
                "anio": fila[2] if len(fila) > 2 else "",
                "tipo": fila[3] if len(fila) > 3 else "",
                "categoria": fila[4] if len(fila) > 4 else "",
                "concepto": fila[5] if len(fila) > 5 else "",
                "presupuesto": limpiar_numero(fila[6]) if len(fila) > 6 else 0,
                "monto": limpiar_numero(fila[7]) if len(fila) > 7 else 0,
                "id": rec_id
            })
        
        return registros

    def _buscar_fila_transaccion(self, record_id: str) -> dict:
        registros = self.get_all_records()
        objetivo = next((r for r in registros if r["id"] == record_id), None)
        if not objetivo:
            raise ValueError("Transacción no encontrada en Google Sheets.")
        return objetivo

    def update_record(self, record_id: str, updated_data: list):
        objetivo = self._buscar_fila_transaccion(record_id)
        row_idx = objetivo["row_index"]
        final_id = record_id if not record_id.startswith("row_") else str(uuid.uuid4())[:8]
        fila_completa = updated_data + [final_id]
        self.sheet.update(f"A{row_idx}:I{row_idx}", [fila_completa], value_input_option="USER_ENTERED")

    def delete_record(self, record_id: str):
        objetivo = self._buscar_fila_transaccion(record_id)
        self.sheet.delete_rows(objetivo["row_index"])

    # --- MÉTODOS PARA COMPROMISOS Y DEUDAS RECURRENTES ---

    def crear_compromiso(self, nombre: str, modalidad: str, categoria: str, monto_cuota: int, cuotas_totales: int = 0) -> dict:
        ws = self._get_compromisos_sheet()
        comp_id = str(uuid.uuid4())[:8]
        fila = [
            comp_id,
            nombre,
            modalidad,
            categoria,
            monto_cuota,
            cuotas_totales,
            0,
            "",
            "Activo"
        ]
        ws.append_row(fila, value_input_option="USER_ENTERED")
        return {
            "id": comp_id, "nombre": nombre, "modalidad": modalidad,
            "categoria": categoria, "monto_cuota": monto_cuota,
            "cuotas_totales": cuotas_totales, "cuotas_pagadas": 0,
            "ultimo_mes_pagado": "", "estado": "Activo"
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

            activos.append({
                "row_index": idx,
                "id": fila[0],
                "nombre": fila[1],
                "modalidad": fila[2],
                "categoria": fila[3],
                "monto_cuota": int(float(str(fila[4]).replace("$", "").replace(",", "").replace(".", "") or 0)),
                "cuotas_totales": int(float(fila[5] or 0)),
                "cuotas_pagadas": int(float(fila[6] or 0)),
                "ultimo_mes_pagado": fila[7],
                "estado": estado
            })
        return activos

    def actualizar_compromiso(self, comp_id: str, nombre: str, modalidad: str, categoria: str, monto_cuota: int, cuotas_totales: int, cuotas_pagadas: int):
        ws = self._get_compromisos_sheet()
        activos = self.listar_compromisos_activos()
        objetivo = next((c for c in activos if c["id"] == comp_id), None)
        if not objetivo:
            raise ValueError("Compromiso no encontrado.")

        row_idx = objetivo["row_index"]
        cuotas_tot = cuotas_totales if modalidad == "Cuotas" else 0
        cuotas_pag = min(cuotas_pagadas, cuotas_tot) if modalidad == "Cuotas" else cuotas_pagadas
        estado = "Finalizado" if (modalidad == "Cuotas" and cuotas_tot > 0 and cuotas_pag >= cuotas_tot) else "Activo"

        ws.update(
            f"B{row_idx}:I{row_idx}",
            [[nombre, modalidad, categoria, monto_cuota, cuotas_tot, cuotas_pag, objetivo["ultimo_mes_pagado"], estado]],
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