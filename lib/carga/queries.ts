import { createClient } from "@/lib/supabase/server";
import type { IndiceActualizacion } from "@/lib/types/database.types";
import type { DatosAltaContrato, OpcionesAlta, ServiciosContrato } from "@/lib/carga/tipos";
import { TIPOS_GARANTIA, aISO, leerFechaISO, sumarDias, sumarMeses, type Cargo, type TipoGarantia } from "@/lib/carga/calculoContrato";
import { calcularAlquilerVigente } from "@/lib/indices/alquilerVigente";
import { ahoraEnArgentina } from "@/lib/fechas";

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
  montoInicial: number; // dato original del alta: se puede corregir con aviso (Entrega 2)
  proxActualizacion: string | null;
  updatedAt: string;
  // Entrega 2 (0023)
  diaVencimiento: number;
  tipoGarantia: string;
  montoPagare: number;
  servicios: ServiciosContrato;
  cargoGeneralServicios: number;
  cocheraMontoInicial: number;
  cocheraActualizaConIndice: boolean;
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
      "codigo, alias_propiedad, dni_inquilino, estado, inicio_contrato, fin_contrato, calc_duracion, indice, act_contrato, honorarios, monto_honorarios, cuota_honorarios, monto_garantia, cuotas_deposito, cargo_electricidad, cargo_gas, cargo_municipalidad, cargo_ooss, cargo_expensas, cargo_imp_inmobiliario, cochera, monto_inicial, prox_actualizacion, updated_at, dia_vencimiento, tipo_de_garantie, monto_pagare, expensas, edesal, gas, municipalidad, ooss, imp_inmobiliario, cargo_general_servicios, cochera_monto_inicial, cochera_actualiza_con_indice"
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
    diaVencimiento: c.dia_vencimiento ?? 10,
    tipoGarantia: c.tipo_de_garantie ?? "Sin Garantía",
    montoPagare: Number(c.monto_pagare ?? 0),
    servicios: {
      expensas: c.expensas ?? 0,
      edesal: c.edesal ?? 0,
      gas: c.gas ?? 0,
      municipalidad: c.municipalidad ?? 0,
      ooss: c.ooss ?? 0,
      impInmobiliario: c.imp_inmobiliario ?? 0,
    },
    cargoGeneralServicios: Number(c.cargo_general_servicios ?? 0),
    cocheraMontoInicial: Number(c.cochera_monto_inicial ?? c.cochera ?? 0),
    cocheraActualizaConIndice: !!c.cochera_actualiza_con_indice,
  }));
}

/**
 * Listas para el alta (Entrega 2): propiedades e inquilinos de la empresa,
 * y qué propiedades ya tienen un contrato activo (se cierra al guardar).
 */
export async function listarOpcionesAlta(empresaId: number): Promise<OpcionesAlta> {
  const supabase = await createClient();
  const [{ data: propiedades, error: e1 }, { data: inquilinos, error: e2 }, { data: activos }] = await Promise.all([
    supabase
      .from("propiedades")
      .select("alias_propiedad, calle, numero, departamento, propietario")
      .eq("empresa_id", empresaId)
      .order("alias_propiedad"),
    supabase.from("inquilinos").select("dni, nombres, apellidos").eq("empresa_id", empresaId).order("apellidos"),
    supabase.from("contratos").select("codigo, alias_propiedad").eq("empresa_id", empresaId).eq("estado", "Activo"),
  ]);
  if (e1) throw new Error(`[Carga] Error cargando propiedades: ${e1.message}`);
  if (e2) throw new Error(`[Carga] Error cargando inquilinos: ${e2.message}`);

  const activoPorAlias = new Map((activos ?? []).map((c) => [c.alias_propiedad, String(c.codigo)]));
  return {
    propiedades: (propiedades ?? []).map((p) => ({
      alias: p.alias_propiedad,
      direccion: [`${p.calle ?? ""} ${p.numero ?? ""}`.trim(), p.departamento].filter(Boolean).join(" — "),
      propietario: p.propietario ?? "",
      contratoActivo: activoPorAlias.get(p.alias_propiedad) ?? null,
    })),
    inquilinos: (inquilinos ?? [])
      .filter((i) => i.dni)
      .map((i) => ({ dni: i.dni as string, nombre: `${i.apellidos}, ${i.nombres}` })),
  };
}

function cargoValido(v: string | null | undefined, porDefecto: Cargo): Cargo {
  return v === "Inquilino" || v === "Propietario" ? v : porDefecto;
}

/**
 * Datos precargados para renovar un contrato con el mismo inquilino:
 * mismas condiciones, fechas nuevas a continuación del anterior y monto
 * inicial = alquiler vigente del anterior. Honorarios y depósito arrancan
 * de nuevo (los cobrados del contrato anterior no se arrastran).
 */
export async function obtenerDatosRenovacion(codigo: string, empresaId: number): Promise<DatosAltaContrato | null> {
  const supabase = await createClient();
  const { data: c } = await supabase
    .from("contratos")
    .select(
      "codigo, alias_propiedad, dni_inquilino, inicio_contrato, fin_contrato, calc_duracion, act_contrato, indice, monto_inicial, alquiler, alquiler_calculado, alquiler_calculado_fecha, honorarios, cuota_honorarios, tipo_de_garantie, cuotas_deposito, monto_pagare, expensas, edesal, gas, municipalidad, ooss, imp_inmobiliario, cochera, cochera_actualiza_con_indice, cargo_general_servicios, dia_vencimiento, cargo_electricidad, cargo_gas, cargo_municipalidad, cargo_ooss, cargo_expensas, cargo_imp_inmobiliario"
    )
    .eq("codigo", codigo)
    .eq("empresa_id", empresaId)
    .maybeSingle();
  if (!c) return null;

  const finViejo = leerFechaISO(c.fin_contrato);
  const hoy = ahoraEnArgentina();
  const inicio = finViejo ? sumarDias(finViejo, 1) : { anio: hoy.anio, mes: hoy.mes, dia: 1 };
  const duracion = c.calc_duracion && c.calc_duracion > 0 ? c.calc_duracion : 24;
  const fin = sumarDias(sumarMeses(inicio, duracion), -1);
  const montoInicial = calcularAlquilerVigente(c.alquiler_calculado, c.alquiler_calculado_fecha, c.alquiler, c.monto_inicial);
  const tipo = (TIPOS_GARANTIA as readonly string[]).includes(c.tipo_de_garantie ?? "")
    ? (c.tipo_de_garantie as TipoGarantia)
    : "Sin Garantía";
  const indice = (["ICL", "IPC", "UVA", "Otro"] as string[]).includes(c.indice) ? c.indice : "Otro";

  return {
    aliasPropiedad: c.alias_propiedad,
    dniInquilino: c.dni_inquilino,
    estado: "Activo",
    fechaInicio: aISO(inicio),
    finContrato: aISO(fin),
    diaVencimiento: c.dia_vencimiento ?? 10,
    montoInicial,
    indice,
    frecuenciaMeses: c.act_contrato ?? 6,
    honorariosPct: Number(c.honorarios ?? 0),
    montoHonorarios: montoInicial,
    cuotaHonorarios: Math.max(1, c.cuota_honorarios ?? 1),
    tipoGarantia: tipo,
    montoGarantia: 0,
    cuotasDeposito: Math.max(1, c.cuotas_deposito ?? 1),
    montoPagare: Number(c.monto_pagare ?? 0),
    servicios: {
      expensas: c.expensas ?? 0,
      edesal: c.edesal ?? 0,
      gas: c.gas ?? 0,
      municipalidad: c.municipalidad ?? 0,
      ooss: c.ooss ?? 0,
      impInmobiliario: c.imp_inmobiliario ?? 0,
    },
    cargos: {
      electricidad: cargoValido(c.cargo_electricidad, "Inquilino"),
      gas: cargoValido(c.cargo_gas, "Inquilino"),
      municipalidad: cargoValido(c.cargo_municipalidad, "Inquilino"),
      ooss: cargoValido(c.cargo_ooss, "Inquilino"),
      expensas: cargoValido(c.cargo_expensas, "Inquilino"),
      impInmobiliario: cargoValido(c.cargo_imp_inmobiliario, "Propietario"),
    },
    cargoGeneralServicios: Number(c.cargo_general_servicios ?? 0),
    cochera: c.cochera ?? 0,
    cocheraActualizaConIndice: !!c.cochera_actualiza_con_indice,
    alquilerVigente: null,
    codigoAnterior: String(c.codigo),
  };
}
