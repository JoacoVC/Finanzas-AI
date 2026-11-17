// Categorías predefinidas
const CATEGORIAS_EGRESO = ['Comida', 'Transporte', 'Suscripciones', 'Compras', 'Servicios', 'Ahorro', 'Préstamo', 'Deudas', 'Otros'];
const CATEGORIAS_INGRESO = ['Trabajo', 'Préstamo', 'Deudas', 'Otros'];

// Formato de moneda colombiana
const formatoMoneda = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0
});

// Clases CSS reutilizables para tabs de navegación principal
const CLS_TAB_ACTIVE = 'tab-btn-active py-2.5 px-5 text-sm transition flex items-center gap-2 whitespace-nowrap rounded-t-lg';
const CLS_TAB_INACTIVE = 'tab-btn-inactive py-2.5 px-5 text-sm transition flex items-center gap-2 whitespace-nowrap rounded-t-lg';

// Clases CSS para subtabs (formulario IA vs Manual en registro)
const CLS_REGFORM_ACTIVE = 'flex-1 py-3 text-xs sm:text-sm font-semibold text-blue-600 border-b-2 border-blue-600 bg-white transition flex items-center justify-center gap-1.5';
const CLS_REGFORM_INACTIVE = 'flex-1 py-3 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-800 transition flex items-center justify-center gap-1.5';

// Clases CSS para subtabs de compromisos (IA vs Manual)
const CLS_SUBTAB_ACTIVE = 'text-xs font-bold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg';
const CLS_SUBTAB_INACTIVE = 'text-xs font-bold text-slate-500 hover:text-slate-800 px-3 py-1.5 rounded-lg';

// Clases CSS para botones de análisis (Todos/Egreso/Ingreso)
const CLS_ANALYSIS_INACTIVE = 'px-3.5 py-1.5 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900 transition';
const CLS_ANALYSIS_TODOS   = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-blue-600 text-white shadow-xs transition';
const CLS_ANALYSIS_EGRESO  = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white shadow-xs transition';
const CLS_ANALYSIS_INGRESO = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 text-white shadow-xs transition';

// Meses en español (índice 0 = Enero, igual que Date.getMonth())
const MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
