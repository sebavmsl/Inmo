"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { calcularMotivoFinalizacion } from "@/lib/carga/validaciones";
import type { IndiceActualizacion, FrecuenciaActualizacion } from "@/lib/types/database.types";

export interface DatosContrato {
  codigo: string;
  aliasPropiedad: string;
  dniInquilino: string;
  fechaInicio: string;
  finContrato: string;
  calcDuracion: number;
  indice: IndiceActualizacion;
  frecuenciaActualizacion: FrecuenciaActualizacion;
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
  const perfil = await requireSessionProfile();
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
    fecha_inicio: datos.fechaInicio,
    fin_contrato: datos.finContrato,
    calc_duracion: datos.calcDuracion,
    mes_contrato: 0,
    indice: datos.indice,
    frecuencia_actualizacion: datos.frecuenciaActualizacion,
    monto_inicial: datos.montoInicial,
    honorarios_pct: datos.honorariosPct,
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

/** Edición de un contrato existente — sin la lógica de renovación (eso solo aplica a altas nuevas). */
export async function editarContrato(codigo: string, datos: Partial<DatosContrato>): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { error } = await supabase
    .from("contratos")
    .update(datos)
    .eq("codigo", codigo)
    .eq("empresa_id", perfil.empresaId);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/carga");
  return { ok: true };
}
