"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import type { ResumenRendicion } from "@/lib/rendicion/queries";

/**
 * Registrar Liquidación — llama a la función atómica registrar_liquidacion_propietario()
 * (migración 0009_registrar_liquidacion.sql), que arregla el bug de
 * atomicidad de v1 (ver docs/DESIGN_LOG.md).
 */
export async function registrarLiquidacion(
  resumen: ResumenRendicion,
  montoLiquidado: number
): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("rendicion");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const saldoPendienteNuevo = resumen.montoALiquidar - montoLiquidado;

  const { error } = await supabase.rpc("registrar_liquidacion_propietario", {
    p_empresa_id: perfil.empresaId,
    p_propietario: resumen.propietario,
    p_periodo: resumen.periodoMes,
    p_monto_calculado: resumen.netoARendir,
    p_saldo_anterior: resumen.saldoAnterior,
    p_monto_retencion_gastos: resumen.montoRetencionGastos,
    p_monto_a_liquidar: resumen.montoALiquidar,
    p_monto_liquidado: montoLiquidado,
    p_saldo_pendiente: saldoPendienteNuevo,
    p_ids_gastos: resumen.gastosRetencion.map((g) => g.id),
    p_registrado_por: perfil.username,
  });

  if (error) return { ok: false, error: error.message };

  revalidatePath("/rendicion");
  return { ok: true };
}
