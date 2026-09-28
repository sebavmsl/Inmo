/**
 * Puerto de `_alquiler_display()` (app.py, línea 3018, Módulo 3 —
 * Planilla). Prioridad EXACTA de v1 para decidir qué alquiler mostrar:
 *
 *   1. `alquiler_calculado`, pero SOLO si `alquiler_calculado_fecha` es
 *      del mes calendario actual.
 *   2. `alquiler` (último vigente/cobrado).
 *   3. `monto_inicial`.
 *   4. 0.
 *
 * BUG encontrado en producción (sesión de depuración, V2.013): el
 * puerto original de esto (lib/planilla/queries.ts,
 * app/(protected)/planilla/actions.ts, app/portal/mi-cuenta/page.tsx,
 * lib/pagos/queries.ts) usaba `alquiler_calculado ?? alquiler ??
 * monto_inicial`, SIN el chequeo del paso 1 — un valor calculado en un
 * ciclo anterior (o, peor, para un ciclo que todavía no llegó) quedaba
 * mostrándose indefinidamente hasta el próximo recálculo real, en vez
 * de caer a `alquiler`/`monto_inicial` como hace v1. Esta función
 * centraliza el criterio correcto para los 4 lugares que lo necesitan.
 */
export function calcularAlquilerVigente(
  alquilerCalculado: number | null | undefined,
  alquilerCalculadoFecha: string | null | undefined,
  alquiler: number | null | undefined,
  montoInicial: number | null | undefined,
  hoy: Date = new Date()
): number {
  if (alquilerCalculado && alquilerCalculado > 0 && alquilerCalculadoFecha) {
    const fechaCalc = new Date(alquilerCalculadoFecha);
    if (
      !Number.isNaN(fechaCalc.getTime()) &&
      fechaCalc.getFullYear() === hoy.getFullYear() &&
      fechaCalc.getMonth() === hoy.getMonth()
    ) {
      return alquilerCalculado;
    }
  }
  if (alquiler && alquiler > 0) return alquiler;
  if (montoInicial && montoInicial > 0) return montoInicial;
  return 0;
}
