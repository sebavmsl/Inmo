import { createClient } from "@/lib/supabase/server";

/**
 * Puerto de la definición real de "pagado" de v1 (app.py línea 1549,
 * Módulo 3 — Planilla): "pagado este mes" = existe un pago registrado
 * en `pagos_historial` con `fecha` dentro del mes calendario ACTUAL, y
 * el `saldo_pendiente` de ESE pago puntual quedó en 0 (o a favor). Si
 * no hay ningún pago este mes, es PENDIENTE — sin importar cuánto haya
 * quedado saldado en meses anteriores.
 *
 * BUG encontrado en producción (sesión de depuración, V2.014): el
 * puerto original (lib/planilla/queries.ts,
 * app/(protected)/planilla/actions.ts) usaba `contratos.saldo_actual <=
 * 0` — la cuenta corriente GLOBAL y acumulada del contrato — como
 * "pagado". Un contrato que quedó saldado en $0 el mes pasado y
 * todavía no tuvo NINGÚN movimiento cargado este mes aparecía "pagado"
 * igual, porque el saldo acumulado seguía en cero. Recién empezando a
 * usar v2 para cobrar, con casi ningún pago cargado todavía en el mes
 * en curso, esto hacía que la Planilla mostrara TODOS los contratos
 * como pagados. `saldo_actual` sigue siendo correcto y útil para la
 * columna "Saldo" (cuánto se debe en total) — el bug era usarlo también
 * como el criterio de "¿pagado ESTE mes?", que es una pregunta distinta.
 */

function primerYUltimoDiaMesActual(): { desde: string; hasta: string } {
  const hoy = new Date();
  const anio = hoy.getFullYear();
  const mes = hoy.getMonth() + 1; // 1-12
  const desde = `${anio}-${String(mes).padStart(2, "0")}-01`;
  const [anioSig, mesSig] = mes === 12 ? [anio + 1, 1] : [anio, mes + 1];
  const hasta = `${anioSig}-${String(mesSig).padStart(2, "0")}-01`;
  return { desde, hasta };
}

/**
 * Para varios contratos a la vez (Planilla, WhatsApp masivo). Devuelve
 * un mapa código de contrato → `saldo_pendiente` del ÚLTIMO pago
 * registrado este mes calendario (ausente si no hubo ninguno).
 */
export async function obtenerUltimoPagoDelMesPorContrato(codigos: string[]): Promise<Map<string, number>> {
  const resultado = new Map<string, number>();
  if (codigos.length === 0) return resultado;

  const supabase = await createClient();
  const { desde, hasta } = primerYUltimoDiaMesActual();

  const { data, error } = await supabase
    .from("pagos_historial")
    .select("codigo_contrato, saldo_pendiente, fecha, id")
    .in("codigo_contrato", codigos)
    .gte("fecha", desde)
    .lt("fecha", hasta)
    .order("id", { ascending: false });
  if (error) throw new Error(`[Pagos] Error cargando pagos del mes actual: ${error.message}`);

  for (const p of data ?? []) {
    if (!resultado.has(p.codigo_contrato)) resultado.set(p.codigo_contrato, p.saldo_pendiente);
  }
  return resultado;
}

/**
 * true si el ÚLTIMO pago de ESTE mes calendario para ese contrato dejó
 * el saldo en 0 o a favor. Sin ningún pago este mes, siempre false —
 * `saldoPendienteUltimoPagoDelMes` viene de
 * `obtenerUltimoPagoDelMesPorContrato()`, `undefined` = no hubo pago.
 */
export function estaPagadoEsteMes(saldoPendienteUltimoPagoDelMes: number | undefined): boolean {
  return saldoPendienteUltimoPagoDelMes !== undefined && saldoPendienteUltimoPagoDelMes <= 0;
}
