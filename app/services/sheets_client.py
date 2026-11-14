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
        
        # Generamos un ID único corto para esta transacción
        record_id = str(uuid.uuid4())[:8]
        
        # Agregamos el ID al final de las columnas existentes
        row_to_insert = record_data + [record_id]
        self.sheet.append_row(row_to_insert, value_input_option="USER_ENTERED")
        
        return record_id

sheets_client = SheetsClient()
