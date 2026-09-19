import { obtenerIclBcraXls, obtenerIpcIndec, obtenerUvaBcraXls } from "@/lib/indices/fuentes";
import type { IndiceActualizacion } from "@/lib/types/database.types";

/**
 * Puerto de `_buscar_valor_mas_cercano()` (app.py línea 1897): busca en
 * la serie el valor más cercano a `fechaTarget`, retrocediendo día por
 * día hasta `diasMax`. Tolera huecos en la serie (ICL es diario, IPC es
 * mensual — por eso IPC usa un `diasMax` mayor).
 */
function buscarValorMasCercano(
  fechaTarget: Date,
  serie: Record<string, number>,
  diasMax: number
): number | null {
  for (let delta = 0; delta <= diasMax; delta++) {
    const fecha = new Date(fechaTarget);
    fecha.setDate(fecha.getDate() - delta);
    const clave = fecha.toISOString().slice(0, 10);
    if (clave in serie) return serie[clave] ?? null;
  }
  return null;
}

function sumarMeses(fecha: Date, meses: number): Date {
  const resultado = new Date(fecha);
  resultado.setMonth(resultado.getMonth() + meses);
  return resultado;
}

export interface ResultadoCalculoIndice {
  valorNuevo: number;
  fechaInicio: string;
  fechaActualizacion: string;
}

/**
 * Puerto de `calcular_valor_actualizado_icl()` (línea 1909):
 * valor_nuevo = monto_inicial × (ICL_actualización / ICL_inicio)
 */
export async function calcularValorActualizadoIcl(
  montoInicial: number,
  fechaInicio: Date,
  mesesIntervalo: number
): Promise<number | null> {
  const fechaActualizacion = sumarMeses(fechaInicio, mesesIntervalo);
  const anios = new Set([fechaInicio.getFullYear(), fechaActualizacion.getFullYear()]);

  let serie: Record<string, number> = {};
  for (const anio of anios) {
    const parcial = await obtenerIclBcraXls(anio);
    serie = { ...serie, ...parcial };
  }
  if (Object.keys(serie).length === 0) return null;

  const iclInicio = buscarValorMasCercano(fechaInicio, serie, 10);
  const iclActual = buscarValorMasCercano(fechaActualizacion, serie, 10);

  if (iclInicio && iclActual && iclInicio > 0) {
    return Math.round(montoInicial * (iclActual / iclInicio));
  }
  return null;
}

/**
 * Puerto de `calcular_valor_actualizado_ipc()` (línea 1939):
 * valor_nuevo = monto_inicial × (IPC_mes_actualización / IPC_mes_inicio)
 */
export async function calcularValorActualizadoIpc(
  montoInicial: number,
  fechaInicio: Date,
  mesesIntervalo: number
): Promise<number | null> {
  const fechaActualizacion = sumarMeses(fechaInicio, mesesIntervalo);
  const serie = await obtenerIpcIndec();
  if (Object.keys(serie).length === 0) return null;

  const ipcInicio = buscarValorMasCercano(fechaInicio, serie, 45);
  const ipcActual = buscarValorMasCercano(fechaActualizacion, serie, 45);

  if (ipcInicio && ipcActual && ipcInicio > 0) {
    return Math.round(montoInicial * (ipcActual / ipcInicio));
  }
  return null;
}

/**
 * UVA — nuevo en v2 (ver docs/DESIGN_LOG.md, "Ampliación del motor de
 * índices"). Misma fórmula y misma tolerancia que ICL (también es una
 * serie diaria del BCRA).
 */
export async function calcularValorActualizadoUva(
  montoInicial: number,
  fechaInicio: Date,
  mesesIntervalo: number
): Promise<number | null> {
  const fechaActualizacion = sumarMeses(fechaInicio, mesesIntervalo);
  const serie = await obtenerUvaBcraXls();
  if (Object.keys(serie).length === 0) return null;

  const uvaInicio = buscarValorMasCercano(fechaInicio, serie, 10);
  const uvaActual = buscarValorMasCercano(fechaActualizacion, serie, 10);

  if (uvaInicio && uvaActual && uvaInicio > 0) {
    return Math.round(montoInicial * (uvaActual / uvaInicio));
  }
  return null;
}

/**
 * Despachador único por tipo de índice. "Otro" nunca se calcula acá —
 * es responsabilidad humana (ver Módulo 5: la validación que bloquea
 * guardar hasta cargar un valor distinto al anterior). Llamarlo con
 * indice="Otro" es un error del caller, no un caso a resolver en
 * silencio.
 *
 * Siempre pega en vivo a la fuente externa — correcto para el botón
 * manual de la Planilla y para Módulo 4 (decisión explícita: recalcular
 * en vivo cada vez que se abre un contrato en Pagos). El cron diario
 * (paso 3) también usa esta misma función: la memoización en
 * lib/indices/fuentes.ts evita pedirle el mismo año a BCRA más de una
 * vez por ejecución, así que no hace falta una versión aparte "de
 * caché" — se descartó esa idea porque `indices_historicos` no puede
 * cubrir la historia completa de contratos viejos sin un backfill que
 * todavía no existe (ver docs/DESIGN_LOG.md).
 */
export async function calcularValorActualizado(
  indice: IndiceActualizacion,
  montoInicial: number,
  fechaInicio: Date,
  mesesIntervalo: number
): Promise<number | null> {
  switch (indice) {
    case "ICL":
      return calcularValorActualizadoIcl(montoInicial, fechaInicio, mesesIntervalo);
    case "IPC":
      return calcularValorActualizadoIpc(montoInicial, fechaInicio, mesesIntervalo);
    case "UVA":
      return calcularValorActualizadoUva(montoInicial, fechaInicio, mesesIntervalo);
    case "Otro":
      throw new Error(
        "El índice 'Otro' no tiene cálculo automático — se negocia caso por caso (ver Módulo 5)."
      );
    default:
      return null;
  }
}
