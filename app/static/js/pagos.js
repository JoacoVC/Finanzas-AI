// --- PESTAÑA 2: GESTIÓN DE PAGOS Y DEUDAS (COMPROMISOS Y TARJETAS) ---
function toggleFormNuevoCompromiso() {
  const panel = document.getElementById('panel-nuevo-compromiso');
  panel.classList.toggle('hidden');
}

function cambiarModoCompromiso(modo) {
  const fIA = document.getElementById('form-comp-ia');
  const fMan = document.getElementById('form-comp-manual');
  const bIA = document.getElementById('subtab-comp-ia');
  const bMan = document.getElementById('subtab-comp-man');

  if (modo === 'ia') {
    fIA.classList.remove('hidden');
    fMan.classList.add('hidden');
    bIA.className = CLS_SUBTAB_ACTIVE;
    bMan.className = CLS_SUBTAB_INACTIVE;
  } else {
    fIA.classList.add('hidden');
    fMan.classList.remove('hidden');
    bMan.className = CLS_SUBTAB_ACTIVE;
    bIA.className = CLS_SUBTAB_INACTIVE;
  }
}

function toggleCampoCuotas() {
  const mod = document.getElementById('comp-modalidad').value;
  document.getElementById('grupo-cuotas').classList.toggle('hidden', mod !== 'Cuotas');
}

function actualizarCategoriasCompManual() {
  const flujo = document.getElementById('comp-flujo').value;
  const sel = document.getElementById('comp-categoria');
  const opts = flujo === 'Ingreso' ? ['Trabajo', 'Préstamo', 'Otros'] : ['Deudas', 'Servicios', 'Suscripciones', 'Otros'];
  sel.innerHTML = opts.map(o => `<option value="${o}">${o}</option>`).join('');
}

async function crearCompromisoIA(e) {
  e.preventDefault();
  const input = document.getElementById('texto-comp-ia');
  const btn = document.getElementById('btn-comp-ia');
  if (!input.value.trim()) return;

  btn.disabled = true;
  try {
    const data = await api('/compromisos/ia', {
      method: 'POST',
      body: JSON.stringify({ texto: input.value.trim() })
    });
    mostrarAlerta(`✅ Compromiso creado: ${data.compromiso.nombre} (${formatoMoneda.format(data.compromiso.monto_cuota)}/mes)`);
    input.value = '';
    toggleFormNuevoCompromiso();
    await cargarCompromisos();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function crearCompromisoManual(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-comp-man');
  btn.disabled = true;

  const payload = {
    flujo: document.getElementById('comp-flujo').value,
    nombre: document.getElementById('comp-nombre').value.trim(),
    modalidad: document.getElementById('comp-modalidad').value,
    categoria: document.getElementById('comp-categoria').value,
    monto_cuota: parseInt(document.getElementById('comp-monto').value || '0', 10),
    dia_pago: parseInt(document.getElementById('comp-dia').value || '1', 10),
    cuotas_totales: parseInt(document.getElementById('comp-cuotas').value || '0', 10)
  };

  try {
    const data = await api('/compromisos/manual', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    mostrarAlerta(`✅ Compromiso guardado: ${payload.nombre}`);
    document.getElementById('comp-nombre').value = '';
    document.getElementById('comp-monto').value = '';
    toggleFormNuevoCompromiso();
    await cargarCompromisos();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

// Pinta las tarjetas de crédito y los compromisos activos
function renderizarCuadriculaPagosYDeudas() {
  const contenedor = document.getElementById('cuadricula-pagos-deudas');
  const tarjetasCredito = todasLasCuentas.filter(c => c.tipo === 'Tarjeta');

  const opcionesCuentasLiquidasHTML = todasLasCuentas
    .filter(c => c.tipo !== 'Tarjeta')
    .map(c => `<option value="${c.nombre}">${c.nombre} (${formatoMoneda.format(c.saldo)})</option>`)
    .join('') || '<option value="Efectivo">Efectivo</option>';

  // Tarjetas de Crédito HTML
  let tarjetasHTML = tarjetasCredito.map(t => {
    const tieneDeuda = t.saldo > 0;
    const pctUso = t.cupo_total > 0 ? Math.min(100, Math.round((t.saldo / t.cupo_total) * 100)) : 0;
    const diaPago = t.dia_pago || 0;

    const badgeFechaLimite = (tieneDeuda && diaPago > 0)
      ? `<span class="text-[11px] font-bold bg-amber-100 text-amber-800 px-2.5 py-0.5 rounded-full flex items-center gap-1">📅 Límite: Día ${diaPago}</span>`
      : (tieneDeuda
        ? `<span class="text-[11px] font-bold bg-rose-100 text-rose-700 px-2.5 py-0.5 rounded-full">Saldo pendiente</span>`
        : `<span class="text-[11px] font-bold bg-emerald-100 text-emerald-700 px-2.5 py-0.5 rounded-full">Al día ($0)</span>`);

    return `
      <div class="border border-purple-200 bg-white rounded-2xl p-5 flex flex-col justify-between hover:shadow-md transition">
        <div>
          <div class="flex justify-between items-start gap-2">
            <div>
              <span class="text-[10px] font-bold uppercase tracking-wider text-purple-700">💳 TARJETA DE CRÉDITO</span>
              <h3 class="font-bold text-slate-900 text-base mt-0.5">${t.nombre}</h3>
            </div>
            ${badgeFechaLimite}
          </div>

          <div class="mt-3 space-y-1.5">
            <p class="text-xs text-slate-500">Deuda actual (cupo utilizado):</p>
            <p class="text-2xl font-black ${tieneDeuda ? 'text-rose-600' : 'text-slate-800'}">${formatoMoneda.format(t.saldo)}</p>
            <div class="flex justify-between text-xs text-slate-500 pt-1">
              <span>Libre: ${formatoMoneda.format(t.cupo_disponible)}</span>
              <span>Cupo: ${formatoMoneda.format(t.cupo_total)}</span>
            </div>
            <div class="w-full bg-slate-200 rounded-full h-2">
              <div class="bg-purple-600 h-2 rounded-full transition-all duration-300" style="width: ${pctUso}%"></div>
            </div>
          </div>
        </div>

        <div class="mt-5 pt-3 border-t border-purple-100 space-y-2">
          ${tieneDeuda ? `
            <div class="flex items-center gap-1.5">
              <label class="text-[11px] font-semibold text-slate-500 whitespace-nowrap">Pagar con:</label>
              <select id="cta-pago-tc-${t.id}" class="w-full text-xs rounded-xl border border-slate-300 py-1.5 px-2 bg-white">
                ${opcionesCuentasLiquidasHTML}
              </select>
            </div>
            <div class="flex gap-2">
              <button
                onclick="pagarSaldoTarjetaTotal('${t.id}', '${t.nombre}', ${t.saldo}, this)"
                class="flex-1 bg-purple-700 hover:bg-purple-800 text-white font-bold py-2 px-3 rounded-xl text-xs transition shadow-xs flex items-center justify-center gap-1"
              >
                ⚡ Saldar a $0
              </button>
              <button
                onclick="abrirModalAbonarTarjeta('${t.id}', '${t.nombre}', ${t.saldo})"
                class="bg-white hover:bg-purple-50 text-purple-700 border border-purple-300 font-bold py-2 px-3 rounded-xl text-xs transition"
              >
                Abonar
              </button>
            </div>
          ` : `
            <p class="text-xs text-emerald-600 font-semibold text-center py-2">✓ ¡Sin deuda pendiente!</p>
          `}
        </div>
      </div>
    `;
  }).join('');

  // Compromisos Recurrentes y Créditos por Cuotas HTML
  let compromisosHTML = todosLosCompromisos.map(c => {
    const esIngreso = (c.flujo || 'Egreso') === 'Ingreso';
    const esCuotas = c.modalidad === 'Cuotas';
    const saldoRestanteTeorico = esCuotas ? Math.max(0, (c.cuotas_totales - c.cuotas_pagadas) * c.monto_cuota) : 0;
    const cuotasRestantes = esCuotas ? Math.max(0, c.cuotas_totales - c.cuotas_pagadas) : 0;
    const pctProgreso = (esCuotas && c.cuotas_totales > 0) ? Math.min(100, Math.round((c.cuotas_pagadas / c.cuotas_totales) * 100)) : 0;

    const badgeEstado = c.pagado_este_mes
      ? `<span class="text-[11px] font-bold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">✓ Al día este mes</span>`
      : `<span class="text-[11px] font-bold bg-amber-100 text-amber-800 px-2.5 py-0.5 rounded-full">Pendiente · Día ${c.dia_pago || 1}</span>`;

    return `
      <div class="border ${esIngreso ? 'border-emerald-200' : 'border-slate-200'} bg-white rounded-2xl p-5 flex flex-col justify-between hover:shadow-md transition">
        <div>
          <div class="flex justify-between items-start gap-2">
            <div>
              <span class="text-[10px] font-bold uppercase tracking-wider ${esIngreso ? 'text-emerald-700' : 'text-blue-700'}">
                ${esIngreso ? '+ INGRESO FIJO' : (esCuotas ? 'CRÉDITO POR CUOTAS' : 'PAGO FIJO')} · ${c.categoria}
              </span>
              <h3 class="font-bold text-slate-900 text-base mt-0.5">${c.nombre}</h3>
            </div>
            ${badgeEstado}
          </div>

          <div class="mt-3 space-y-1">
            <p class="text-2xl font-black ${esIngreso ? 'text-emerald-600' : 'text-slate-900'}">
              ${esIngreso ? '+' : ''}${formatoMoneda.format(c.monto_cuota)} <span class="text-xs font-normal text-slate-500">/ mes</span>
            </p>

            ${esCuotas ? `
              <div class="mt-3 space-y-1 pt-1">
                <div class="flex justify-between text-xs text-slate-600">
                  <span>Cuota <strong>${c.cuotas_pagadas} de ${c.cuotas_totales}</strong></span>
                  <span>Resta: <strong>${formatoMoneda.format(saldoRestanteTeorico)}</strong></span>
                </div>
                <div class="w-full bg-slate-200 rounded-full h-2">
                  <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: ${pctProgreso}%"></div>
                </div>
              </div>
            ` : `
              <p class="text-xs text-slate-500 pt-1">Día ${c.dia_pago || 1} de cada mes</p>
            `}
          </div>
        </div>

        <div class="mt-5 pt-3 border-t border-slate-100 space-y-2">
          <div class="flex items-center gap-1.5">
            <select id="cta-comp-${c.id}" class="text-xs border border-slate-300 rounded-xl px-2 py-2 bg-white max-w-[125px]">
              ${opcionesCuentasLiquidasHTML}
            </select>
            <button
              onclick="pagarCuotaCompromiso('${c.id}', this)"
              class="flex-1 ${esIngreso ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-slate-900 hover:bg-slate-800'} text-white font-bold py-2 px-2.5 rounded-xl text-xs transition flex items-center justify-center gap-1 shadow-xs"
            >
              ${esIngreso ? '✓ Cobrar' : '✓ Pagar cuota'}
            </button>
            <button onclick="eliminarCompromiso('${c.id}', '${c.nombre}')" title="Eliminar" class="text-xs text-slate-400 hover:text-rose-600 p-2 rounded-xl border border-slate-200 bg-white">
              🗑️
            </button>
          </div>

          ${(!esIngreso && esCuotas) ? `
            <button
              onclick="abrirModalLiquidarCredito('${c.id}', '${c.nombre}', ${saldoRestanteTeorico}, ${cuotasRestantes})"
              class="w-full bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 font-bold py-2 px-3 rounded-xl text-xs transition flex items-center justify-center gap-1"
            >
              ⚡ Saldar deuda completa (${formatoMoneda.format(saldoRestanteTeorico)})
            </button>
          ` : ''}

          ${!c.pagado_este_mes ? `
            <button
              onclick="marcarCompromisoSinSaldo('${c.id}', '${c.nombre}', this)"
              title="Marcar como ya pagado por fuera sin alterar saldo actual"
              class="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-1.5 px-3 rounded-xl text-[11px] transition text-center"
            >
              ✓ Marcar al día (sin tocar saldo)
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  if (!tarjetasHTML && !compromisosHTML) {
    contenedor.innerHTML = '<p class="text-sm text-slate-400 col-span-full py-4 text-center">No tienes deudas ni compromisos activos.</p>';
  } else {
    contenedor.innerHTML = tarjetasHTML + compromisosHTML;
  }
}

// Pagar una cuota ordinaria de compromiso
async function pagarCuotaCompromiso(id, btn) {
  const cuenta = document.getElementById(`cta-comp-${id}`)?.value || 'Efectivo';
  btn.disabled = true;

  try {
    const data = await api(`/compromisos/${id}/pagar`, {
      method: 'POST',
      body: JSON.stringify({ cuenta })
    });
    mostrarAlerta(data.message);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
    btn.disabled = false;
  }
}

async function marcarCompromisoSinSaldo(id, nombre, btn) {
  btn.disabled = true;
  try {
    const data = await api(`/compromisos/${id}/marcar-pagado`, { method: 'POST' });
    mostrarAlerta(data.message);
    await cargarCompromisos();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
    btn.disabled = false;
  }
}

async function eliminarCompromiso(id, nombre) {
  if (!confirm(`¿Eliminar el compromiso "${nombre}"?`)) return;
  try {
    const data = await api(`/compromisos/${id}`, { method: 'DELETE' });
    mostrarAlerta('🗑️ ' + data.message);
    await cargarCompromisos();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  }
}

// Modal Liquidar Crédito Anticipadamente
function abrirModalLiquidarCredito(id, nombre, saldoTeorico, cuotasRestantes) {
  document.getElementById('modal-liq-id').value = id;
  document.getElementById('modal-liq-nombre').textContent = nombre;
  document.getElementById('modal-liq-cuotas').textContent = `${cuotasRestantes} cuotas`;
  document.getElementById('modal-liq-teorico').textContent = formatoMoneda.format(saldoTeorico);
  document.getElementById('modal-liq-monto-real').value = saldoTeorico;

  document.getElementById('modal-liquidar-credito').classList.remove('hidden');
}

function cerrarModalLiquidarCredito() {
  document.getElementById('modal-liquidar-credito').classList.add('hidden');
}

async function confirmarLiquidacionCredito(e) {
  e.preventDefault();
  const id = document.getElementById('modal-liq-id').value;
  const montoReal = parseInt(document.getElementById('modal-liq-monto-real').value || '0', 10);
  const cuenta = document.getElementById('modal-liq-cuenta').value || 'Efectivo';
  const btn = document.getElementById('btn-confirmar-liq');

  if (!montoReal || montoReal <= 0) {
    mostrarAlerta('❌ Ingresa un monto real válido mayor a 0.', true);
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Procesando liquidación...';

  try {
    const data = await api(`/compromisos/${id}/liquidar`, {
      method: 'POST',
      body: JSON.stringify({ cuenta, monto_real: montoReal })
    });
    cerrarModalLiquidarCredito();
    mostrarAlerta(data.message || '🎉 Deuda saldada al 100% y registrada en movimientos.');
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Confirmar y Saldar a $0';
  }
}

// Modal Abonar a Tarjeta
function abrirModalAbonarTarjeta(id, nombre, deudaActual) {
  document.getElementById('abono-tarjeta-id').value = id;
  document.getElementById('abono-tarjeta-nombre').textContent = nombre;
  document.getElementById('abono-tarjeta-deuda').textContent = formatoMoneda.format(deudaActual);
  document.getElementById('abono-tarjeta-monto').value = Math.min(deudaActual, 50000);
  document.getElementById('modal-abonar-tarjeta').classList.remove('hidden');
}

function cerrarModalAbonarTarjeta() {
  document.getElementById('modal-abonar-tarjeta').classList.add('hidden');
}

async function confirmarAbonoTarjeta(e) {
  e.preventDefault();
  const id = document.getElementById('abono-tarjeta-id').value;
  const monto = parseInt(document.getElementById('abono-tarjeta-monto').value || '0', 10);
  const cuentaOrigen = document.getElementById('abono-tarjeta-cuenta').value;
  const btn = document.getElementById('btn-confirmar-abono');

  btn.disabled = true;
  try {
    const data = await api(`/cuentas/${id}/pagar-tarjeta`, {
      method: 'POST',
      body: JSON.stringify({ cuenta_origen: cuentaOrigen, es_total: false, monto })
    });
    cerrarModalAbonarTarjeta();
    mostrarAlerta(data.message || '✅ Abono registrado exitosamente.');
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

// Pagar Saldo Total de Tarjeta
async function pagarSaldoTarjetaTotal(id, nombre, saldo, btn) {
  const selectCta = document.getElementById(`cta-pago-tc-${id}`);
  const cuentaOrigen = selectCta ? selectCta.value : 'Efectivo';
  if (!confirm(`¿Confirmas liquidar la tarjeta "${nombre}" por ${formatoMoneda.format(saldo)} pagando desde ${cuentaOrigen}? Dejará su deuda en $0 y registrará el movimiento.`)) return;

  if (btn) btn.disabled = true;
  try {
    const data = await api(`/cuentas/${id}/pagar-tarjeta`, {
      method: 'POST',
      body: JSON.stringify({ cuenta_origen: cuentaOrigen, es_total: true, monto: saldo })
    });
    mostrarAlerta(data.message || `✅ Tarjeta ${nombre} saldada a $0 exitosamente.`);
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}
