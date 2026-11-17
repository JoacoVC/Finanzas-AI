// Llama a la API y devuelve el JSON parseado.
// Lanza Error con el 'detail' del backend si la respuesta no es OK.
// No fuerza Content-Type cuando el body es FormData (el navegador fija el boundary).
async function api(url, opciones = {}) {
  if (opciones.body && !(opciones.body instanceof FormData) && !opciones.headers) {
    opciones.headers = { 'Content-Type': 'application/json' };
  }
  const res = await fetch(url, opciones);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Error en la solicitud');
  return data;
}

// Recarga cuentas, movimientos y compromisos en paralelo
async function sincronizarTodo() {
  await cargarCuentas();
  await Promise.all([cargarMovimientos(), cargarCompromisos()]);
}

async function cargarCuentas() {
  try {
    const data = await api('/cuentas');
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
    const data = await api('/movimientos');
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
    const data = await api('/compromisos');
    todosLosCompromisos = data.compromisos || [];
    if (pestanaActual === 'pagos') renderizarCuadriculaPagosYDeudas();
  } catch (err) {
    console.error(err);
  }
}
