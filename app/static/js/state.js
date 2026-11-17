// Estado de navegación
let pestanaActual = 'resumen';

// Datos cargados desde el backend
let todosLosMovimientos = [];
let todosLosCompromisos = [];
let todasLasCuentas = [];

// Filtro activo de análisis
let tipoAnalisisActual = 'Todos'; // 'Todos' | 'Egreso' | 'Ingreso'

// Instancias de Chart.js (destruir antes de recrear)
let chartDona = null;
let chartRanking = null;
let chartLineas = null;

// Grabación de audio
let mediaRecorder = null;
let audioChunks = [];
