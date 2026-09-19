"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { calcularValorActualizado } from "@/lib/indices/calculo";
import { periodoActual } from "@/lib/planilla/queries";
import { enviarMensajeWhatsapp, getCredencialesWhatsapp } from "@/lib/whatsapp/enviar";
import { tieneWhatsapp } from "@/lib/auth/permissions";
import { formatMoneda } from "@/lib/format";

/** Puerto del checkbox "✓ verificado" — ahora persistente (ver DESIGN_LOG.md). */
export async function toggleVerificado(codigoContrato: string, verificado: boolean) {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const { error } = await supabase.from("planilla_verificaciones").upsert(
    {
      empresa_id: perfil.empresaId,
      codigo_contrato: codigoContrato,
      periodo: periodoActual(),
      verificado,
      verificado_por: perfil.username,
      verificado_fecha: new Date().toISOString(),
    },
    { onConflict: "codigo_contrato,periodo" }
  );

  if (error) throw new Error(`Error al guardar verificación: ${error.message}`);
  revalidatePath("/planilla");
}

/** Edición ad-hoc de expensas para el WhatsApp de este mes, sin tocar el contrato. */
export async function actualizarExpensasAdhoc(codigoContrato: string, monto: number | null) {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const { error } = await supabase.from("planilla_verificaciones").upsert(
    {
      empresa_id: perfil.empresaId,
      codigo_contrato: codigoContrato,
      periodo: periodoActual(),
      expensas_adhoc: monto,
    },
    { onConflict: "codigo_contrato,periodo" }
  );

  if (error) throw new Error(`Error al guardar expensas: ${error.message}`);
  revalidatePath("/planilla");
}

/** Botón "🗄️ Archivar" — solo para filas vencidas-de-hecho (ver DESIGN_LOG.md, Módulo 3). */
export async function archivarContrato(codigoContrato: string) {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const { error } = await supabase
    .from("contratos")
    .update({ archivado: true })
    .eq("codigo", codigoContrato)
    .eq("empresa_id", perfil.empresaId)
    .eq("finalizado_por", "auto_vencimiento");

  if (error) throw new Error(`Error al archivar: ${error.message}`);
  revalidatePath("/planilla");
}

/**
 * Botón manual "🔄 Actualizar índices" — respaldo real ante fallo del
 * cron, refresca en vivo (no asume que el cron ya corrió). Sin candado
 * por defecto; `soloPendientes` es el checkbox opcional (destildado por
 * defecto, mismo comportamiento que v1).
 */
export async function actualizarIndicesManual(soloPendientes: boolean) {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const { data: elegibles, error: errElegibles } = await supabase.rpc(
    "contratos_elegibles_actualizacion",
    { p_empresa_id: perfil.empresaId, p_solo_pendientes: soloPendientes }
  );
  if (errElegibles) throw new Error(`Error buscando contratos elegibles: ${errElegibles.message}`);

  let actualizados = 0;
  let sinResultado = 0;

  for (const c of elegibles ?? []) {
    try {
      const valor = await calcularValorActualizado(
        c.indice as "ICL" | "IPC" | "UVA",
        c.monto_inicial,
        new Date(c.fecha_inicio),
        c.frecuencia_meses
      );
      if (valor === null) {
        sinResultado += 1;
        continue;
      }
      const { data: ok } = await supabase.rpc("aplicar_actualizacion_individual", {
        p_codigo_contrato: c.codigo,
        p_valor_calculado: valor,
        p_empresa_id: perfil.empresaId,
      });
      if (ok) actualizados += 1;
    } catch {
      sinResultado += 1;
    }
  }

  revalidatePath("/planilla");
  return { actualizados, sinResultado, total: elegibles?.length ?? 0 };
}

/**
 * Envío masivo de "recibo preliminar" — a los contratos marcados ✓
 * verificado. Solo texto, sin PDF adjunto (ver DESIGN_LOG.md, Módulo 8 —
 * tabla de diferencia entre recibo preliminar y comprobante definitivo).
 */
export async function enviarRecibosPreliminaresMasivo() {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  if (!perfil.empresaId) throw new Error("Usuario sin empresa asociada.");

  const { data: cfg } = await supabase
    .from("configuraciones_empresa")
    .select("whatsapp_habilitado")
    .eq("empresa_id", perfil.empresaId)
    .single();

  if (!tieneWhatsapp(perfil.rol, perfil.permisos, cfg?.whatsapp_habilitado ?? false)) {
    // El caller de la UI ya debería haber ocultado el botón si no
    // corresponde; esto es el resguardo del lado del servidor.
    throw new Error("No tenés permiso para enviar por WhatsApp.");
  }

  const credenciales = await getCredencialesWhatsapp(perfil.empresaId);
  if (!credenciales) throw new Error("WhatsApp no está configurado para esta empresa.");

  const periodo = periodoActual();
  const { data: verificados, error } = await supabase
    .from("planilla_verificaciones")
    .select("codigo_contrato, expensas_adhoc")
    .eq("periodo", periodo)
    .eq("verificado", true);
  if (error) throw new Error(error.message);

  let enviados = 0;
  let errores = 0;

  for (const v of verificados ?? []) {
    const { data: contrato } = await supabase
      .from("contratos")
      .select("codigo, alias_propiedad, dni_inquilino, alquiler_calculado, alquiler, monto_inicial")
      .eq("codigo", v.codigo_contrato)
      .eq("empresa_id", perfil.empresaId)
      .single();
    if (!contrato) {
      errores += 1;
      continue;
    }
    const { data: inquilino } = await supabase
      .from("inquilinos")
      .select("nombres, apellidos, telefono")
      .eq("dni", contrato.dni_inquilino)
      .single();
    if (!inquilino?.telefono) {
      errores += 1;
      continue;
    }

    const alquiler = contrato.alquiler_calculado ?? contrato.alquiler ?? contrato.monto_inicial ?? 0;
    const total = alquiler + (v.expensas_adhoc ?? 0);

    const ok = await enviarMensajeWhatsapp({
      phoneId: credenciales.phoneId,
      token: credenciales.token,
      numeroDestino: inquilino.telefono,
      templateName: "recibo_preliminar_alquiler",
      variables: [
        `${inquilino.nombres} ${inquilino.apellidos}`.trim(),
        contrato.alias_propiedad,
        formatMoneda(total),
      ],
    });
    if (ok) enviados += 1;
    else errores += 1;
  }

  return { enviados, errores };
}
