"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { calcularMotivoFinalizacion, bloqueadoPorActualizacionPendiente } from "@/lib/carga/validaciones";
import { verificarConflicto } from "@/lib/concurrencia/queries";
import { listarContratosEditables, type ContratoEditable } from "@/lib/carga/queries";
import type { IndiceActualizacion } from "@/lib/types/database.types";

export async function listarContratos(): Promise<ContratoEditable[]> {
  const perfil = await requirePermisoAction("carga");
  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  return listarContratosEditables(propietarioFiltro, empresaFiltro);
}

export interface DatosContrato {
  codigo: string;
  aliasPropiedad: string;
  dniInquilino: string;
  fechaInicio: string;
  finContrato: string;
  calcDuracion: number;
  indice: IndiceActualizacion;
  /**
   * Frecuencia de actualización del alquiler, en cantidad de meses
   * (1, 2, 3, 4, 6, 12, 24...). Va directo a `contratos.act_contrato`
   * (integer) — NO existe `frecuencia_actualizacion` en la base real.
   */
  frecuenciaMeses: number;
  montoInicial: number;
  honorariosPct: number;
  montoHonorarios: number | null; // total pactado — NULL = usar monto_inicial (ver DESIGN_LOG.md)
  cuotaHonorarios: number;
  montoGarantia: number | null;
  cuotasDeposito: number;
  honorariosPagadosBase: number;
  cuotasHonorariosPagadasBase: number;
  garantiaPagadaBase: number;
  cuotasDepositoPagadasBase: number;
  cargoElectricidad: "Inquilino" | "Propietario";
  cargoGas: "Inquilino" | "Propietario";
  cargoMunicipalidad: "Inquilino" | "Propietario";
  cargoOoss: "Inquilino" | "Propietario";
  cargoExpensas: "Inquilino" | "Propietario";
  cargoImpInmobiliario: "Inquilino" | "Propietario";
  cochera: number;
}

/**
 * Crear contrato nuevo — puerto de app.py líneas 5980-6060. Incluye la
 * regla de auto-finalizado del contrato viejo de la misma propiedad
 * (ver DESIGN_LOG.md): corre SIEMPRE (no solo si el nuevo es Activo,
 * a diferencia de v1), y calcula Finalizado vs Cancelado según si el
 * viejo cumplió su curso o se cortó antes de tiempo.
 */
export async function crearContrato(datos: DatosContrato): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("carga");
  const supabase = await createClient();

  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  // 1. Buscar contrato Activo existente en la misma propiedad
  const { data: contratoViejo } = await supabase
    .from("contratos")
    .select("codigo, fin_contrato, mes_contrato, calc_duracion")
    .eq("alias_propiedad", datos.aliasPropiedad)
    .eq("empresa_id", perfil.empresaId)
    .eq("estado", "Activo")
    .maybeSingle();

  // 2. Si existe, finalizarlo SIEMPRE (sin condición sobre el estado del nuevo)
  if (contratoViejo) {
    const motivo = calcularMotivoFinalizacion({
      finContratoViejo: contratoViejo.fin_contrato,
      mesContratoViejo: contratoViejo.mes_contrato,
      calcDuracionViejo: contratoViejo.calc_duracion,
    });

    const { error: errorFinalizar } = await supabase
      .from("contratos")
      .update({
        estado: motivo,
        // fecha_finalizacion queda NULL a propósito — solo el auto-
        // vencimiento por cron completa esa columna (ver DESIGN_LOG.md,
        // distingue "vencido de hecho" de "renovado").
        finalizado_por: "renovacion",
      })
      .eq("codigo", contratoViejo.codigo)
      .eq("empresa_id", perfil.empresaId);

    if (errorFinalizar) return { ok: false, error: `Error finalizando el contrato anterior: ${errorFinalizar.message}` };
  }

  // 3. Insertar el contrato nuevo
  const { error: errorInsert } = await supabase.from("contratos").insert({
    empresa_id: perfil.empresaId,
    codigo: datos.codigo,
    alias_propiedad: datos.aliasPropiedad,
    dni_inquilino: datos.dniInquilino,
    // La columna real en `contratos` es `inicio_contrato`, no `fecha_inicio`
    // (ver DESIGN_LOG.md — hallazgo de auditoría de esquema real vs. supuesto).
    inicio_contrato: datos.fechaInicio,
    fin_contrato: datos.finContrato,
    calc_duracion: datos.calcDuracion,
    mes_contrato: 0,
    indice: datos.indice,
    act_contrato: datos.frecuenciaMeses,
    monto_inicial: datos.montoInicial,
    honorarios: datos.honorariosPct,
    monto_honorarios: datos.montoHonorarios,
    cuota_honorarios: datos.cuotaHonorarios,
    monto_garantia: datos.montoGarantia,
    cuotas_deposito: datos.cuotasDeposito,
    honorarios_pagados_base: datos.honorariosPagadosBase,
    cuotas_honorarios_pagadas_base: datos.cuotasHonorariosPagadasBase,
    garantia_pagada_base: datos.garantiaPagadaBase,
    cuotas_deposito_pagadas_base: datos.cuotasDepositoPagadasBase,
    cargo_electricidad: datos.cargoElectricidad,
    cargo_gas: datos.cargoGas,
    cargo_municipalidad: datos.cargoMunicipalidad,
    cargo_ooss: datos.cargoOoss,
    cargo_expensas: datos.cargoExpensas,
    cargo_imp_inmobiliario: datos.cargoImpInmobiliario,
    cochera: datos.cochera,
    estado: "Activo",
  });

  if (errorInsert) return { ok: false, error: `Error al crear el contrato: ${errorInsert.message}` };

  revalidatePath("/carga");
  revalidatePath("/planilla");
  return { ok: true };
}

export interface DatosEditarContrato {
  estado: string;
  dniInquilino: string;
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
}

/**
 * Edición de un contrato existente — sin la lógica de renovación (eso
 * solo aplica a altas nuevas, ver crearContrato). NO toca `monto_inicial`
 * (histórico del alta) ni `alquiler` (vigente, lo mantiene el motor de
 * índices de Planilla — ver actualizarIndicesManual()).
 *
 * CORRECCIÓN (hallazgo de esta sesión): la versión anterior de esta
 * función pasaba `datos` (claves en camelCase, ej. `aliasPropiedad`)
 * directo a `.update()`, que espera nombres de columna reales
 * (snake_case, ej. `alias_propiedad`) — nunca hubiera actualizado nada
 * en la base real. No tenía pantalla propia todavía, así que el bug no
 * se había manifestado. Ahora mapea cada campo explícitamente, igual
 * criterio que crearContrato().
 *
 * Dos capas de protección antes de guardar: optimistic locking (Módulo
 * transversal "Ediciones simultáneas") y el bloqueo por actualización
 * de índice pendiente (ver lib/carga/validaciones.ts).
 */
export async function editarContrato(
  codigo: string,
  datos: DatosEditarContrato,
  updatedAtEsperado: string
): Promise<{ ok: boolean; error?: string; conflicto?: boolean; bloqueado?: boolean }> {
  const perfil = await requirePermisoAction("carga");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const conflicto = await verificarConflicto("contratos", codigo, updatedAtEsperado);
  if (conflicto.hayConflicto) {
    return { ok: false, conflicto: true, error: "Alguien más guardó cambios sobre este contrato mientras lo editabas. Actualizá y volvé a intentar." };
  }

  const { data: actual } = await supabase
    .from("contratos")
    .select("fin_contrato, prox_actualizacion")
    .eq("codigo", codigo)
    .eq("empresa_id", perfil.empresaId)
    .maybeSingle();

  const { bloqueado, motivo } = bloqueadoPorActualizacionPendiente({
    estado: datos.estado,
    finContrato: actual?.fin_contrato ?? null,
    proxActualizacion: actual?.prox_actualizacion ?? null,
  });
  if (bloqueado) return { ok: false, bloqueado: true, error: motivo ?? "Edición bloqueada." };

  const { error } = await supabase
    .from("contratos")
    .update({
      estado: datos.estado,
      dni_inquilino: datos.dniInquilino,
      inicio_contrato: datos.fechaInicio,
      fin_contrato: datos.finContrato,
      calc_duracion: datos.calcDuracion,
      indice: datos.indice,
      act_contrato: datos.frecuenciaMeses,
      honorarios: datos.honorariosPct,
      monto_honorarios: datos.montoHonorarios,
      cuota_honorarios: datos.cuotaHonorarios,
      monto_garantia: datos.montoGarantia,
      cuotas_deposito: datos.cuotasDeposito,
      cargo_electricidad: datos.cargoElectricidad,
      cargo_gas: datos.cargoGas,
      cargo_municipalidad: datos.cargoMunicipalidad,
      cargo_ooss: datos.cargoOoss,
      cargo_expensas: datos.cargoExpensas,
      cargo_imp_inmobiliario: datos.cargoImpInmobiliario,
      cochera: datos.cochera,
    })
    .eq("codigo", codigo)
    .eq("empresa_id", perfil.empresaId);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/carga");
  revalidatePath("/planilla");
  return { ok: true };
}
