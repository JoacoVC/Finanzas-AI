// --- PESTAÑA 3: CONFIGURACIÓN DE CUENTAS Y TARJETAS ---
function renderizarCuadriculaCuentasP3() {
  const contenedor = document.getElementById('cuadricula-cuentas');
  const totalLiquido = todasLasCuentas.filter(c => c.tipo !== 'Tarjeta').reduce((s, c) => s + c.saldo, 0);
  const totalCupoTarjetas = todasLasCuentas.filter(c => c.tipo === 'Tarjeta').reduce((s, c) => s + c.cupo_disponible, 0);

  document.getElementById('subtitulo-resumen-cuentas-p3').textContent =
    `Disponible líquido: ${formatoMoneda.format(totalLiquido)} · Cupo libre en tarjetas: ${formatoMoneda.format(totalCupoTarjetas)}`;

  if (todasLasCuentas.length === 0) {
    contenedor.innerHTML = '<p class="text-sm text-slate-400 col-span-full py-4 text-center">No hay cuentas registradas.</p>';
    return;
  }

  contenedor.innerHTML = todasLasCuentas.map(c => {
    const esTarjeta = (c.tipo === 'Tarjeta');
    const icono = esTarjeta ? '💳' : (c.tipo === 'Banco' ? '🏦' : '💵');
    const diaPago = c.dia_pago || 0;

    let cuerpoHTML = '';
    if (esTarjeta) {
      const pctUso = c.cupo_total > 0 ? Math.min(100, Math.round((c.saldo / c.cupo_total) * 100)) : 0;
      cuerpoHTML = `
        <div class="mt-2 space-y-1.5">
          <p class="text-xs text-slate-500">Cupo disponible:</p>
          <p class="text-2xl font-black text-purple-700">${formatoMoneda.format(c.cupo_disponible)}</p>
          <div class="flex justify-between text-xs text-slate-500 pt-1">
            <span>Deuda usada: ${formatoMoneda.format(c.saldo)}</span>
            <span>Cupo total: ${formatoMoneda.format(c.cupo_total)}</span>
          </div>
          <div class="w-full bg-slate-200 rounded-full h-2">
            <div class="bg-purple-600 h-2 rounded-full" style="width: ${pctUso}%"></div>
          </div>
          ${diaPago > 0 ? `
            <p class="text-[11px] font-bold text-amber-700 pt-1">📅 Día límite de pago: ${diaPago}</p>
          ` : ''}
        </div>
      `;
    } else {
      cuerpoHTML = `
        <div class="mt-2 space-y-1">
          <p class="text-xs text-slate-500">Saldo disponible:</p>
          <p class="text-2xl font-black ${c.saldo >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatoMoneda.format(c.saldo)}</p>
        </div>
      `;
    }

    return `
      <div class="border border-slate-200 bg-white rounded-2xl p-5 flex flex-col justify-between hover:shadow-md transition">
        <div>
          <div class="flex justify-between items-center gap-2">
            <span class="font-bold text-slate-900 text-base flex items-center gap-1.5">${icono} ${c.nombre}</span>
            <span class="text-[10px] font-bold uppercase ${esTarjeta ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-700'} px-2.5 py-0.5 rounded-full">
              ${c.tipo}
            </span>
          </div>
          ${cuerpoHTML}
        </div>
        <div class="mt-4 pt-3 border-t border-slate-100 flex justify-end gap-1.5">
          <button onclick="abrirModalEditarCta('${c.id}')" title="Editar cuenta" class="text-xs px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600">✏️ Editar</button>
          <button onclick="eliminarCuenta('${c.id}', '${c.nombre}')" title="Eliminar cuenta" class="text-xs px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-rose-50 text-slate-600 hover:text-rose-600">🗑️</button>
        </div>
      </div>
    `;
  }).join('');
}

function abrirModalEditarCta(id) {
  const c = todasLasCuentas.find(item => item.id === id);
  if (!c) return;
  document.getElementById('edit-cta-id').value = c.id;
  document.getElementById('edit-cta-nombre').value = c.nombre;
  document.getElementById('edit-cta-tipo').value = c.tipo;
  document.getElementById('edit-cta-saldo').value = c.saldo;
  document.getElementById('edit-cta-cupo').value = c.cupo_total || 0;
  document.getElementById('edit-cta-diapago').value = c.dia_pago || 15;
  toggleCamposTipoCuenta('edit-cta');
  document.getElementById('modal-editar-cta').classList.remove('hidden');
}

function cerrarModalCta() {
  document.getElementById('modal-editar-cta').classList.add('hidden');
}

// Muestra/oculta cupo y día de pago solo cuando el tipo es Tarjeta
function toggleCamposTipoCuenta(prefijo) {
  const tipo = document.getElementById(`${prefijo}-tipo`).value;
  const esTarjeta = (tipo === 'Tarjeta');
  document.getElementById(`grupo-${prefijo}-cupo`).classList.toggle('hidden', !esTarjeta);
  document.getElementById(`grupo-${prefijo}-diapago`).classList.toggle('hidden', !esTarjeta);
  document.getElementById(`lbl-${prefijo}-saldo`).textContent = esTarjeta ? 'Cupo Usado / Deuda ($)' : 'Saldo Actual ($)';
}

async function crearCuenta(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-guardar-cta');
  btn.disabled = true;

  const tipo = document.getElementById('cta-tipo').value;
  const payload = {
    nombre: document.getElementById('cta-nombre').value.trim(),
    tipo: tipo,
    saldo: parseInt(document.getElementById('cta-saldo').value || '0', 10),
    cupo_total: (tipo === 'Tarjeta') ? parseInt(document.getElementById('cta-cupo').value || '0', 10) : 0,
    dia_pago: (tipo === 'Tarjeta') ? parseInt(document.getElementById('cta-diapago').value || '0', 10) : 0
  };

  try {
    const data = await api('/cuentas', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    mostrarAlerta(`✅ Cuenta "${payload.nombre}" creada.`);
    document.getElementById('cta-nombre').value = '';
    document.getElementById('cta-saldo').value = '0';
    toggleFormNuevaCuenta();
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function toggleFormNuevaCuenta() {
  const panel = document.getElementById('panel-nueva-cuenta');
  panel.classList.toggle('hidden');
}

async function guardarEdicionCta(e) {
  e.preventDefault();
  const id = document.getElementById('edit-cta-id').value;
  const tipo = document.getElementById('edit-cta-tipo').value;
  const payload = {
    nombre: document.getElementById('edit-cta-nombre').value.trim(),
    tipo: tipo,
    saldo: parseInt(document.getElementById('edit-cta-saldo').value || '0', 10),
    cupo_total: (tipo === 'Tarjeta') ? parseInt(document.getElementById('edit-cta-cupo').value || '0', 10) : 0,
    dia_pago: (tipo === 'Tarjeta') ? parseInt(document.getElementById('edit-cta-diapago').value || '0', 10) : 0
  };

  try {
    const data = await api(`/cuentas/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
    cerrarModalCta();
    mostrarAlerta('✅ ' + data.message);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  }
}

async function eliminarCuenta(id, nombre) {
  if (!confirm(`¿Eliminar la cuenta "${nombre}"?`)) return;
  try {
    const data = await api(`/cuentas/${id}`, { method: 'DELETE' });
    mostrarAlerta('🗑️ ' + data.message);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  }
}
