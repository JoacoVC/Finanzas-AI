// Recalcula KPIs y re-renderiza gráficas e historial
function actualizarDashboard() {
  const filtrados = obtenerMovimientosFiltradosPorFecha();

  const ingresos = filtrados.filter(m => m.tipo.toLowerCase() === 'ingreso');
  const egresos  = filtrados.filter(m => m.tipo.toLowerCase() === 'egreso');
  const sumIngresos = ingresos.reduce((s, m) => s + m.monto, 0);
  const sumEgresos  = egresos.reduce((s, m) => s + m.monto, 0);

  const saldoLiquido = todasLasCuentas
    .filter(c => c.tipo !== 'Tarjeta')
    .reduce((s, c) => s + c.saldo, 0);

  const deudaTarjetas = todasLasCuentas
    .filter(c => c.tipo === 'Tarjeta')
    .reduce((s, c) => s + c.saldo, 0);

  const deudaCuotas = todosLosCompromisos
    .filter(c => c.modalidad === 'Cuotas' && (c.flujo || 'Egreso') === 'Egreso')
    .reduce((s, c) => s + Math.max(0, c.cuotas_totales - c.cuotas_pagadas) * c.monto_cuota, 0);

  const deudaTotal = deudaTarjetas + deudaCuotas;

  document.getElementById('kpi-saldo-disponible').textContent = formatoMoneda.format(saldoLiquido);
  document.getElementById('kpi-ingresos-mes').textContent     = formatoMoneda.format(sumIngresos);
  document.getElementById('kpi-egresos-mes').textContent      = formatoMoneda.format(sumEgresos);
  document.getElementById('kpi-deuda-total').textContent      = formatoMoneda.format(deudaTotal);

  const mesSel  = document.getElementById('filtro-mes').value;
  const anioSel = document.getElementById('filtro-anio').value;
  const labelPeriodo = (mesSel === 'Todos' && anioSel === 'Todos')
    ? 'Todo el histórico'
    : `${mesSel} ${anioSel !== 'Todos' ? anioSel : ''}`;
  document.getElementById('subtitulo-kpi-ingresos').textContent = labelPeriodo;
  document.getElementById('subtitulo-kpi-egresos').textContent  = labelPeriodo;

  renderizarResumenRapidoTarjetas();
  renderizarGraficas(filtrados, sumIngresos, sumEgresos);
  renderizarHistorialMovimientos();
}

// --- Resumen rápido de tarjetas (sección superior del dashboard) ---
function renderizarResumenRapidoTarjetas() {
  const contenedor = document.getElementById('lista-resumen-rapido-tarjetas');
  const tarjetas = todasLasCuentas.filter(c => c.tipo === 'Tarjeta');
  document.getElementById('badge-total-tarjetas').textContent = `${tarjetas.length} tarjetas`;

  if (tarjetas.length === 0) {
    contenedor.innerHTML = '<p class="text-xs text-slate-400 py-1 col-span-full">No tienes tarjetas de crédito configuradas.</p>';
    return;
  }

  contenedor.innerHTML = tarjetas.map(t => {
    const pctUso = t.cupo_total > 0 ? Math.min(100, Math.round((t.saldo / t.cupo_total) * 100)) : 0;
    const tieneDeuda = t.saldo > 0;
    const diaPago = t.dia_pago || 0;

    const badgeFecha = (tieneDeuda && diaPago > 0)
      ? `<span class="text-[10px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-md flex items-center gap-1">📅 Límite: Día ${diaPago}</span>`
      : (tieneDeuda
        ? `<span class="text-[10px] font-bold bg-rose-50 text-rose-700 px-2 py-0.5 rounded-md">Saldo pendiente</span>`
        : `<span class="text-[10px] font-bold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-md">Al día ($0)</span>`);

    return `
      <div class="border border-slate-200 bg-slate-50/50 rounded-xl p-3 flex flex-col justify-between hover:bg-white transition shadow-xs">
        <div class="flex justify-between items-center gap-2 mb-1.5">
          <span class="font-bold text-slate-900 text-xs flex items-center gap-1.5">💳 ${t.nombre}</span>
          ${badgeFecha}
        </div>
        <div class="space-y-1">
          <div class="flex justify-between text-xs">
            <span class="text-slate-500 font-medium">Usado: <strong class="${tieneDeuda ? 'text-rose-600' : 'text-slate-700'}">${formatoMoneda.format(t.saldo)}</strong></span>
            <span class="text-slate-500 font-medium">Total: <strong class="text-slate-800">${formatoMoneda.format(t.cupo_total)}</strong></span>
          </div>
          <div class="w-full bg-slate-200 rounded-full h-1.5">
            <div class="bg-purple-600 h-1.5 rounded-full transition-all duration-300" style="width: ${pctUso}%"></div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- Switch de tipo de análisis: Todos | Egreso | Ingreso ---
function cambiarTipoAnalisis(tipo) {
  tipoAnalisisActual = tipo;

  document.getElementById('btn-vista-todos').className   = CLS_ANALYSIS_INACTIVE;
  document.getElementById('btn-vista-egreso').className  = CLS_ANALYSIS_INACTIVE;
  document.getElementById('btn-vista-ingreso').className = CLS_ANALYSIS_INACTIVE;

  if (tipo === 'Todos')   document.getElementById('btn-vista-todos').className   = CLS_ANALYSIS_TODOS;
  else if (tipo === 'Egreso')  document.getElementById('btn-vista-egreso').className  = CLS_ANALYSIS_EGRESO;
  else                    document.getElementById('btn-vista-ingreso').className = CLS_ANALYSIS_INGRESO;

  actualizarDashboard();
}

// --- Gráficas ---
function renderizarGraficas(filtrados, sumIngresos, sumEgresos) {
  const paletaCategorias = ['#2563EB','#10B981','#F59E0B','#EF4444','#8B5CF6','#06B6D4','#EC4899','#64748B'];

  // 1. Gráfico Dona
  const ctxDona = document.getElementById('chart-dona');
  if (chartDona) chartDona.destroy();

  let labelsDona, dataDona, colorsDona;

  if (tipoAnalisisActual === 'Todos') {
    document.getElementById('titulo-grafico-dona').textContent    = 'Comparativa: Ingresos vs Egresos';
    document.getElementById('subtitulo-grafico-dona').textContent = 'Distribución global de flujos';
    labelsDona = ['Ingresos', 'Egresos'];
    dataDona   = [sumIngresos, sumEgresos];
    colorsDona = ['#10B981', '#EF4444'];
  } else {
    const esEgr = tipoAnalisisActual === 'Egreso';
    document.getElementById('titulo-grafico-dona').textContent    = esEgr ? 'Distribución de Egresos por Categoría' : 'Distribución de Ingresos por Categoría';
    document.getElementById('subtitulo-grafico-dona').textContent = 'Porcentaje por rubro';

    const movsTipo = filtrados.filter(m => m.tipo.toLowerCase() === tipoAnalisisActual.toLowerCase());
    const agrp = {};
    movsTipo.forEach(m => { const c = m.categoria || 'Otros'; agrp[c] = (agrp[c] || 0) + m.monto; });
    labelsDona = Object.keys(agrp);
    dataDona   = Object.values(agrp);
    colorsDona = paletaCategorias.slice(0, labelsDona.length);
  }

  chartDona = new Chart(ctxDona, {
    type: 'doughnut',
    data: {
      labels: labelsDona,
      datasets: [{
        data: dataDona.length ? dataDona : [1],
        backgroundColor: dataDona.length ? colorsDona : ['#E2E8F0'],
        borderWidth: 2,
        borderColor: '#FFFFFF'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11, weight: 'bold' } } },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${formatoMoneda.format(ctx.raw || 0)}` } }
      }
    }
  });

  // 2. Gráfico Barras Horizontales (Ranking)
  const ctxRanking = document.getElementById('chart-ranking-barras');
  if (chartRanking) chartRanking.destroy();

  const movsParaRanking = tipoAnalisisActual === 'Todos'
    ? filtrados.filter(m => m.tipo.toLowerCase() !== 'traslado')
    : filtrados.filter(m => m.tipo.toLowerCase() === tipoAnalisisActual.toLowerCase());

  const categoriasRanking = {};
  movsParaRanking.forEach(m => {
    const cat = m.categoria || 'Otros';
    categoriasRanking[cat] = (categoriasRanking[cat] || 0) + m.monto;
  });

  const rankingOrdenado = Object.keys(categoriasRanking)
    .map(cat => ({ cat, total: categoriasRanking[cat] }))
    .sort((a, b) => b.total - a.total);

  const colorBarras = tipoAnalisisActual === 'Ingreso' ? '#10B981'
    : (tipoAnalisisActual === 'Egreso' ? '#EF4444' : '#2563EB');

  chartRanking = new Chart(ctxRanking, {
    type: 'bar',
    data: {
      labels: rankingOrdenado.map(i => i.cat),
      datasets: [{ label: 'Total', data: rankingOrdenado.map(i => i.total), backgroundColor: colorBarras, borderRadius: 6 }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ` ${formatoMoneda.format(ctx.raw || 0)}` } }
      },
      scales: {
        x: { ticks: { callback: (val) => `$${(val / 1000).toLocaleString()}k` }, grid: { color: '#F1F5F9' } },
        y: { grid: { display: false } }
      }
    }
  });

  // 3. Gráfico de Líneas (Evolución temporal)
  const ctxLineas = document.getElementById('chart-lineas-tiempo');
  if (chartLineas) chartLineas.destroy();

  const mapaTemporal = {};
  filtrados.forEach(m => {
    if (m.tipo.toLowerCase() === 'traslado' || !m.fecha) return;
    if (!mapaTemporal[m.fecha]) mapaTemporal[m.fecha] = { ingreso: 0, egreso: 0 };
    if (m.tipo.toLowerCase() === 'ingreso') mapaTemporal[m.fecha].ingreso += m.monto;
    else if (m.tipo.toLowerCase() === 'egreso') mapaTemporal[m.fecha].egreso += m.monto;
  });

  const fechasOrdenadas = Object.keys(mapaTemporal).sort((a, b) => {
    const [dA, mA, yA] = a.split('/').map(Number);
    const [dB, mB, yB] = b.split('/').map(Number);
    return new Date(yA, mA - 1, dA) - new Date(yB, mB - 1, dB);
  });

  chartLineas = new Chart(ctxLineas, {
    type: 'line',
    data: {
      labels: fechasOrdenadas,
      datasets: [
        {
          label: 'Ingresos',
          data: fechasOrdenadas.map(f => mapaTemporal[f].ingreso),
          borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.1)',
          borderWidth: 2.5, tension: 0.3, fill: true,
          pointBackgroundColor: '#10B981', pointRadius: 4
        },
        {
          label: 'Egresos',
          data: fechasOrdenadas.map(f => mapaTemporal[f].egreso),
          borderColor: '#EF4444', backgroundColor: 'rgba(239,68,68,0.05)',
          borderWidth: 2.5, tension: 0.3, fill: true,
          pointBackgroundColor: '#EF4444', pointRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11, weight: 'bold' } } },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${formatoMoneda.format(ctx.raw || 0)}` } }
      },
      scales: {
        y: { ticks: { callback: (val) => `$${(val / 1000).toLocaleString()}k` }, grid: { color: '#F1F5F9' } },
        x: { grid: { display: false } }
      }
    }
  });
}

// --- Helpers para el historial (elimina lógica duplicada desktop/mobile) ---
function _getBadgeTipo(tipoNorm, isMobile = false) {
  const cls = isMobile
    ? 'text-[10px] font-bold px-2 py-0.5 rounded-md'
    : 'px-2.5 py-0.5 rounded-full text-xs font-semibold';
  if (tipoNorm === 'ingreso')  return `<span class="${cls} bg-emerald-100 text-emerald-800">Ingreso</span>`;
  if (tipoNorm === 'traslado') return `<span class="${cls} bg-blue-100 text-blue-800">Traslado</span>`;
  return `<span class="${cls} bg-rose-100 text-rose-800">Egreso</span>`;
}

function _getMontoStyle(tipoNorm) {
  if (tipoNorm === 'ingreso')  return { clase: 'text-emerald-600 font-bold', signo: '+' };
  if (tipoNorm === 'traslado') return { clase: 'text-blue-700 font-bold',    signo: '' };
  return { clase: 'text-rose-600 font-bold', signo: '-' };
}

function _getCuentaFlujo(m) {
  if (m.tipo.toLowerCase() === 'traslado') {
    return `${m.cuenta || 'Efectivo'} → ${m.cuenta_destino || 'Destino'}`;
  }
  return m.cuenta || 'Efectivo';
}

// --- Historial de movimientos (tabla desktop + cards mobile) ---
function renderizarHistorialMovimientos() {
  const filtradosFecha = obtenerMovimientosFiltradosPorFecha();
  const selCat = document.getElementById('filtro-categoria-historial').value;

  // Actualizar opciones del selector de categorías
  const catsUnicas = [...new Set(filtradosFecha.map(m => m.categoria || 'Otros'))];
  const selectFiltro = document.getElementById('filtro-categoria-historial');
  const prevCat = selectFiltro.value;
  selectFiltro.innerHTML = '<option value="Todas">Todas las categorías</option>' +
    catsUnicas.map(c => `<option value="${c}">${c}</option>`).join('');
  if (catsUnicas.includes(prevCat)) selectFiltro.value = prevCat;

  const movsFinales = filtradosFecha.filter(m => {
    const coincideTipo = tipoAnalisisActual === 'Todos' || m.tipo.toLowerCase() === tipoAnalisisActual.toLowerCase();
    const coincideCat  = selCat === 'Todas' || m.categoria === selCat;
    return coincideTipo && coincideCat;
  });

  document.getElementById('contador-movimientos').textContent = `${movsFinales.length} movimientos`;

  const tbodyDesktop = document.getElementById('tabla-movimientos-desktop');
  const divMobile    = document.getElementById('lista-movimientos-mobile');

  if (movsFinales.length === 0) {
    tbodyDesktop.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-slate-400">No hay movimientos registrados para este filtro.</td></tr>';
    divMobile.innerHTML    = '<p class="py-6 text-center text-slate-400 text-xs">No hay movimientos registrados para este filtro.</p>';
    return;
  }

  // Tabla Desktop
  tbodyDesktop.innerHTML = movsFinales.map(m => {
    const tipoNorm   = m.tipo.toLowerCase();
    const { clase: montoClase, signo } = _getMontoStyle(tipoNorm);
    const conceptoEsc = (m.concepto || '').replace(/'/g, "\\'");
    return `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 px-4 text-slate-600 whitespace-nowrap text-xs">${m.fecha}</td>
        <td class="py-3 px-4">${_getBadgeTipo(tipoNorm, false)}</td>
        <td class="py-3 px-4">
          <span class="text-xs font-medium text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg">${_getCuentaFlujo(m)}</span>
        </td>
        <td class="py-3 px-4 text-xs font-semibold text-slate-600">${m.categoria}</td>
        <td class="py-3 px-4 text-slate-900 font-medium">${m.concepto}</td>
        <td class="py-3 px-4 text-right whitespace-nowrap ${montoClase}">${signo}${formatoMoneda.format(m.monto)}</td>
        <td class="py-3 px-4 text-center whitespace-nowrap">
          <button onclick="abrirModalEditarMov('${m.id}')" title="Editar" class="text-xs px-2 py-1 rounded-lg hover:bg-blue-50 text-slate-500 hover:text-blue-600 transition">✏️</button>
          <button onclick="eliminarMovimiento('${m.id}', '${conceptoEsc}')" title="Eliminar" class="text-xs px-2 py-1 rounded-lg hover:bg-rose-50 text-slate-500 hover:text-rose-600 transition">🗑️</button>
        </td>
      </tr>
    `;
  }).join('');

  // Cards Mobile
  divMobile.innerHTML = movsFinales.map(m => {
    const tipoNorm   = m.tipo.toLowerCase();
    const { clase: montoClase, signo } = _getMontoStyle(tipoNorm);
    const conceptoEsc = (m.concepto || '').replace(/'/g, "\\'");
    return `
      <div class="py-3 px-2 flex justify-between items-start gap-2">
        <div class="space-y-1">
          <div class="flex items-center gap-1.5 flex-wrap">
            ${_getBadgeTipo(tipoNorm, true)}
            <span class="text-[11px] font-bold text-slate-500">${m.fecha}</span>
            <span class="text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md">${_getCuentaFlujo(m)}</span>
          </div>
          <p class="font-bold text-slate-900 text-sm leading-snug">${m.concepto}</p>
          <span class="text-[11px] text-slate-500 font-medium">[${m.categoria}]</span>
        </div>
        <div class="text-right flex flex-col items-end gap-1">
          <span class="text-sm ${montoClase} whitespace-nowrap">${signo}${formatoMoneda.format(m.monto)}</span>
          <div class="flex gap-1 pt-1">
            <button onclick="abrirModalEditarMov('${m.id}')" class="text-xs p-1 rounded-md bg-slate-100 text-slate-600">✏️</button>
            <button onclick="eliminarMovimiento('${m.id}', '${conceptoEsc}')" class="text-xs p-1 rounded-md bg-slate-100 text-slate-600">🗑️</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}
