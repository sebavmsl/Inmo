import { sumarMeses } from "@/lib/indices/calculo";

export interface EstadoActualizacionContrato {
  /** Próxima actualización, avanzando ciclo por ciclo desde el inicio hasta llegar a una fecha futura. */
  proxActualizacionCalculada: Date;
  /**
   * Meses entre el inicio del contrato y la ÚLTIMA actualización que ya
   * debería haberse aplicado (0 si todavía no pasó ningún ciclo
   * completo — recién arrancó el contrato).
   */
  mesesHastaUltimaAct: number;
  /** true si el contrato arrancó este mismo mes calendario. */
  mismoMesInicio: boolean;
}

/**
 * Puerto de la sección "REPLICACIÓN DE ALERTAS DE ACTUALIZACIÓN" de
 * app.py (Módulo 4 — Pagos, líneas 3569-3813).
 *
 * BUG encontrado en producción (sesión de depuración, V2.013):
 * lib/pagos/queries.ts (getContratoParaPago) recalculaba el índice en
 * vivo pasándole SIEMPRE "inicio_contrato + 1 × frecuencia" a
 * calcularValorActualizado — un único punto fijo, sin importar cuántos
 * ciclos ya pasaron de verdad. Para un contrato con más de un ciclo de
 * historia, eso apunta a una fecha vieja (no a la actualización vigente
 * real); para uno recién creado, apunta a una fecha FUTURA que ni
 * siquiera tiene datos de índice todavía — y ese cálculo prematuro es
 * justamente lo que generó el valor incorrecto que motivó este fix.
 *
 * v1 en cambio: (1) avanza "próxima actualización" ciclo por ciclo
 * hasta encontrar una fecha que todavía no llegó (`while prox < hoy:
 * prox += frecuencia`), (2) retrocede un ciclo desde ahí para obtener
 * la ÚLTIMA actualización ya vencida, y (3) exige que haya pasado AL
 * MENOS un ciclo completo (`mesesHastaUltimaAct > 0`) y que el contrato
 * no haya arrancado este mismo mes, antes de calcular nada. Si no se
 * cumple, v1 no calcula — muestra `alquiler`/`monto_inicial` tal cual
 * (ver lib/indices/alquilerVigente.ts).
 *
 * El resultado de acá se usa así: se le pasa `mesesHastaUltimaAct` (NO
 * la frecuencia cruda) como `mesesIntervalo` a calcularValorActualizado
 * — esa función ya calcula internamente
 * `fechaActualizacion = inicio + mesesIntervalo`, así que pasándole los
 * meses YA transcurridos hasta la última actualización vencida, apunta
 * exactamente a esa fecha (la lógica de cálculo en sí no cambia).
 */
export function calcularEstadoActualizacion(
  inicioContrato: Date,
  frecuenciaMeses: number,
  hoy: Date = new Date()
): EstadoActualizacionContrato {
  const mismoMesInicio =
    inicioContrato.getFullYear() === hoy.getFullYear() && inicioContrato.getMonth() === hoy.getMonth();

  if (!frecuenciaMeses || frecuenciaMeses <= 0) {
    return { proxActualizacionCalculada: inicioContrato, mesesHastaUltimaAct: 0, mismoMesInicio };
  }

  let proxActualizacionCalculada = sumarMeses(inicioContrato, frecuenciaMeses);
  while (proxActualizacionCalculada < hoy) {
    proxActualizacionCalculada = sumarMeses(proxActualizacionCalculada, frecuenciaMeses);
  }

  const ultimaActDt = sumarMeses(proxActualizacionCalculada, -frecuenciaMeses);
  // Ambas fechas comparten el mismo día del mes (se derivan de sumar
  // meses enteros desde inicioContrato), así que la diferencia en
  // meses es exacta sin necesitar aritmética de días.
  const mesesHastaUltimaAct =
    (ultimaActDt.getFullYear() - inicioContrato.getFullYear()) * 12 + (ultimaActDt.getMonth() - inicioContrato.getMonth());

  return { proxActualizacionCalculada, mesesHastaUltimaAct, mismoMesInicio };
}
