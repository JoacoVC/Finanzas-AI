// Recarga cuentas, movimientos y compromisos en paralelo
async function sincronizarTodo() {
  await cargarCuentas();
  await Promise.all([cargarMovimientos(), cargarCompromisos()]);
}

async function cargarCuentas() {
  try {
    const res = await fetch('/cuentas');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al cargar cuentas');
    todasLasCuentas = data.cuentas || [];
    actualizarSelectoresCuentas();
    renderizarResumenRapidoTarjetas();
    if (pestanaActual === 'cuentas') renderizarCuadriculaCuentasP3();
  } catch (err) {
    console.error(err);
  }
}

async function cargarMovimientos() {
  try {
    const res = await fetch('/movimientos');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al cargar movimientos');
    todosLosMovimientos = data.movimientos || [];
    poblarSelectorAnios();
    actualizarDashboard();
  } catch (err) {
    console.error(err);
    mostrarAlerta('Error sincronizando movimientos: ' + err.message, true);
  }
}

async function cargarCompromisos() {
  try {
    const res = await fetch('/compromisos');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al cargar compromisos');
    todosLosCompromisos = data.compromisos || [];
    if (pestanaActual === 'pagos') renderizarCuadriculaPagosYDeudas();
  } catch (err) {
    console.error(err);
  }
}
