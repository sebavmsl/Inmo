import { createClient } from "@/lib/supabase/server";

export interface FilaIngresoMetrica {
  propiedad: string;
  propietario: string;
  grupo: string | null;
  mes: string; // YYYY-MM, calendario real (fecha del pago) — ver nota de diseño abajo
  alquiler: number;
  cochera: number;
  expensas: number;
  totalIngreso: number;
  gastoAdmin: number;
  impInmobiliario: number;
  cotizacionUsd: number | null;
}

export interface FilaGastoMetrica {
  propiedad: string;
  propietario: string;
  grupo: string | null;
  mes: string;
  totalGasto: number;
  cotizacionUsd: number | null;
}

export interface DatosMetricasGastos {
  ingresos: FilaIngresoMetrica[];
  gastos: FilaGastoMetrica[];
  propiedades: { alias: string; propietario: string; grupo: string | null }[];
}

/**
 * Módulo 2 (Tier B) — datos crudos para el panel de métricas
 * "Ingresos vs. Gastos por Propiedad" (ver PanelMetricas.tsx, que hace
 * el filtrado/agregación/gráfico en el cliente).
 *
 * SIMPLIFICACIÓN DE DISEÑO respecto a v1 (documentar en DESIGN_LOG.md):
 * v1 agrupaba por "mes calendario" reconstruido a partir de
 * `inicio_contrato + nro_periodo` (porque `periodo` es texto tipo
 * "Mes 3 de 12", no una fecha). v2 agrupa directo por
 * `pagos_historial.fecha` (la fecha REAL del cobro, que si existe en
 * v2 y no hacía falta reconstruir) — mismo resultado práctico, sin la
 * complejidad de recalcular el calendario a mano. `gastos_propiedades`
 * ya usaba `fecha` real en los dos lados, así que la comparación es
 * consistente.
 */
export async function getDatosMetricasGastos(
  propietarioFiltro?: string,
  empresaFiltro?: number | null
): Promise<DatosMetricasGastos> {
  const supabase = await createClient();

  let propQuery = supabase.from("propiedades").select("id, alias_propiedad, propietario, grupo");
  if (propietarioFiltro) propQuery = propQuery.eq("propietario", propietarioFiltro);
  if (empresaFiltro !== undefined) {
    propQuery = empresaFiltro === null ? propQuery.is("empresa_id", null) : propQuery.eq("empresa_id", empresaFiltro);
  }
  const { data: propiedades, error: errProp } = await propQuery;
  if (errProp) throw new Error(`[Métricas Gastos] Error cargando propiedades: ${errProp.message}`);

  const hayFiltroDePropiedades = Boolean(propietarioFiltro) || empresaFiltro !== undefined;
  if (hayFiltroDePropiedades && (!propiedades || propiedades.length === 0)) {
    return { ingresos: [], gastos: [], propiedades: [] };
  }

  const mapaPorAlias = new Map((propiedades ?? []).map((p) => [p.alias_propiedad, p]));
  const mapaPorId = new Map((propiedades ?? []).map((p) => [p.id, p]));

  let pagosQuery = supabase
    .from("pagos_historial")
    .select("propiedad, fecha, monto_alquiler, monto_cochera, monto_expensas, monto_gasto_admin, monto_imp_inmobiliario, cotizacion_usd");
  if (hayFiltroDePropiedades) pagosQuery = pagosQuery.in("propiedad", Array.from(mapaPorAlias.keys()));
  const { data: pagos, error: errPagos } = await pagosQuery;
  if (errPagos) throw new Error(`[Métricas Gastos] Error cargando pagos: ${errPagos.message}`);

  let gastosQuery = supabase.from("gastos_propiedades").select("propiedad_id, fecha, monto, cotizacion_usd");
  if (hayFiltroDePropiedades) gastosQuery = gastosQuery.in("propiedad_id", Array.from(mapaPorId.keys()));
  const { data: gastos, error: errGastos } = await gastosQuery;
  if (errGastos) throw new Error(`[Métricas Gastos] Error cargando gastos: ${errGastos.message}`);

  const ingresos: FilaIngresoMetrica[] = (pagos ?? []).flatMap((p) => {
    const prop = mapaPorAlias.get(p.propiedad);
    if (!prop) return [];
    return [
      {
        propiedad: p.propiedad,
        propietario: prop.propietario,
        grupo: prop.grupo,
        mes: p.fecha.slice(0, 7),
        alquiler: p.monto_alquiler,
        cochera: p.monto_cochera,
        expensas: p.monto_expensas,
        totalIngreso: p.monto_alquiler + p.monto_cochera + p.monto_expensas,
        gastoAdmin: p.monto_gasto_admin,
        impInmobiliario: p.monto_imp_inmobiliario,
        cotizacionUsd: p.cotizacion_usd,
      },
    ];
  });

  const gastosMetrica: FilaGastoMetrica[] = (gastos ?? []).flatMap((g) => {
    const prop = mapaPorId.get(g.propiedad_id);
    if (!prop) return [];
    return [
      {
        propiedad: prop.alias_propiedad,
        propietario: prop.propietario,
        grupo: prop.grupo,
        mes: g.fecha.slice(0, 7),
        totalGasto: g.monto,
        cotizacionUsd: g.cotizacion_usd,
      },
    ];
  });

  return {
    ingresos,
    gastos: gastosMetrica,
    propiedades: (propiedades ?? []).map((p) => ({ alias: p.alias_propiedad, propietario: p.propietario, grupo: p.grupo })),
  };
}
