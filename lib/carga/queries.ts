import { createClient } from "@/lib/supabase/server";
import type { IndiceActualizacion } from "@/lib/types/database.types";

export interface ContratoEditable {
  codigo: string;
  aliasPropiedad: string;
  dniInquilino: string;
  inquilino: string; // "Apellidos, Nombres" para el selector
  estado: string;
  fechaInicio: string;
  finContrato: string | null;
  calcDuracion: number | null;
  indice: IndiceActualizacion;
  frecuenciaMeses: number;
  honorariosPct: number;
  montoHonorarios: number | null;
  cuotaHonorarios: number;
  montoGarantia: number | null;
  cuotasDeposito: number;
  cargoElectricidad: "Inquilino" | "Propietario";
  cargoGas: "Inquilino" | "Propietario";
  cargoMunicipalidad: "Inquilino" | "Propietario";
  cargoOoss: "Inquilino" | "Propietario";
  cargoExpensas: "Inquilino" | "Propietario";
  cargoImpInmobiliario: "Inquilino" | "Propietario";
  cochera: number | null;
  montoInicial: number; // solo lectura acá — es histórico, no se edita después del alta
  proxActualizacion: string | null;
  updatedAt: string;
}

/**
 * Módulo "Carga de Contratos" — lista para el selector de "Editar
 * Contrato". RLS de contratos ya filtra por empresa para roles normales
 * (0001_v2_auth_setup.sql) — `empresaFiltro` es solo para superadmin, que
 * bypassea esa restricción (ver lib/auth/session.ts).
 */
export async function listarContratosEditables(
  propietarioFiltro?: string,
  empresaFiltro?: number | null
): Promise<ContratoEditable[]> {
  const supabase = await createClient();

  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  if (empresaFiltro !== undefined) {
    propiedadesQuery =
      empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
  }
  const { data: propiedades } = await propiedadesQuery;
  const aliasPermitidos = propietarioFiltro ? new Set((propiedades ?? []).map((p) => p.alias_propiedad)) : null;
  if (aliasPermitidos && aliasPermitidos.size === 0) return [];

  let contratosQuery = supabase
    .from("contratos")
    .select(
      "codigo, alias_propiedad, dni_inquilino, estado, inicio_contrato, fin_contrato, calc_duracion, indice, act_contrato, honorarios, monto_honorarios, cuota_honorarios, monto_garantia, cuotas_deposito, cargo_electricidad, cargo_gas, cargo_municipalidad, cargo_ooss, cargo_expensas, cargo_imp_inmobiliario, cochera, monto_inicial, prox_actualizacion, updated_at"
    )
    .order("alias_propiedad");
  if (aliasPermitidos) contratosQuery = contratosQuery.in("alias_propiedad", Array.from(aliasPermitidos));
  if (empresaFiltro !== undefined) {
    contratosQuery =
      empresaFiltro === null ? contratosQuery.is("empresa_id", null) : contratosQuery.eq("empresa_id", empresaFiltro);
  }

  const { data: contratos, error } = await contratosQuery;
  if (error) throw new Error(`[Carga] Error cargando contratos: ${error.message}`);
  if (!contratos || contratos.length === 0) return [];

  const dnis = Array.from(new Set(contratos.map((c) => c.dni_inquilino)));
  const { data: inquilinos } = await supabase.from("inquilinos").select("dni, nombres, apellidos").in("dni", dnis);
  const mapaInquilinos = new Map((inquilinos ?? []).map((i) => [i.dni, `${i.apellidos}, ${i.nombres}`]));

  return contratos.map((c) => ({
    codigo: c.codigo,
    aliasPropiedad: c.alias_propiedad,
    dniInquilino: c.dni_inquilino,
    inquilino: mapaInquilinos.get(c.dni_inquilino) ?? c.dni_inquilino,
    estado: c.estado,
    fechaInicio: c.inicio_contrato,
    finContrato: c.fin_contrato,
    calcDuracion: c.calc_duracion,
    indice: c.indice,
    frecuenciaMeses: c.act_contrato,
    honorariosPct: c.honorarios,
    montoHonorarios: c.monto_honorarios,
    cuotaHonorarios: c.cuota_honorarios,
    montoGarantia: c.monto_garantia,
    cuotasDeposito: c.cuotas_deposito,
    cargoElectricidad: c.cargo_electricidad,
    cargoGas: c.cargo_gas,
    cargoMunicipalidad: c.cargo_municipalidad,
    cargoOoss: c.cargo_ooss,
    cargoExpensas: c.cargo_expensas,
    cargoImpInmobiliario: c.cargo_imp_inmobiliario,
    cochera: c.cochera,
    montoInicial: c.monto_inicial,
    proxActualizacion: c.prox_actualizacion,
    updatedAt: c.updated_at,
  }));
}
