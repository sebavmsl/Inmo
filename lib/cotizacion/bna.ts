/**
 * Fuente: dólar oficial BNA vía api.bluelytics.com.ar — mismo endpoint
 * que usaba v1 (_obtener_cotizacion_bna(), app.py línea ~2485), mismo
 * campo (`oficial.value_sell`). Puerto directo, sin cambios de criterio.
 */
export async function fetchCotizacionBna(): Promise<number | null> {
  try {
    const res = await fetch("https://api.bluelytics.com.ar/v2/latest", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    const valor = Number(data?.oficial?.value_sell);
    return Number.isFinite(valor) && valor > 0 ? valor : null;
  } catch {
    // Caído, timeout, red bloqueada, lo que sea — nunca debe tirar abajo
    // el formulario de Pagos/Gastos. El llamador cae al último valor
    // conocido (ver lib/cotizacion/queries.ts).
    return null;
  }
}
