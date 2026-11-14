import os
import uuid
import gspread
from google.oauth2.service_account import Credentials
from app.core.config import settings

class SheetsClient:
    def __init__(self):
        self.client = None
        self.sheet = None

    def connect(self):
        if not os.path.exists(settings.google_credentials_path):
            raise FileNotFoundError(f"Falta el archivo: {settings.google_credentials_path}")
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(
            settings.google_credentials_path, scopes=scopes
        )
        self.client = gspread.authorize(credentials)
        sh = self.client.open_by_key(settings.sheet_id)
        self.sheet = sh.worksheet(settings.worksheet_name)
        return self.sheet

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
        # Saltamos la fila 1 de encabezados (Fecha, Mes, Año, Tipo, Categoria, Concepto, Presupuesto, Monto, ID)
        for fila in filas[1:]:
            if not fila or not fila[0].strip():
                continue
            
            def limpiar_numero(val):
                limpio = str(val).replace("$", "").replace(",", "").replace(".", "").strip()
                try:
                    return int(float(limpio)) if limpio else 0
                except ValueError:
                    return 0

            registros.append({
                "fecha": fila[0] if len(fila) > 0 else "",
                "mes": fila[1] if len(fila) > 1 else "",
                "anio": fila[2] if len(fila) > 2 else "",
                "tipo": fila[3] if len(fila) > 3 else "",
                "categoria": fila[4] if len(fila) > 4 else "",
                "concepto": fila[5] if len(fila) > 5 else "",
                "presupuesto": limpiar_numero(fila[6]) if len(fila) > 6 else 0,
                "monto": limpiar_numero(fila[7]) if len(fila) > 7 else 0,
                "id": fila[8] if len(fila) > 8 else ""
            })
        
        return registros

sheets_client = SheetsClient()