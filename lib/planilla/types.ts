import type { UrgenciaFila } from "@/lib/contratos/urgencia";
export type { UrgenciaFila };

export interface FilaPlanilla {
  codigo: string;
  aliasPropiedad: string;
  inquilino: string;
  telefono: string | null;
  finContrato: string | null;
  proxActualizacion: string | null;
  indice: string;
  alquilerMostrar: number; // prioridad: alquiler_calculado > alquiler vigente > monto_inicial
  cochera: number | null;
  saldoActual: number; // contratos.saldo_actual (cuenta corriente)
  pagado: boolean; // saldoActual <= 0, ver DESIGN_LOG.md "¿Pagado? — REDEFINIDO"
  urgencia: UrgenciaFila;
  archivado: boolean;
  estadoVencido: boolean; // finalizado_por = 'auto_vencimiento' && !archivado
  verificado: boolean;
  expensasAdhoc: number | null;
}
