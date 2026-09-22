"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { registrarCotizacionUsada } from "@/lib/cotizacion/queries";
import type { TipoPago } from "@/lib/types/database.types";

export interface ConceptosPago {
  alquiler: number;
  expensas: number;
  edesal: number;
  gas: number;
  municipalidad: number;
  cochera: number;
  ooss: number;
  impInmobiliario: number;
  honorarios: number;
  garantia: number;
  conceptoExtra: number;
}

export interface ImpactarCobroParams {
  codigoContrato: string;
  tipoPago: TipoPago;
  periodo: string; // "Mes N de M" — ver DESIGN_LOG.md sobre por qué no es un mes calendario
  conceptos: ConceptosPago | null; // null para Complemento/Corrección
  diferenciaCorreccion: number | null;
  montoAbonado: number;
  metodoPago: string;
  comentario: string;
  cotizacionUsd: number | null;
}

export interface ResultadoImpactarCobro {
  ok: boolean;
  nroComprobante?: string;
  saldoNuevo?: number;
  error?: string;
}

/**
 * "Impactar Cobro" — Server Action delgado: toda la lógica que necesita
 * el candado de concurrencia vive en la función SQL `impactar_cobro()`
 * (migración 0006_pagos_extras.sql). Ver ahí el comentario de por qué
 * NO se puede armar esto como una secuencia de llamadas separadas desde
 * el cliente (pg_advisory_xact_lock no sobrevive entre llamadas de
 * Supabase-js — hallazgo de esta sesión).
 */
export async function impactarCobro(params: ImpactarCobroParams): Promise<ResultadoImpactarCobro> {
  const perfil = await requirePermisoAction("pagos");
  const supabase = await createClient();

  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const c = params.conceptos;

  const { data, error } = await supabase.rpc("impactar_cobro", {
    p_codigo_contrato: params.codigoContrato,
    p_empresa_id: perfil.empresaId,
    p_tipo_pago: params.tipoPago,
    p_periodo: params.periodo,
    p_monto_alquiler: c?.alquiler ?? 0,
    p_monto_expensas: c?.expensas ?? 0,
    p_monto_edesal: c?.edesal ?? 0,
    p_monto_gas: c?.gas ?? 0,
    p_monto_municipalidad: c?.municipalidad ?? 0,
    p_monto_cochera: c?.cochera ?? 0,
    p_monto_ooss: c?.ooss ?? 0,
    p_monto_imp_inmobiliario: c?.impInmobiliario ?? 0,
    p_monto_honorarios: c?.honorarios ?? 0,
    p_monto_garantia: c?.garantia ?? 0,
    p_monto_concepto_extra: c?.conceptoExtra ?? 0,
    p_diferencia_correccion: params.diferenciaCorreccion,
    p_monto_abonado: params.montoAbonado,
    p_metodo_pago: params.metodoPago,
    p_comentario: params.comentario || null,
    p_cotizacion_usd: params.cotizacionUsd,
    p_registrado_por: perfil.username,
  });

  if (error) return { ok: false, error: error.message };

  const fila = Array.isArray(data) ? data[0] : data;
  if (!fila?.ok) return { ok: false, error: fila?.mensaje_error ?? "Error desconocido." };

  revalidatePath("/pagos");
  revalidatePath("/planilla");

  // Best-effort, no bloquea la respuesta si falla (ver doc-comment de
  // registrarCotizacionUsada) — el cobro ya se guardó.
  await registrarCotizacionUsada(perfil.empresaId, params.cotizacionUsd);

  return { ok: true, nroComprobante: fila.nro_comprobante, saldoNuevo: fila.saldo_nuevo };
}
