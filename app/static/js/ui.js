// Muestra o oculta la alerta global en la parte superior
function mostrarAlerta(mensaje, esError = false) {
  const alerta = document.getElementById('alerta');
  alerta.innerHTML = String(mensaje).replace(/\n/g, '<br/>');
  alerta.className = `p-4 rounded-2xl text-sm font-medium shadow-sm whitespace-pre-line leading-relaxed ${
    esError
      ? 'bg-rose-50 text-rose-800 border border-rose-200'
      : 'bg-emerald-50 text-emerald-900 border border-emerald-200'
  }`;
  alerta.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  setTimeout(() => alerta.classList.add('hidden'), 7000);
}

// Rellena el input de fecha del formulario manual con la fecha de hoy (local)
function establecerFechaLocalHoy() {
  const hoy = new Date();
  const anio = hoy.getFullYear();
  const mes = String(hoy.getMonth() + 1).padStart(2, '0');
  const dia = String(hoy.getDate()).padStart(2, '0');
  document.getElementById('man-fecha').value = `${anio}-${mes}-${dia}`;
}

// Rellena todos los <select> de cuentas en formularios y modales
function actualizarSelectoresCuentas() {
  const opcionesLiquidas = todasLasCuentas
    .filter(c => c.tipo !== 'Tarjeta')
    .map(c => `<option value="${c.nombre}">${c.nombre} (${formatoMoneda.format(c.saldo)})</option>`)
    .join('') || '<option value="Efectivo">Efectivo</option>';

  const todasOpciones = todasLasCuentas
    .map(c => `<option value="${c.nombre}">${c.nombre}</option>`)
    .join('') || '<option value="Efectivo">Efectivo</option>';

  // Formulario de registro manual
  document.getElementById('man-cuenta').innerHTML = todasOpciones;
  document.getElementById('man-cuenta-destino').innerHTML = todasOpciones;
  document.getElementById('ia-cuenta').innerHTML = '<option value="">Auto (Detectar IA)</option>' + todasOpciones;

  // Modales
  document.getElementById('edit-mov-cuenta').innerHTML = todasOpciones;
  document.getElementById('edit-mov-destino').innerHTML = todasOpciones;
  document.getElementById('modal-liq-cuenta').innerHTML = opcionesLiquidas;
  document.getElementById('abono-tarjeta-cuenta').innerHTML = opcionesLiquidas;
}

// Cambia entre pestañas principales: 'resumen' | 'pagos' | 'cuentas'
function cambiarPestana(pestana) {
  pestanaActual = pestana;

  const secciones = {
    resumen: document.getElementById('seccion-resumen'),
    pagos:   document.getElementById('seccion-pagos'),
    cuentas: document.getElementById('seccion-cuentas'),
  };
  const botones = {
    resumen: document.getElementById('nav-resumen'),
    pagos:   document.getElementById('nav-pagos'),
    cuentas: document.getElementById('nav-cuentas'),
  };

  // Ocultar todo y desactivar todos los botones
  Object.values(secciones).forEach(s => s.classList.add('hidden'));
  Object.values(botones).forEach(b => b.className = CLS_TAB_INACTIVE);

  // Mostrar la sección activa y activar su botón
  secciones[pestana].classList.remove('hidden');
  botones[pestana].className = CLS_TAB_ACTIVE;

  // Renderizar contenido de la pestaña seleccionada
  if (pestana === 'resumen') actualizarDashboard();
  else if (pestana === 'pagos') renderizarCuadriculaPagosYDeudas();
  else if (pestana === 'cuentas') renderizarCuadriculaCuentasP3();
}

// Rellena el selector de años basándose en los movimientos cargados
function poblarSelectorAnios() {
  const selectAnio = document.getElementById('filtro-anio');
  const previo = selectAnio.value;
  const anios = [...new Set(todosLosMovimientos.map(m => String(m.anio)).filter(Boolean))].sort().reverse();
  selectAnio.innerHTML = '<option value="Todos">Todos los años</option>' +
    anios.map(a => `<option value="${a}">${a}</option>`).join('');
  if (anios.includes(previo)) selectAnio.value = previo;
}

// Devuelve los movimientos filtrados por mes y año seleccionados
function obtenerMovimientosFiltradosPorFecha() {
  const mesSel = document.getElementById('filtro-mes').value;
  const anioSel = document.getElementById('filtro-anio').value;
  return todosLosMovimientos.filter(m => {
    const coincideMes = mesSel === 'Todos' || m.mes.toLowerCase() === mesSel.toLowerCase();
    const coincideAnio = anioSel === 'Todos' || String(m.anio) === anioSel;
    return coincideMes && coincideAnio;
  });
}

// Nombre del mes al que corresponde el próximo vencimiento de un día del mes.
// - yaPagado === null: sin registro de pago (tarjetas) -> si el día ya pasó este mes, el vencimiento es del mes siguiente.
// - yaPagado === true/false (compromisos): el flag 'pagado este mes' manda; si no se ha pagado, el vencimiento es del mes actual (aunque el día ya haya pasado = vencido).
function mesVencimiento(diaPago, yaPagado = null) {
  const hoy = new Date();
  const offset = (yaPagado !== null)
    ? (yaPagado ? 1 : 0)
    : (hoy.getDate() > diaPago ? 1 : 0);
  return MESES_ES[(hoy.getMonth() + offset) % 12];
}
