"use server";

import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { tieneCotizacionManual } from "@/lib/auth/permissions";
import { fetchCotizacionBna } from "@/lib/cotizacion/bna";

export interface ResultadoCotizacion {
  valor: number;
  fuente: "bna" | "ultimo_conocido" | "sin_dato";
  fecha: string | null;
  /** ¿Este usuario puede pisar el valor a mano? (permiso "cotizacion_manual", ver lib/auth/permissions.ts). */
  puedeEditar: boolean;
}

/**
 * Cotización del dólar para precargar en los formularios de Pagos y
 * Gastos (Módulo 4, ver docs/DESIGN_LOG.md). Se llama tanto al abrir el
 * formulario como al apretar "Actualizar BNA" — siempre intenta BNA
 * primero; si falla o devuelve 0, cae al último valor REALMENTE USADO
 * en un pago/gasto de esta empresa (nunca precarga 0, salvo que la
 * empresa no tenga ni un solo antecedente todavía — caso de borde de
 * una empresa recién creada).
 */
export async function obtenerCotizacionUsd(): Promise<ResultadoCotizacion> {
  const perfil = await requireSessionProfile();
  const puedeEditar = tieneCotizacionManual(perfil.rol, perfil.permisos);

  const valorBna = await fetchCotizacionBna();
  if (valorBna) {
    if (perfil.empresaId) await guardarUltimaCotizacion(perfil.empresaId, valorBna);
    return { valor: valorBna, fuente: "bna", fecha: new Date().toISOString(), puedeEditar };
  }

  if (perfil.empresaId) {
    const supabase = await createClient();
    const { data } = await supabase
      .from("configuraciones_empresa")
      .select("ultima_cotizacion_usd, ultima_cotizacion_fecha")
      .eq("empresa_id", perfil.empresaId)
      .maybeSingle();
    if (data?.ultima_cotizacion_usd) {
      return {
        valor: data.ultima_cotizacion_usd,
        fuente: "ultimo_conocido",
        fecha: data.ultima_cotizacion_fecha,
        puedeEditar,
      };
    }
  }

  return { valor: 0, fuente: "sin_dato", fecha: null, puedeEditar };
}

async function guardarUltimaCotizacion(empresaId: number, valor: number): Promise<void> {
  const supabase = await createClient();
  await supabase
    .from("configuraciones_empresa")
    .update({ ultima_cotizacion_usd: valor, ultima_cotizacion_fecha: new Date().toISOString() })
    .eq("empresa_id", empresaId);
}

/**
 * Cuando se guarda un pago/gasto con una cotización cargada A MANO (o
 * traída de BNA en el momento), ese valor pasa a ser el nuevo "último
 * conocido" para la próxima vez que BNA no responda. Llamar desde
 * impactarCobro()/crearGasto() después de un insert exitoso, con el
 * valor efectivamente guardado en la fila — best-effort, un fallo acá
 * nunca debe hacer fallar el pago/gasto que ya se guardó.
 */
export async function registrarCotizacionUsada(empresaId: number, valor: number | null): Promise<void> {
  if (!valor || !Number.isFinite(valor) || valor <= 0) return;
  try {
    await guardarUltimaCotizacion(empresaId, valor);
  } catch {
    // best-effort, ver doc-comment de arriba.
  }
}
