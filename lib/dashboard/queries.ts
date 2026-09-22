import { createClient } from "@/lib/supabase/server";
import type { ContratoActivoDashboardRow } from "@/lib/dashboard/types";

/**
 * Puerto de `_cached_contratos_activos()` (app.py líneas 1474-1487).
 *
 * NOTA TÉCNICA: v1 relaciona contratos↔propiedades↔inquilinos por texto
 * (`alias_propiedad`, `dni`), no por una foreign key declarada en
 * Postgres. Eso significa que no podemos usar el embed anidado de
 * PostgREST (`propiedades!inner(...)`) — necesita una FK real para saber
 * cómo armar el join. Para no tener que tocar el esquema de v1 (riesgo
 * de romper inserts si hay algún mismatch de mayúsculas/espacios en
 * datos viejos), resolvemos el join acá con 3 queries simples.
 *
 * RLS ya filtra por empresa en las tres tablas para roles normales (ver
 * auth_empresa_id() en la migración 0001) — `empresaFiltro` es solo para
 * superadmin, que bypassea esa restricción (ver lib/auth/session.ts).
 */
export async function getContratosActivosDashboard(
  propietarioFiltro?: string,
  empresaFiltro?: number | null
): Promise<ContratoActivoDashboardRow[]> {
  const supabase = await createClient();

  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario");
  if (propietarioFiltro) {
    propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  }
  if (empresaFiltro !== undefined) {
    propiedadesQuery =
      empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
  }
  const { data: propiedades, error: errProp } = await propiedadesQuery;
  if (errProp) throw new Error(`[Dashboard] Error cargando propiedades: ${errProp.message}`);

  // Si hay filtro (propietario y/o empresa) y no matchea ninguna
  // propiedad, cortamos acá: ningún contrato puede matchear.
  const hayFiltroDePropiedades = Boolean(propietarioFiltro) || empresaFiltro !== undefined;
  const aliasPermitidos = hayFiltroDePropiedades ? new Set((propiedades ?? []).map((p) => p.alias_propiedad)) : null;
  if (aliasPermitidos && aliasPermitidos.size === 0) return [];

  let contratosQuery = supabase
    .from("contratos")
    .select("codigo, alias_propiedad, dni_inquilino, fin_contrato, prox_actualizacion, alquiler, mes_contrato, act_contrato, estado")
    .eq("estado", "Activo");

  if (aliasPermitidos) {
    contratosQuery = contratosQuery.in("alias_propiedad", Array.from(aliasPermitidos));
  }

  const { data: contratos, error: errCont } = await contratosQuery;
  if (errCont) throw new Error(`[Dashboard] Error cargando contratos: ${errCont.message}`);
  if (!contratos || contratos.length === 0) return [];

  const dnis = Array.from(new Set(contratos.map((c) => c.dni_inquilino).filter(Boolean)));
  const { data: inquilinos, error: errInq } = await supabase
    .from("inquilinos")
    .select("dni, apellidos, nombres")
    .in("dni", dnis);
  if (errInq) throw new Error(`[Dashboard] Error cargando inquilinos: ${errInq.message}`);

  const inquilinoPorDni = new Map((inquilinos ?? []).map((i) => [i.dni, i]));

  return contratos.map((c) => {
    const inquilino = inquilinoPorDni.get(c.dni_inquilino);
    return {
      codigo: c.codigo,
      alias_propiedad: c.alias_propiedad,
      inquilino: `${inquilino?.apellidos ?? ""}, ${inquilino?.nombres ?? ""}`,
      estado: c.estado,
      fin_contrato: c.fin_contrato,
      prox_actualizacion: c.prox_actualizacion,
      alquiler: c.alquiler,
      mes_contrato: c.mes_contrato,
      act_contrato: c.act_contrato,
    };
  });
}

/**
 * Puerto de `_cached_pagos_totales()` (app.py líneas 1490-1496): suma
 * histórica de `monto_abonado` en `pagos_historial`, opcionalmente
 * restringida a las propiedades de un propietario.
 */
export async function getCajaHistorica(propietarioFiltro?: string, empresaFiltro?: number | null): Promise<number> {
  const supabase = await createClient();

  if (propietarioFiltro || empresaFiltro !== undefined) {
    let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad");
    if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
    if (empresaFiltro !== undefined) {
      propiedadesQuery =
        empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
    }
    const { data: propiedadesFiltradas, error: errProp } = await propiedadesQuery;

    if (errProp) throw new Error(`[Dashboard] Error resolviendo propiedades: ${errProp.message}`);

    const alias = (propiedadesFiltradas ?? []).map((p) => p.alias_propiedad);
    if (alias.length === 0) return 0;

    const { data, error } = await supabase
      .from("pagos_historial")
      .select("monto_abonado")
      .in("propiedad", alias);

    if (error) throw new Error(`[Dashboard] Error cargando caja histórica: ${error.message}`);
    return (data ?? []).reduce((acc, r) => acc + (Number(r.monto_abonado) || 0), 0);
  }

  const { data, error } = await supabase.from("pagos_historial").select("monto_abonado");
  if (error) throw new Error(`[Dashboard] Error cargando caja histórica: ${error.message}`);
  return (data ?? []).reduce((acc, r) => acc + (Number(r.monto_abonado) || 0), 0);
}
