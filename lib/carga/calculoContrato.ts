/**
 * Cálculos puros del alta de contratos (Entrega 2 — V2.018).
 *
 * Replican las fórmulas de la pestaña "Carga de Contratos" de Python
 * (app.py, deploy 2, líneas ~5420-5510) para que un contrato cargado
 * desde la v2 quede igual que uno cargado desde Python:
 *
 *   - Duración: meses entre inicio y fin (relativedelta), +1 si sobran
 *     días y el día de fin no coincide con el de inicio.
 *   - Mes del contrato: meses transcurridos desde el inicio + 1.
 *   - Próxima actualización: inicio + k × frecuencia, la primera que no
 *     quedó en el pasado. Sin actualización: el día siguiente al fin.
 *   - Fin por defecto: inicio + 2 años − 1 día.
 *
 * Todas las fechas son texto "YYYY-MM-DD" (como las guarda Python) y la
 * aritmética de meses recorta al último día del mes, igual que
 * relativedelta (31/01 + 1 mes = 28/02 o 29/02).
 *
 * Sin dependencias: se puede probar con `node --experimental-strip-types`.
 */

export interface FechaPartes {
  anio: number;
  mes: number; // 1-12
  dia: number;
}

function dos(n: number): string {
  return String(n).padStart(2, "0");
}

export function diasDelMes(anio: number, mes: number): number {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}

/** Lee "YYYY-MM-DD" (o "DD/MM/YYYY", por datos viejos). null si no es una fecha válida. */
export function leerFechaISO(valor: string | null | undefined): FechaPartes | null {
  const v = (valor ?? "").trim();
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  let p: FechaPartes | null = null;
  if (m) p = { anio: Number(m[1]), mes: Number(m[2]), dia: Number(m[3]) };
  else {
    m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(v);
    if (m) p = { anio: Number(m[3]), mes: Number(m[2]), dia: Number(m[1]) };
  }
  if (!p || p.mes < 1 || p.mes > 12 || p.dia < 1 || p.dia > diasDelMes(p.anio, p.mes)) return null;
  return p;
}

export function aISO(p: FechaPartes): string {
  return `${p.anio}-${dos(p.mes)}-${dos(p.dia)}`;
}

export function aTextoAR(p: FechaPartes): string {
  return `${dos(p.dia)}/${dos(p.mes)}/${p.anio}`;
}

function comparar(a: FechaPartes, b: FechaPartes): number {
  return a.anio - b.anio || a.mes - b.mes || a.dia - b.dia;
}

/** Suma meses recortando al último día del mes (como relativedelta). */
export function sumarMeses(p: FechaPartes, meses: number): FechaPartes {
  const total = p.anio * 12 + (p.mes - 1) + meses;
  const anio = Math.floor(total / 12);
  const mes = (total % 12) + 1;
  return { anio, mes, dia: Math.min(p.dia, diasDelMes(anio, mes)) };
}

export function sumarDias(p: FechaPartes, dias: number): FechaPartes {
  const d = new Date(Date.UTC(p.anio, p.mes - 1, p.dia + dias));
  return { anio: d.getUTCFullYear(), mes: d.getUTCMonth() + 1, dia: d.getUTCDate() };
}

/** relativedelta(hasta, desde): años, meses y días completos (asume hasta >= desde). */
function relativedelta(hasta: FechaPartes, desde: FechaPartes): { meses: number; dias: number } {
  if (comparar(hasta, desde) < 0) {
    const r = relativedelta(desde, hasta);
    return { meses: -r.meses, dias: -r.dias };
  }
  let meses = (hasta.anio - desde.anio) * 12 + (hasta.mes - desde.mes);
  if (comparar(sumarMeses(desde, meses), hasta) > 0) meses -= 1;
  const base = sumarMeses(desde, meses);
  const dias = Math.round(
    (Date.UTC(hasta.anio, hasta.mes - 1, hasta.dia) - Date.UTC(base.anio, base.mes - 1, base.dia)) / 86400000
  );
  return { meses, dias };
}

/** Duración en meses, fórmula de Python. */
export function calcularDuracion(inicio: FechaPartes, fin: FechaPartes): number {
  const r = relativedelta(fin, inicio);
  let meses = r.meses;
  if (r.dias > 0 && fin.dia !== inicio.dia) meses += 1;
  return Math.max(0, meses);
}

/** Fin por defecto de Python: inicio + 2 años − 1 día. */
export function finPorDefecto(inicio: FechaPartes): FechaPartes {
  return sumarDias(sumarMeses(inicio, 24), -1);
}

/** Mes del contrato que corre hoy (1 = el mes del inicio). */
export function calcularMesActual(inicio: FechaPartes, hoy: FechaPartes): number {
  const r = relativedelta(hoy, inicio);
  return Math.max(0, r.meses) + 1;
}

/** Próxima actualización, fórmula de Python. */
export function calcularProxActualizacion(
  inicio: FechaPartes,
  fin: FechaPartes,
  frecuenciaMeses: number,
  hoy: FechaPartes
): FechaPartes {
  if (!frecuenciaMeses || frecuenciaMeses <= 0) return sumarDias(fin, 1);
  let k = 1;
  let prox = sumarMeses(inicio, frecuenciaMeses);
  while (comparar(prox, hoy) < 0) {
    k += 1;
    prox = sumarMeses(inicio, frecuenciaMeses * k);
  }
  return prox;
}

/** Ciclo de actualización al que pertenece un mes del contrato (0 = monto inicial). */
export function cicloDelMes(nroMes: number, frecuenciaMeses: number): number {
  if (!frecuenciaMeses || frecuenciaMeses <= 0) return 0;
  return Math.floor((nroMes - 1) / frecuenciaMeses);
}

/** Fecha de vencimiento de un mes del contrato: el día elegido, recortado al último día del mes. */
export function vencimientoDelMes(inicio: FechaPartes, nroMes: number, diaVencimiento: number): FechaPartes {
  const mesCal = sumarMeses({ ...inicio, dia: 1 }, nroMes - 1);
  const dia = Math.min(Math.max(1, Math.floor(diaVencimiento) || 10), diasDelMes(mesCal.anio, mesCal.mes));
  return { anio: mesCal.anio, mes: mesCal.mes, dia };
}

const NOMBRES_MES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

export function nombreMesCalendario(inicio: FechaPartes, nroMes: number): string {
  const m = sumarMeses({ ...inicio, dia: 1 }, nroMes - 1);
  return `${NOMBRES_MES[m.mes - 1]} ${m.anio}`;
}

export function redondear2(n: number): number {
  return Math.round((Number.isFinite(n) ? n : 0) * 100) / 100;
}

/**
 * Cuota de un total pactado para el mes `nroMes` (las cuotas se cobran
 * en los primeros meses del contrato). La última cuota absorbe el
 * redondeo, así la suma da exacto el total.
 */
export function cuotaDelMes(total: number, cuotas: number, nroMes: number): number {
  const n = Math.max(1, Math.floor(cuotas) || 1);
  if (!total || total <= 0 || nroMes < 1 || nroMes > n) return 0;
  const porCuota = redondear2(total / n);
  return nroMes < n ? porCuota : redondear2(total - porCuota * (n - 1));
}

/** Formato de moneda de Python: "$1.234.567,89". */
export function monedaPython(n: number): string {
  const [entero, dec] = Math.abs(n).toFixed(2).split(".");
  const conPuntos = (entero ?? "0").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${n < 0 ? "-" : ""}$${conPuntos},${dec ?? "00"}`;
}

export type Cargo = "Inquilino" | "Propietario";

/**
 * Texto de la columna `servicios`, con el mismo formato que arma Python.
 * Python lo LEE: saca el alquiler vigente de "[Alq.Actualizado: $…]" y
 * decide si el impuesto inmobiliario va al inquilino buscando
 * "[Imp.Inmob: Inquilino]". Por eso hay que escribirlo igual.
 * Los identificadores (NIS, cuentas) ya viven en la propiedad; van en 0/vacío
 * como cuando se dejan sin completar en Python.
 */
export function textoServiciosPython(p: {
  alquilerVigente: number;
  cargos: {
    electricidad: Cargo;
    gas: Cargo;
    municipalidad: Cargo;
    ooss: Cargo;
    expensas: Cargo;
    impInmobiliario: Cargo;
  };
}): string {
  const c = p.cargos;
  const identificadores = "[NIS: 0] [Cta Gas: ] [Finca: ] [Cta OO.SS.: ]";
  const detalle = `| Elec: ${c.electricidad} | Gas: ${c.gas} | Mun: ${c.municipalidad} | OOSS: ${c.ooss} | Exp: ${c.expensas} | Inmob: ${c.impInmobiliario}`;
  return `[Alq.Actualizado: ${monedaPython(p.alquilerVigente)} | Imp.Inmob: ${c.impInmobiliario}] ${identificadores} ${detalle}`;
}

export const TIPOS_GARANTIA = [
  "Sin Garantía",
  "Depósito",
  "Solo Pagaré",
  "Pagaré y Depósito",
  "Propietario",
  "Recibo de Sueldo",
  "Bien Inmueble",
  "Aval Bancario",
  "Otro",
] as const;
export type TipoGarantia = (typeof TIPOS_GARANTIA)[number];

export function tieneDeposito(tipo: string): boolean {
  return tipo === "Depósito" || tipo === "Pagaré y Depósito";
}
export function tienePagare(tipo: string): boolean {
  return tipo === "Solo Pagaré" || tipo === "Pagaré y Depósito";
}

/** Columna `garantia` de Python: estado del depósito. */
export function estadoGarantiaPython(tipo: string, total: number, pagado: number): string {
  if (!tieneDeposito(tipo) || !total || total <= 0) return "Sin Depósito";
  return pagado >= total - 0.005 ? "Depositada Completa" : "Financiando";
}
