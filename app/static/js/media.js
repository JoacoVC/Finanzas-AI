// --- FUNCIONES MULTIMEDIA (NOTAS DE VOZ Y FOTOS DE COMPROBANTES) ---
async function toggleGrabacionAudio(contexto) {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    mostrarAlerta('❌ Tu navegador no soporta micrófono o requiere HTTPS.', true);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
    mediaRecorder = new MediaRecorder(stream, { mimeType });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      actualizarUIGrabacion(contexto, false);

      const blobAudio = new Blob(audioChunks, { type: mimeType });
      if (blobAudio.size < 1000) {
        mostrarAlerta('⚠️ Audio demasiado corto o vacío.', true);
        return;
      }

      if (contexto === 'transaccion') {
        await enviarAudioTransaccion(blobAudio);
      } else {
        await enviarAudioCompromiso(blobAudio);
      }
    };

    mediaRecorder.start();
    actualizarUIGrabacion(contexto, true);
  } catch (err) {
    mostrarAlerta('❌ No se pudo acceder al micrófono: ' + err.message, true);
  }
}

function actualizarUIGrabacion(contexto, grabando) {
  if (contexto === 'transaccion') {
    const btn = document.getElementById('btn-voz-ia');
    const txt = document.getElementById('texto-btn-voz-ia');
    const banner = document.getElementById('estado-media-ia');
    const msg = document.getElementById('mensaje-media-ia');

    if (grabando) {
      btn.className = "bg-rose-600 hover:bg-rose-700 text-white font-semibold px-3 py-2.5 rounded-xl text-xs transition flex items-center gap-1.5 whitespace-nowrap animate-pulse";
      txt.textContent = "Detener y Enviar";
      banner.classList.remove('hidden');
      msg.textContent = "Grabando nota de voz... Habla claro y haz clic en 'Detener y Enviar'.";
    } else {
      btn.className = "bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 font-semibold px-3 py-2.5 rounded-xl text-xs transition flex items-center gap-1.5 whitespace-nowrap";
      txt.textContent = "Dictar";
    }
  } else {
    const btn = document.getElementById('btn-voz-comp');
    const txt = document.getElementById('texto-btn-voz-comp');
    const banner = document.getElementById('estado-media-comp');
    const msg = document.getElementById('mensaje-media-comp');

    if (grabando) {
      btn.className = "bg-rose-600 hover:bg-rose-700 text-white font-semibold px-3.5 py-2 rounded-xl text-xs transition flex items-center gap-1.5 whitespace-nowrap animate-pulse";
      txt.textContent = "Detener";
      banner.classList.remove('hidden');
      msg.textContent = "Grabando compromiso por voz...";
    } else {
      btn.className = "bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 font-semibold px-3.5 py-2 rounded-xl text-xs transition flex items-center gap-1.5 whitespace-nowrap";
      txt.textContent = "Dictar";
    }
  }
}

async function enviarAudioTransaccion(blobAudio) {
  const banner = document.getElementById('estado-media-ia');
  const msg = document.getElementById('mensaje-media-ia');
  banner.classList.remove('hidden');
  msg.textContent = "🎧 Analizando nota de voz con Gemini...";

  const formData = new FormData();
  formData.append('archivo', blobAudio, 'nota_voz.webm');
  formData.append('nota', document.getElementById('texto-ia').value.trim());
  formData.append('cuenta', document.getElementById('ia-cuenta').value);

  try {
    const data = await api('/registrar-transaccion-media', { method: 'POST', body: formData });
    mostrarAlerta(data.message || '✅ Movimiento(s) por voz registrados exitosamente.');
    document.getElementById('texto-ia').value = '';
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('⚠️ ' + err.message, true);
  } finally {
    banner.classList.add('hidden');
  }
}

async function enviarAudioCompromiso(blobAudio) {
  const banner = document.getElementById('estado-media-comp');
  const msg = document.getElementById('mensaje-media-comp');
  banner.classList.remove('hidden');
  msg.textContent = "🎧 Interpretando compromiso por voz con Gemini...";

  const formData = new FormData();
  formData.append('audio', blobAudio, 'compromiso_voz.webm');

  try {
    const data = await api('/compromisos/ia-audio', { method: 'POST', body: formData });
    mostrarAlerta(`✅ Compromiso agregado por voz: ${data.compromiso.nombre} (${formatoMoneda.format(data.compromiso.monto_cuota)}/mes)`);
    toggleFormNuevoCompromiso();
    await cargarCompromisos();
  } catch (err) {
    mostrarAlerta('⚠️ ' + err.message, true);
  } finally {
    banner.classList.add('hidden');
  }
}

// Reduce resolución y peso de la imagen antes de enviarla a Gemini
function comprimirImagen(archivo, maxAncho = 1280, calidad = 0.82) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        if (width > maxAncho) {
          height = Math.round((height * maxAncho) / width);
          width = maxAncho;
        }
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob((blob) => resolve(blob || archivo), 'image/jpeg', calidad);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(archivo);
  });
}

async function procesarImagenesSeleccionadas(event) {
  const archivos = Array.from(event.target.files);
  if (!archivos.length) return;

  const banner = document.getElementById('estado-media-ia');
  const msg = document.getElementById('mensaje-media-ia');
  const btnFoto = document.getElementById('btn-foto-ia');

  banner.classList.remove('hidden');
  msg.textContent = `📷 Leyendo comprobante(s) con Gemini...`;
  btnFoto.disabled = true;

  try {
    const formData = new FormData();
    for (let i = 0; i < archivos.length; i++) {
      const optimizada = await comprimirImagen(archivos[i]);
      formData.append('archivos', optimizada, `comprobante_${i + 1}.jpg`);
    }
    formData.append('nota', document.getElementById('texto-ia').value.trim());
    formData.append('cuenta', document.getElementById('ia-cuenta').value);

    const data = await api('/registrar-transaccion-media', { method: 'POST', body: formData });
    mostrarAlerta(data.message || '✅ Comprobante(s) registrado(s) exitosamente.');
    document.getElementById('texto-ia').value = '';
    await sincronizarTodo();
  } catch (err) {
    mostrarAlerta('❌ ' + err.message, true);
  } finally {
    banner.classList.add('hidden');
    btnFoto.disabled = false;
    event.target.value = '';
  }
}
