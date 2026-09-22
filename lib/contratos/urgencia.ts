export type UrgenciaFila = "actualizar_este_mes" | "actualizar_mes_proximo" | "renovar" | "normal";

/**
 * Clasifica la urgencia de actualización de un contrato, mismo
 * criterio de colores que v1: amarillo (actualizar este mes) / celeste
 * (mes próximo) / rojo (RENOVAR: la próxima actualización cae después
 * del fin del contrato) / normal.
 *
 * Movido acá (antes vivía solo en lib/planilla/queries.ts) para que
 * Carga de Contratos (Editar Contrato, ver lib/carga/validaciones.ts)
 * use el MISMO criterio para bloquear la edición cuando hay una
 * actualización de índice pendiente, en vez de reimplementarlo.
 */
export function clasificarUrgencia(finContrato: string | null, proxActualizacion: string | null): UrgenciaFila {
  if (!proxActualizacion) return "normal";

  const hoy = new Date();
  const mesActual = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  const mesProximo = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 1);
  const prox = new Date(proxActualizacion);
  const proxMes = new Date(prox.getFullYear(), prox.getMonth(), 1);

  if (finContrato) {
    const fin = new Date(finContrato);
    if (prox > fin) return "renovar"; // la próxima actualización cae después de que termina el contrato
  }

  if (proxMes.getTime() === mesActual.getTime()) return "actualizar_este_mes";
  if (proxMes.getTime() === mesProximo.getTime()) return "actualizar_mes_proximo";
  return "normal";
}
