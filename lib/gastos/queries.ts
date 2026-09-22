import { createClient } from "@/lib/supabase/server";

export interface FilaGasto {
  id: number;
  propiedad: string;
  propietario: string;
  fecha: string;
  categoria: string;
  descripcion: string;
  monto: number;
  cotizacionUsd: number | null;
  montoUsd: number | null;
  proveedor: string | null;
  comprobante: string | null;
  pagadoPor: string;
  tipoGasto: string;
  observaciones: string | null;
}

/**
 * Módulo 2 (Tier A) — Historial de Gastos. Puerto de la subpestaña
 * "📋 Historial de Gastos" de app.py (líneas ~7863-7920): mismos
 * filtros (propiedad, categoría, texto libre) y mismos 4 totales.
 * `gastos_propiedades` usa `propiedad_id` (FK numérica) en vez del
 * `alias_propiedad` de texto que usa `pagos_historial` — se resuelve acá
 * con un join manual contra `propiedades`, igual criterio que
 * lib/historial/queries.ts.
 */
export async function getHistorialGastos(propietarioFiltro?: string, empresaFiltro?: number | null): Promise<FilaGasto[]> {
  const supabase = await createClient();

  let propiedadesQuery = supabase.from("propiedades").select("id, alias_propiedad, propietario");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  if (empresaFiltro !== undefined) {
    propiedadesQuery =
      empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
  }
  const { data: propiedades, error: errProp } = await propiedadesQuery;
  if (errProp) throw new Error(`[Gastos] Error cargando propiedades: ${errProp.message}`);

  const hayFiltroDePropiedades = Boolean(propietarioFiltro) || empresaFiltro !== undefined;
  const mapaPropiedades = new Map((propiedades ?? []).map((p) => [p.id, p]));
  if (hayFiltroDePropiedades && mapaPropiedades.size === 0) return [];

  let gastosQuery = supabase
    .from("gastos_propiedades")
    .select(
      "id, propiedad_id, fecha, categoria, descripcion, monto, cotizacion_usd, proveedor, comprobante, pagado_por, tipo_gasto, observaciones"
    )
    .order("fecha", { ascending: false });
  if (hayFiltroDePropiedades) gastosQuery = gastosQuery.in("propiedad_id", Array.from(mapaPropiedades.keys()));

  const { data: gastos, error } = await gastosQuery;
  if (error) throw new Error(`[Gastos] Error cargando gastos: ${error.message}`);

  return (gastos ?? []).flatMap((g) => {
    const propiedad = mapaPropiedades.get(g.propiedad_id);
    if (!propiedad) return []; // gasto de una propiedad que ya no matchea el filtro de propietario
    return [
      {
        id: g.id,
        propiedad: propiedad.alias_propiedad,
        propietario: propiedad.propietario,
        fecha: g.fecha,
        categoria: g.categoria,
        descripcion: g.descripcion,
        monto: g.monto,
        cotizacionUsd: g.cotizacion_usd,
        montoUsd: g.cotizacion_usd && g.cotizacion_usd > 0 ? g.monto / g.cotizacion_usd : null,
        proveedor: g.proveedor,
        comprobante: g.comprobante,
        pagadoPor: g.pagado_por,
        tipoGasto: g.tipo_gasto,
        observaciones: g.observaciones,
      },
    ];
  });
}
