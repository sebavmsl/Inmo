import { createClient } from "@/lib/supabase/server";

export interface ResumenRendicion {
  propietario: string;
  periodoMes: string; // "YYYY-MM", calendario
  totalCobrado: number;
  comision: number;
  netoARendir: number;
  servicios: number; // informativo, no se descuenta
  otros: number; // informativo, no se descuenta
  saldoAnterior: number;
  gastosRetencion: { id: number; descripcion: string; monto: number }[];
  montoRetencionGastos: number;
  montoALiquidar: number;
  propiedades: number;
}

/**
 * Puerto de la sección de cálculo de Rendición (app.py líneas 8355-8390):
 * Neto a Rendir = (alquiler + cochera + expensas) − comisión (gasto_admin).
 * "Servicios" y "Otros" son informativos, NO se descuentan — ver
 * docs/DESIGN_LOG.md, "Aclaración importante: dos conceptos distintos
 * comparten el nombre honorarios".
 */
export async function calcularResumenRendicion(
  empresaId: number,
  propietario: string,
  periodoMes: string // "YYYY-MM"
): Promise<ResumenRendicion> {
  const supabase = await createClient();

  const desde = `${periodoMes}-01`;
  const [anioStr, mesStr] = periodoMes.split("-");
  const anio = Number(anioStr ?? new Date().getFullYear());
  const mes = Number(mesStr ?? new Date().getMonth() + 1);
  const hasta = new Date(anio, mes, 0).toISOString().slice(0, 10); // último día del mes

  const { data: propiedades } = await supabase
    .from("propiedades")
    .select("alias_propiedad")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario);
  const aliasPropiedades = (propiedades ?? []).map((p) => p.alias_propiedad);

  const { data: pagos } = await supabase
    .from("pagos_historial")
    .select("monto_alquiler, monto_cochera, monto_expensas, monto_gasto_admin, monto_imp_inmobiliario, monto_edesal, monto_gas, monto_municipalidad, monto_ooss, monto_honorarios, monto_garantia, monto_concepto_extra")
    .eq("empresa_id", empresaId)
    .in("propiedad", aliasPropiedades)
    .gte("fecha", desde)
    .lte("fecha", hasta);

  const filas = pagos ?? [];
  const totalCobrado = filas.reduce((a, p) => a + p.monto_alquiler + p.monto_cochera + p.monto_expensas, 0);
  const comision = filas.reduce((a, p) => a + (p.monto_gasto_admin ?? 0), 0);
  const servicios = filas.reduce(
    (a, p) => a + p.monto_imp_inmobiliario + p.monto_edesal + p.monto_gas + p.monto_municipalidad + p.monto_ooss,
    0
  );
  const otros = filas.reduce((a, p) => a + p.monto_honorarios + p.monto_garantia + p.monto_concepto_extra, 0);

  // Saldo anterior — última liquidación previa de este propietario (ver
  // DESIGN_LOG.md: v1 ya hace esto bien, toma solo la última, sin sumar
  // todos los períodos — el mismo patrón correcto que adoptamos para
  // contratos.saldo_actual).
  const { data: liquidacionAnterior } = await supabase
    .from("liquidaciones_propietarios")
    .select("saldo_pendiente")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario)
    .lt("periodo", periodoMes)
    .order("periodo", { ascending: false })
    .limit(1)
    .maybeSingle();
  const saldoAnterior = liquidacionAnterior?.saldo_pendiente ?? 0;

  // Gastos "Extraordinarios" pagados por alguien que no sea el
  // propietario, pendientes de retener.
  const { data: propiedadesConId } = await supabase
    .from("propiedades")
    .select("id")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario);
  const idsPropiedades = (propiedadesConId ?? []).map((p) => p.id);

  const { data: gastos } = await supabase
    .from("gastos_propiedades")
    .select("id, descripcion, monto")
    .eq("empresa_id", empresaId)
    .in("propiedad_id", idsPropiedades)
    .eq("tipo_gasto", "Extraordinario")
    .neq("pagado_por", "Propietario")
    .eq("cobrado", false);

  const gastosRetencion = gastos ?? [];
  const montoRetencionGastos = gastosRetencion.reduce((a, g) => a + g.monto, 0);
  const netoARendir = totalCobrado - comision;
  const montoALiquidar = netoARendir + saldoAnterior - montoRetencionGastos;

  return {
    propietario,
    periodoMes,
    totalCobrado,
    comision,
    netoARendir,
    servicios,
    otros,
    saldoAnterior,
    gastosRetencion,
    montoRetencionGastos,
    montoALiquidar,
    propiedades: aliasPropiedades.length,
  };
}

export async function getPropietarios(empresaId: number): Promise<string[]> {
  const supabase = await createClient();
  const { data } = await supabase.from("propiedades").select("propietario").eq("empresa_id", empresaId);
  return Array.from(new Set((data ?? []).map((p) => p.propietario))).sort();
}
