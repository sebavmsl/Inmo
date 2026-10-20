import { calcularValorActualizado } from "@/lib/indices/calculo";
import { ahoraEnArgentina } from "@/lib/fechas";
import { actualizaConIndice, armarPrevisualizacion, resumenAlta, type ResumenAlta } from "@/lib/carga/armadoAlta";
import type { DatosAltaContrato, PrevisualizacionAlta } from "@/lib/carga/tipos";
import type { FechaPartes } from "@/lib/carga/calculoContrato";

export function hoyArgentina(): FechaPartes {
  const p = ahoraEnArgentina();
  return { anio: p.anio, mes: p.mes, dia: p.dia };
}

/**
 * Consulta el alquiler de cada ciclo de actualización ya cumplido
 * (monto inicial × índice del ciclo ÷ índice del inicio, igual que
 * Python y que Pagos). Un ciclo que falla queda en null y la
 * previsualización usa el último monto conocido, con aviso.
 */
async function consultarMontosPorCiclo(d: DatosAltaContrato, r: ResumenAlta): Promise<Map<number, number | null>> {
  const montos = new Map<number, number | null>();
  if (!actualizaConIndice(d) || r.ciclos.length === 0) return montos;
  const inicio = new Date(`${d.fechaInicio}T00:00:00Z`);
  // En serie: ICL y UVA comparten la descarga por año (memoizada), y así
  // no se le piden N archivos a la vez al BCRA.
  for (const ciclo of r.ciclos) {
    try {
      montos.set(ciclo, await calcularValorActualizado(d.indice, d.montoInicial, inicio, ciclo * d.frecuenciaMeses));
    } catch {
      montos.set(ciclo, null);
    }
  }
  return montos;
}

export async function previsualizarAltaContrato(d: DatosAltaContrato): Promise<PrevisualizacionAlta> {
  const r = resumenAlta(d, hoyArgentina());
  const montos = await consultarMontosPorCiclo(d, r);
  return armarPrevisualizacion(d, r, montos);
}
