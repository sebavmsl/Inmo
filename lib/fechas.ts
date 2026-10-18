/**
 * Manejo único de fechas de la v2 (Entrega 1 — V2.015).
 *
 * La base comparte datos con Python (Streamlit), que guarda las fechas de
 * pagos y liquidaciones como TEXTO en formato argentino:
 *   pagos_historial.fecha              → "29/09/2026 01:12"
 *   liquidaciones_propietarios.fecha_liquidacion → ídem
 * y las fechas de contratos/gastos como "YYYY-MM-DD".
 *
 * Antes de V2.015 la v2 trataba esos textos con `new Date(texto)`, que los
 * interpreta con formato de EE.UU. (MM/DD): "05/09/2026" pasaba a ser el
 * 9 de mayo y "29/09/2026" daba "Invalid Date". También filtraba por mes
 * comparando el texto ("fecha >= '2026-09-01'"), lo que con el formato de
 * Python nunca encuentra nada.
 *
 * Regla: todo lo que lea o escriba una de estas fechas pasa por acá.
 * Argentina usa UTC-3 fijo (sin horario de verano desde 2009).
 */

export const ZONA_HORARIA_AR = "America/Argentina/Buenos_Aires";
const OFFSET_AR_HORAS = 3;

export interface PartesFecha {
  anio: number;
  mes: number; // 1-12
  dia: number;
  hora: number;
  minuto: number;
}

function dos(n: number): string {
  return String(n).padStart(2, "0");
}

/** Partes de un instante (Date) vistas en hora argentina. */
export function partesEnArgentina(instante: Date): PartesFecha {
  const fmt = new Intl.DateTimeFormat("en-GB", {
    timeZone: ZONA_HORARIA_AR,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const valor = (tipo: string): number => {
    const parte = fmt.formatToParts(instante).find((p) => p.type === tipo);
    return Number(parte?.value ?? "0");
  };
  const hora = valor("hour");
  return { anio: valor("year"), mes: valor("month"), dia: valor("day"), hora: hora === 24 ? 0 : hora, minuto: valor("minute") };
}

/**
 * Lee cualquiera de los formatos que hay en la base:
 *   "DD/MM/YYYY", "DD/MM/YYYY HH:MM"            (Python, hora argentina)
 *   "YYYY-MM-DD", "YYYY-MM-DD HH:MM[:SS]"        (sin zona: se toma literal)
 *   "YYYY-MM-DDTHH:MM:SS(.sss)Z" o "...+00(:00)" (con zona: se pasa a hora argentina)
 * Devuelve null si el texto no es una fecha reconocible.
 */
export function parsearFecha(valor: string | null | undefined): PartesFecha | null {
  const v = (valor ?? "").trim();
  if (!v) return null;

  const ar = /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/.exec(v);
  if (ar) {
    const partes: PartesFecha = {
      dia: Number(ar[1] ?? "0"),
      mes: Number(ar[2] ?? "0"),
      anio: Number(ar[3] ?? "0"),
      hora: Number(ar[4] ?? "0"),
      minuto: Number(ar[5] ?? "0"),
    };
    return esValida(partes) ? partes : null;
  }

  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(v);
  if (iso) {
    const tieneZona = /[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(Z|[+-]\d{2}(?::?\d{2})?)$/.test(v);
    if (tieneZona) {
      const instante = new Date(v.replace(" ", "T").replace(/([+-]\d{2})$/, "$1:00"));
      if (!Number.isNaN(instante.getTime())) return partesEnArgentina(instante);
    }
    const partes: PartesFecha = {
      anio: Number(iso[1] ?? "0"),
      mes: Number(iso[2] ?? "0"),
      dia: Number(iso[3] ?? "0"),
      hora: Number(iso[4] ?? "0"),
      minuto: Number(iso[5] ?? "0"),
    };
    return esValida(partes) ? partes : null;
  }

  return null;
}

function esValida(p: PartesFecha): boolean {
  return p.anio > 1900 && p.mes >= 1 && p.mes <= 12 && p.dia >= 1 && p.dia <= 31 && p.hora <= 23 && p.minuto <= 59;
}

/** Instante real (Date) de unas partes en hora argentina. */
export function aInstante(p: PartesFecha): Date {
  return new Date(Date.UTC(p.anio, p.mes - 1, p.dia, p.hora + OFFSET_AR_HORAS, p.minuto));
}

/** Número para ordenar cronológicamente (0 si la fecha no se reconoce). */
export function valorOrden(valor: string | null | undefined): number {
  const p = parsearFecha(valor);
  return p ? aInstante(p).getTime() : 0;
}

/** "YYYY-MM" (para agrupar o filtrar por mes). "" si no se reconoce. */
export function claveMes(valor: string | null | undefined): string {
  const p = parsearFecha(valor);
  return p ? `${p.anio}-${dos(p.mes)}` : "";
}

/** "YYYY-MM-DD" (para comparar con un <input type="date">). "" si no se reconoce. */
export function claveDia(valor: string | null | undefined): string {
  const p = parsearFecha(valor);
  return p ? `${p.anio}-${dos(p.mes)}-${dos(p.dia)}` : "";
}

/** "DD/MM/YYYY" para mostrar. Si no se reconoce, devuelve el texto original (o "—"). */
export function formatearFecha(valor: string | null | undefined): string {
  const p = parsearFecha(valor);
  if (!p) return (valor ?? "").trim() || "—";
  return `${dos(p.dia)}/${dos(p.mes)}/${p.anio}`;
}

/** "DD/MM/YYYY HH:MM" para mostrar. Si no se reconoce, devuelve el texto original (o "—"). */
export function formatearFechaHora(valor: string | null | undefined): string {
  const p = parsearFecha(valor);
  if (!p) return (valor ?? "").trim() || "—";
  return `${dos(p.dia)}/${dos(p.mes)}/${p.anio} ${dos(p.hora)}:${dos(p.minuto)}`;
}

/** Hoy en Argentina. */
export function ahoraEnArgentina(): PartesFecha {
  return partesEnArgentina(new Date());
}

/** "YYYY-MM" del mes actual en Argentina. */
export function claveMesActual(): string {
  const p = ahoraEnArgentina();
  return `${p.anio}-${dos(p.mes)}`;
}

/** "YYYY-MM-DD" de hoy en Argentina. */
export function claveHoy(): string {
  const p = ahoraEnArgentina();
  return `${p.anio}-${dos(p.mes)}-${dos(p.dia)}`;
}

/** "DD/MM/YYYY HH:MM" de ahora en Argentina — el formato en que Python guarda la fecha de un pago. */
export function fechaHoraPythonAhora(): string {
  const p = ahoraEnArgentina();
  return `${dos(p.dia)}/${dos(p.mes)}/${p.anio} ${dos(p.hora)}:${dos(p.minuto)}`;
}
