# AGENTS.md

## What this is

FastAPI app (`app/main.py`, ~600 lines) for personal finance tracking. Google Sheets is the database (via `gspread`), Google Gemini is the LLM, and the frontend is a single self-contained HTML page. Everything (comments, API messages, prompts, categories) is in **Spanish**.

## Running

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Or `run.bat` at the repo root (wrapper around `iniciar_servidor.bat`; opens the browser automatically).
- Use the `venv/` Python (3.11); deps in `requirements.txt` are unpinned.
- There are **no tests, no linter, no CI**. Verification = run the server and exercise the endpoints / UI at `http://127.0.0.1:8000`.

## Live production data — be careful

There is no test/staging environment. Every endpoint call mutates the user's **real Google Sheet** (tabs `Registros`, `Cuentas`, `Compromisos`) and real account balances. Do not run exploratory POST/PUT/DELETE requests against the live sheet; simulate on the sheet copy (`Finanzas Bot (1).xlsx` in the root) or reason from code instead.

⚠️ The `--reload` reloader can **silently stop detecting changes** (observed 2026-11-17: worker process stayed alive from 17:02 despite backend files edited at 18:31–18:58, likely OneDrive interfering with file-change notifications). After backend edits, verify the reload worker actually restarted (`Get-CimInstance Win32_Process -Filter "ParentProcessId=<uvicorn-pid>" | Select CreationDate`) or restart the server manually — stale code caused a real bug (loan registered as a plain transaction, compromiso never created). A second uvicorn instance fails to bind (port in use) — kill the old one first. The server may also be running as an agent background process instead of the user's `run.bat` console.

## Architecture facts that aren't obvious

- **All routes live in `app/main.py`.** `app/api/routes.py` and `app/services/intent_parser.py` are **empty placeholder files** — don't put code there expecting it to run.
- Services are module-level singletons (`from app.services.sheets_client import sheets_client`) created lazily; the Sheets connection auto-creates tabs/headers on first connect. `Movimientos` header row: `Fecha, Mes, Anio, Tipo, Categoria, Concepto, Monto, ID, Cuenta, CuentaDestino`. Row IDs are `uuid4()[:8]`; updates/deletes need the `row_index` from listing, not the ID.
- Frontend = `app/static/index.html` (HTML structure only) + modular JS in `app/static/js/`. Load order matters (`state.js` → `config.js` → `api.js` → `ui.js` → view modules → `app.js` init); all functions are globals called from inline `onclick` attributes. Use the `api(url, opciones)` helper in `api.js` for any new fetch (throws with the backend `detail`, handles JSON vs FormData headers); endpoint error handling is centralized in `app/main.py` exception handlers (`ValueError` → 400, unhandled → 500) — endpoints don't need `try/except`.
- The Gemini prompt + response JSON contract lives in `app/services/llm_factory.py` (`PROMPT_FINANCIERO_MULTIMODAL`, `PROMPT_COMPROMISO`); model fallback chain: `gemini-3.5-flash-lite` → `gemini-3.8-flash` → `gemini-2.5-flash`. The prompt's `accion` values must stay in sync with `ejecutar_operacion_financiera()` in `main.py` (`transaccion`, `pago_tarjeta`, `transferencia`/`traslado`, `pago_compromiso`, `prestamo`). A `prestamo` (person-to-person loan: `direccion` "dado" = user lent → Ingreso compromiso + Egreso movement; "recibido" = user borrowed → Egreso compromiso + Ingreso movement) also registers the initial money movement, and so does any compromiso created by IA with category `Préstamo` (`crear_compromiso_desde_ia`). Temporal awareness: every parser method injects `_contexto_fecha_actual()` (FECHA ACTUAL with Spanish weekday) so Gemini resolves "ayer"/"hace N días"/"el sábado pasado"; ops carry an optional `fecha` ("YYYY-MM-DD") field resolved by `_fecha_desde_ia()` in `main.py` (transacciones, pagos de compromisos, préstamos, y el movimiento inicial de `crear_compromiso_desde_ia`).
- Business rules baked into both prompt and code: transfers between own accounts are **neither ingreso nor egreso**; paying a credit card is `pago_tarjeta`, never a plain transfer; for `Tarjeta` accounts `saldo` = current debt and `cupo_disponible = cupo_total - saldo`.

## Config & credentials

- `.env` at repo root (from `.env.example`): `GEMINI_API_KEY`, `SHEET_ID`, `WORKSHEET_NAME`, `CREDENTIALS_PATH`. Loaded by pydantic-settings (`app/core/config.py`).
- `credentials.json` (service account JSON) sits at the repo root. Alternative: put the whole JSON content in the `GOOGLE_CREDENTIALS_JSON` env var (checked first by `sheets_client.connect()`).
- `.gitignore` blocks **all `*.json`** files — anything JSON you want committed needs a `!` exception. `credentials.json`, `.env`, and `venv/` must never be committed.
