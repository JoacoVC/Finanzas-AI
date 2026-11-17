// --- EDICIÓN Y ELIMINACIÓN DE MOVIMIENTOS ---
function convertirFechaDDMMYYYYaISO(fechaStr) {
  const partes = (fechaStr || '').split('/');
  if (partes.length !== 3) return '';
  return `${partes[2]}-${partes[1].padStart(2, '0')}-${partes[0].padStart(2, '0')}`;
}

function abrirModalEditarMov(id) {
  const mov = todosLosMovimientos.find(m => m.id === id);
  if (!mov) return;

  document.getElementById('edit-mov-id').value = mov.id;
  document.getElementById('edit-mov-fecha').value = convertirFechaDDMMYYYYaISO(mov.fecha);
  document.getElementById('edit-mov-tipo').value = mov.tipo;
  actualizarModoEdicionMovTipo(mov.categoria);
  document.getElementById('edit-mov-cuenta').value = mov.cuenta || 'Efectivo';
  document.getElementById('edit-mov-destino').value = mov.cuenta_destino || 'Efectivo';
  document.getElementById('edit-mov-concepto').value = mov.concepto;
  document.getElementById('edit-mov-monto').value = mov.monto;

  document.getElementById('modal-editar-mov').classList.remove('hidden');
}

// Muestra/oculta la columna de destino según el tipo elegido en edición
function actualizarModoEdicionMovTipo(catActual = null) {
  const tipo = document.getElementById('edit-mov-tipo').value;
  const colDestino = document.getElementById('edit-col-destino');
  const colCat = document.getElementById('edit-col-categoria');
  const selCat = document.getElementById('edit-mov-categoria');
  const lblCta = document.getElementById('lbl-edit-mov-cuenta');

  if (tipo === 'Traslado') {
    colDestino.classList.remove('hidden');
    colCat.classList.add('hidden');
    lblCta.textContent = 'Cuenta Origen';
  } else {
    colDestino.classList.add('hidden');
    colCat.classList.remove('hidden');
    lblCta.textContent = 'Cuenta';

    const cats = (tipo === 'Egreso') ? CATEGORIAS_EGRESO : CATEGORIAS_INGRESO;
    selCat.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
    if (catActual && cats.includes(catActual)) selCat.value = catActual;
  }
}

function cerrarModalMov() {
  document.getElementById('modal-editar-mov').classList.add('hidden');
}

async function guardarEdicionMov(e) {
  e.preventDefault();
  const id = document.getElementById('edit-mov-id').value;
  const tipo = document.getElementById('edit-mov-tipo').value;
  const btn = document.getElementById('btn-guardar-edit-mov');
  btn.disabled = true;

  const payload = {
    fecha: document.getElementById('edit-mov-fecha').value,
    tipo: tipo,
    categoria: (tipo === 'Traslado') ? 'Traslado' : document.getElementById('edit-mov-categoria').value,
    cuenta: document.getElementById('edit-mov-cuenta').value,
    cuenta_destino: (tipo === 'Traslado') ? document.getElementById('edit-mov-destino').value : '',
    concepto: document.getElementById('edit-mov-concepto').value.trim(),
    monto: parseInt(document.getElementById('edit-mov-monto').value || '0', 10)
  };

  try {
    const data = await api(`/movimientos/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
    cerrarModalMov();
    mostrarAlerta('✅ ' + data.message);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function eliminarMovimiento(id, concepto) {
  if (!confirm(`¿Eliminar el movimiento "${concepto}"?`)) return;
  try {
    const data = await api(`/movimientos/${id}`, { method: 'DELETE' });
    mostrarAlerta('🗑️ ' + data.message);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  }
}
