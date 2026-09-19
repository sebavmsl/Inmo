/**
 * Regla de auto-finalizado del contrato viejo al cargar uno nuevo para
 * la misma propiedad — ver docs/DESIGN_LOG.md, "Auto-finalizado del
 * contrato viejo al renovar — REGLA FINAL".
 *
 *   ¿fin_contrato_viejo <= fin del mes actual?          (ya terminó o termina este mes)
 *   O ¿mes_contrato_viejo >= calc_duracion_viejo?        (ya no le quedan períodos por pagar)
 *
 *   → Si CUALQUIERA es cierta: FINALIZADO (terminó su curso normal)
 *   → Si NINGUNA es cierta: CANCELADO (se cortó antes de tiempo)
 *
 * A diferencia de v1 (que siempre marca 'Finalizado' sin distinguir
 * motivo, y solo si el contrato NUEVO también es 'Activo'), esto corre
 * SIEMPRE, sin esa condición — decisión de esta sesión, robustez ante
 * futuro sin costo real hoy.
 */
export function calcularMotivoFinalizacion(params: {
  finContratoViejo: string | null;
  mesContratoViejo: number | null;
  calcDuracionViejo: number | null;
}): "Finalizado" | "Cancelado" {
  const { finContratoViejo, mesContratoViejo, calcDuracionViejo } = params;

  const hoy = new Date();
  const finDeMesActual = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);

  const yaTermino = finContratoViejo ? new Date(finContratoViejo) <= finDeMesActual : false;
  const sinPeriodosRestantes =
    mesContratoViejo !== null && calcDuracionViejo !== null && mesContratoViejo >= calcDuracionViejo;

  return yaTermino || sinPeriodosRestantes ? "Finalizado" : "Cancelado";
}
