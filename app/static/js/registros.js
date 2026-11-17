// --- FORMULARIOS DE REGISTRO RÁPIDO (IA vs MANUAL) ---
function cambiarModoRegistro(modo) {
  const fIA = document.getElementById('form-ia');
  const fMan = document.getElementById('form-manual');
  const tIA = document.getElementById('tab-ia');
  const tMan = document.getElementById('tab-manual');

  if (modo === 'ia') {
    fIA.classList.remove('hidden');
    fMan.classList.add('hidden');
    tIA.className = CLS_REGFORM_ACTIVE;
    tMan.className = CLS_REGFORM_INACTIVE;
  } else {
    fIA.classList.add('hidden');
    fMan.classList.remove('hidden');
    tMan.className = CLS_REGFORM_ACTIVE;
    tIA.className = CLS_REGFORM_INACTIVE;
    establecerFechaLocalHoy();
    actualizarModoManualTipo();
  }
}

// Muestra/oculta la columna de cuenta destino según el tipo elegido
function actualizarModoManualTipo() {
  const tipo = document.getElementById('man-tipo').value;
  const colDestino = document.getElementById('col-man-cuenta-destino');
  const colCat = document.getElementById('col-man-categoria');
  const lblCuenta = document.getElementById('lbl-man-cuenta');
  const selCat = document.getElementById('man-categoria');

  if (tipo === 'Traslado') {
    colDestino.classList.remove('hidden');
    colCat.classList.add('hidden');
    lblCuenta.textContent = 'Cuenta Origen';
  } else {
    colDestino.classList.add('hidden');
    colCat.classList.remove('hidden');
    lblCuenta.textContent = 'Cuenta';

    const cats = (tipo === 'Egreso') ? CATEGORIAS_EGRESO : CATEGORIAS_INGRESO;
    selCat.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
  }
}

// Registro de movimientos con lenguaje natural (texto)
async function enviarIA(e) {
  e.preventDefault();
  const input = document.getElementById('texto-ia');
  const btn = document.getElementById('btn-ia');
  const texto = input.value.trim();
  const cuenta = document.getElementById('ia-cuenta').value;
  if (!texto) return;

  btn.disabled = true;
  btn.textContent = 'Analizando...';

  try {
    const data = await api('/registrar-transaccion', {
      method: 'POST',
      body: JSON.stringify({ texto, cuenta })
    });
    mostrarAlerta(data.message || '✅ Movimiento registrado exitosamente.');
    input.value = '';
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Registrar';
  }
}

// Registro manual con formulario
async function enviarManual(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-manual');
  btn.disabled = true;

  const tipo = document.getElementById('man-tipo').value;
  const payload = {
    fecha: document.getElementById('man-fecha').value,
    tipo: tipo,
    categoria: (tipo === 'Traslado') ? 'Traslado' : document.getElementById('man-categoria').value,
    cuenta: document.getElementById('man-cuenta').value,
    cuenta_destino: (tipo === 'Traslado') ? document.getElementById('man-cuenta-destino').value : '',
    concepto: document.getElementById('man-concepto').value.trim(),
    monto: parseInt(document.getElementById('man-monto').value || '0', 10)
  };

  try {
    const data = await api('/registrar-manual', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    mostrarAlerta(data.message || '✅ Movimiento manual registrado exitosamente.');
    document.getElementById('man-concepto').value = '';
    document.getElementById('man-monto').value = '';
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}
