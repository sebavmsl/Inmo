import { createClient } from "@/lib/supabase/server";

export interface FilaHistorial {
  nroComprobante: string | null;
  fecha: string;
  periodo: string; // "Mes N de M", relativo al contrato
  codigoContrato: string;
  propiedad: string;
  inquilino: string;
  tipoPago: string;
  montoAbonado: number;
  saldoPendiente: number; // cuenta corriente, ver DESIGN_LOG.md
  retencionAgencia: number; // FIX: antes hardcodeado en $0 (ver DESIGN_LOG.md, Módulo 6)
  metodoPago: string | null;
}

/**
 * Puerto de `_cached_historial_pagos()` — con el fix de "Retención
 * Agencia" (ver docs/DESIGN_LOG.md): v1 tenía `0 AS "_pct_admin"`
 * hardcodeado en la query. El dato real ya existe en cada fila
 * (`pagos_historial.monto_gasto_admin`, calculado automáticamente al
 * registrar el pago — ver Módulo 4) — acá simplemente se lee, sin
 * necesitar ningún join nuevo ni recálculo.
 */
export async function getHistorialPagos(propietarioFiltro?: string): Promise<FilaHistorial[]> {
  const supabase = await createClient();

  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  const { data: propiedades, error: errProp } = await propiedadesQuery;
  if (errProp) throw new Error(`[Historial] Error cargando propiedades: ${errProp.message}`);

  const aliasPermitidos = propietarioFiltro ? new Set((propiedades ?? []).map((p) => p.alias_propiedad)) : null;
  if (aliasPermitidos && aliasPermitidos.size === 0) return [];

  let pagosQuery = supabase
    .from("pagos_historial")
    .select(
      "nro_comprobante, fecha, periodo, codigo_contrato, propiedad, inquilino, tipo_pago, monto_abonado, saldo_pendiente, monto_gasto_admin, metodo_pago"
    )
    .order("fecha", { ascending: false });

  if (aliasPermitidos) pagosQuery = pagosQuery.in("propiedad", Array.from(aliasPermitidos));

  const { data: pagos, error } = await pagosQuery;
  if (error) throw new Error(`[Historial] Error cargando pagos: ${error.message}`);

  return (pagos ?? []).map((p) => ({
    nroComprobante: p.nro_comprobante,
    fecha: p.fecha,
    periodo: p.periodo,
    codigoContrato: p.codigo_contrato,
    propiedad: p.propiedad,
    inquilino: p.inquilino,
    tipoPago: p.tipo_pago,
    montoAbonado: p.monto_abonado,
    saldoPendiente: p.saldo_pendiente,
    retencionAgencia: p.monto_gasto_admin ?? 0,
    metodoPago: p.metodo_pago,
  }));
}
