import type { ContratoActivoDashboardRow } from "@/lib/dashboard/types";

/**
 * Puerto de `opciones_meses` (app.py línea 2557): en contratos viejos
 * `act_contrato` quedó guardado como etiqueta de texto en vez de un
 * número de meses. Frecuencias no contempladas caen en 6 (semestral),
 * igual que el `.get(str(_act_raw), 6)` original.
 */
const FRECUENCIA_A_MESES: Record<string, number> = {
  Mensual: 1,
  Bimensual: 2,
  Trimestral: 3,
  Cuatrimestral: 4,
  Semestral: 6,
  Anual: 12,
  Bianual: 24,
};

const MESES_A_ETIQUETA: Record<number, string> = {
  1: "Mensual",
  2: "Bimensual",
  3: "Trimestral",
  4: "Cuatrimestral",
  6: "Semestral",
  12: "Anual",
  24: "Bianual",
};

function frecuenciaEnMeses(actContrato: number | string | null): number {
  if (typeof actContrato === "number") return actContrato;
  if (actContrato && FRECUENCIA_A_MESES[actContrato] !== undefined) {
    return FRECUENCIA_A_MESES[actContrato];
  }
  return 6;
}

/** Acepta "YYYY-MM-DD" o "DD/MM/YYYY", igual que los dos `strptime` de v1. */
function parsearFecha(valor: string | null | undefined): Date | null {
  const v = (valor ?? "").trim();
  if (!v) return null;

  const isoMatch = v.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) {
    const [, y, m, d] = isoMatch;
    return new Date(Number(y), Number(m) - 1, Number(d));
  }

  const arMatch = v.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (arMatch) {
    const [, d, m, y] = arMatch;
    return new Date(Number(y), Number(m) - 1, Number(d));
  }

  return null;
}

function diasEntre(desde: Date, hasta: Date): number {
  const msPorDia = 1000 * 60 * 60 * 24;
  const desdeUTC = Date.UTC(desde.getFullYear(), desde.getMonth(), desde.getDate());
  const hastaUTC = Date.UTC(hasta.getFullYear(), hasta.getMonth(), hasta.getDate());
  return Math.round((hastaUTC - desdeUTC) / msPorDia);
}

function primerDiaDelMes(fecha: Date): Date {
  return new Date(fecha.getFullYear(), fecha.getMonth(), 1);
}

function mesSiguiente(fecha: Date): Date {
  return new Date(fecha.getFullYear(), fecha.getMonth() + 1, 1);
}

function mismoMes(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

export interface AlertaVencimiento {
  tipo: "vencimiento";
  inquilino: string;
  aliasPropiedad: string;
  diasParaVencer: number;
  fechaTexto: string;
}

export interface AlertaActualizacion {
  tipo: "actualizacion";
  urgencia: "este_mes" | "mes_proximo" | "fallback";
  inquilino: string;
  aliasPropiedad: string;
  frecuenciaLabel: string;
  proximaActualizacionTexto: string | null;
}

export interface DashboardMetrics {
  totalActivos: number;
  actualizanEsteMes: number;
  vencenPronto: number;
  cajaHistorica: number;
  alertasVencimiento: AlertaVencimiento[];
  alertasActualizacion: AlertaActualizacion[];
}

/**
 * Puerto directo del loop de cómputo del Dashboard (app.py líneas
 * 2542-2598). Función pura para poder testearla sin pegarle a la BD.
 */
export function calcularMetricasDashboard(
  contratos: ContratoActivoDashboardRow[],
  cajaHistorica: number,
  hoy: Date = new Date()
): DashboardMetrics {
  let vencenPronto = 0;
  let actualizanEsteMes = 0;
  const alertasVencimiento: AlertaVencimiento[] = [];
  const alertasActualizacion: AlertaActualizacion[] = [];

  const mesActual = primerDiaDelMes(hoy);
  const mesProximo = mesSiguiente(mesActual);

  for (const row of contratos) {
    // ── Vencimiento de contrato (ventana de 60 días) ──
    const finDt = parsearFecha(row.fin_contrato);
    if (finDt) {
      const dias = diasEntre(hoy, finDt);
      if (dias >= 0 && dias <= 60) {
        vencenPronto += 1;
        alertasVencimiento.push({
          tipo: "vencimiento",
          inquilino: row.inquilino,
          aliasPropiedad: row.alias_propiedad,
          diasParaVencer: dias,
          fechaTexto: row.fin_contrato ?? "",
        });
      }
    }

    // ── Actualización de alquiler (índice) ──
    const frecuencia = frecuenciaEnMeses(row.act_contrato);
    const frecuenciaLabel = MESES_A_ETIQUETA[frecuencia] ?? String(frecuencia);
    const proxStr = (row.prox_actualizacion ?? "").trim();

    if (proxStr) {
      const proxDt = parsearFecha(proxStr);
      if (proxDt) {
        const proxMes = primerDiaDelMes(proxDt);
        if (mismoMes(proxMes, mesActual)) {
          actualizanEsteMes += 1;
          alertasActualizacion.push({
            tipo: "actualizacion",
            urgencia: "este_mes",
            inquilino: row.inquilino,
            aliasPropiedad: row.alias_propiedad,
            frecuenciaLabel,
            proximaActualizacionTexto: proxStr,
          });
        } else if (mismoMes(proxMes, mesProximo)) {
          alertasActualizacion.push({
            tipo: "actualizacion",
            urgencia: "mes_proximo",
            inquilino: row.inquilino,
            aliasPropiedad: row.alias_propiedad,
            frecuenciaLabel,
            proximaActualizacionTexto: proxStr,
          });
        }
      }
    } else {
      // Fallback: sin prox_actualizacion cargada, usar mes_contrato % frecuencia
      const mesVivo = row.mes_contrato || 1;
      if ((mesVivo - 1) % frecuencia === 0 && mesVivo > 1) {
        actualizanEsteMes += 1;
        alertasActualizacion.push({
          tipo: "actualizacion",
          urgencia: "fallback",
          inquilino: row.inquilino,
          aliasPropiedad: row.alias_propiedad,
          frecuenciaLabel,
          proximaActualizacionTexto: null,
        });
      }
    }
  }

  return {
    totalActivos: contratos.length,
    actualizanEsteMes,
    vencenPronto,
    cajaHistorica,
    alertasVencimiento,
    alertasActualizacion,
  };
}
