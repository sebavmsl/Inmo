import { clasificarUrgencia } from "@/lib/contratos/urgencia";

/**
 * "Editar Contrato" — bloqueo por actualización de índice pendiente.
 * Puerto simplificado de `bloqueo_por_actualizacion` en app.py (líneas
 * ~5642-5657): v1 mezclaba, en un único mega-formulario, la edición de
 * datos administrativos del contrato CON la actualización del alquiler
 * por índice — y bloqueaba el guardado de TODO si el contrato estaba en
 * su mes de actualización y todavía no se había cargado el nuevo valor.
 *
 * v2 separa esas dos cosas (la actualización de índice ya vive en
 * Planilla → "Actualizar Índices", ver actualizarIndicesManual()) — acá
 * se reusa el MISMO criterio de urgencia que pinta la Planilla
 * (lib/contratos/urgencia.ts) para bloquear la edición de otros campos
 * del contrato mientras haya una actualización de índice vencida o
 * vence este mes, en vez de dejar que se edite por arriba de un
 * alquiler desactualizado. "Mes próximo" (urgencia amarilla/celeste
 * temprana) NO bloquea — solo cuando ya está vencida o vence este mes.
 */
export function bloqueadoPorActualizacionPendiente(params: {
  estado: string;
  finContrato: string | null;
  proxActualizacion: string | null;
}): { bloqueado: boolean; motivo: string | null } {
  if (params.estado !== "Activo") return { bloqueado: false, motivo: null };

  const urgencia = clasificarUrgencia(params.finContrato, params.proxActualizacion);
  if (urgencia === "actualizar_este_mes") {
    return {
      bloqueado: true,
      motivo: "Este contrato tiene una actualización de índice pendiente para este mes. Actualizala desde Planilla antes de editar otros datos.",
    };
  }
  if (urgencia === "renovar") {
    return {
      bloqueado: true,
      motivo: "La próxima actualización de este contrato cae después de su fin — necesita renovarse (cargar un contrato nuevo) antes de editar otros datos.",
    };
  }
  return { bloqueado: false, motivo: null };
}

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
