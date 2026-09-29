"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { calcularValorActualizado } from "@/lib/indices/calculo";
import { calcularAlquilerVigente } from "@/lib/indices/alquilerVigente";
import { obtenerUltimoPagoDelMesPorContrato, estaPagadoEsteMes } from "@/lib/pagos/pagoMesActual";
import { periodoActual } from "@/lib/planilla/queries";
import { enviarMensajeWhatsapp, getCredencialesWhatsapp } from "@/lib/whatsapp/enviar";
import { tieneWhatsapp } from "@/lib/auth/permissions";
import { formatMontoEntero, nombreMesAnio, fechaLimiteDia10 } from "@/lib/format";

/** Puerto del checkbox "✓ verificado" — ahora persistente (ver DESIGN_LOG.md). */
export async function toggleVerificado(codigoContrato: string, verificado: boolean) {
  const perfil = await requirePermisoAction("planilla");
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
  const perfil = await requirePermisoAction("planilla");
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
  const perfil = await requirePermisoAction("planilla");
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
  const perfil = await requirePermisoAction("planilla");
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
 *
 * CORRECCIÓN (hallazgo de esta sesión, comparando contra app.py líneas
 * 2660-2716 y 3298-3308) — la versión anterior de esta función tenía
 * tres bugs respecto de v1:
 *
 * 1. No filtraba por saldo: mandaba el preliminar a CUALQUIER contrato
 *    con ✓ verificado, incluso si ya había pagado este mes. v1 solo
 *    manda a los que figuran `pagado_mes == False`. [V2.014: acá se usaba
 *    `saldo_actual` — la cuenta corriente GLOBAL — lo que hacía que TODOS
 *    los contratos quedaran "omitidos" en cuanto se saldaban una vez.
 *    Ahora usa el mismo chequeo real de v1 ("¿hubo un pago registrado
 *    ESTE mes calendario?"), ver lib/pagos/pagoMesActual.ts].
 * 2. No sumaba la cochera al total — solo alquiler + expensas ad-hoc.
 *    v1 arma "adicional" = cochera + expensas, y el total es
 *    alquiler + adicional.
 * 3. Mandaba solo 3 variables a la plantilla de WhatsApp, cuando la
 *    plantilla real ("recibo_preliminar_alquiler") tiene 7 variables
 *    posicionales fijas: nombre, mes/año, dirección, alquiler,
 *    adicional, total y fecha límite — un mismatch de cantidad rompe
 *    el envío contra la API real de Meta (las plantillas son rígidas).
 */
export async function enviarRecibosPreliminaresMasivo() {
  const perfil = await requirePermisoAction("planilla");
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

  const nombreMes = nombreMesAnio();
  const fechaLimite = fechaLimiteDia10();

  // V2.014 — mismo fix que lib/planilla/queries.ts: "ya pagó este mes" se
  // decide con un pago real cargado en pagos_historial este mes calendario,
  // no con saldo_actual (cuenta corriente global). Ver lib/pagos/pagoMesActual.ts.
  const pagosDelMes = await obtenerUltimoPagoDelMesPorContrato((verificados ?? []).map((v) => v.codigo_contrato));

  let enviados = 0;
  let errores = 0;
  let omitidos = 0; // ya pagaron este mes, o sin teléfono registrado

  for (const v of verificados ?? []) {
    const { data: contrato } = await supabase
      .from("contratos")
      .select("codigo, alias_propiedad, dni_inquilino, alquiler_calculado, alquiler_calculado_fecha, alquiler, monto_inicial, cochera")
      .eq("codigo", v.codigo_contrato)
      .eq("empresa_id", perfil.empresaId)
      .single();
    if (!contrato) {
      errores += 1;
      continue;
    }

    // Bug #1 corregido (V2.014): si ya pagó este mes calendario, no se
    // manda el preliminar aunque haya quedado ✓ verificado de una revisión
    // previa.
    if (estaPagadoEsteMes(pagosDelMes.get(contrato.codigo))) {
      omitidos += 1;
      continue;
    }

    const { data: propiedad } = await supabase
      .from("propiedades")
      .select("calle, numero")
      .eq("alias_propiedad", contrato.alias_propiedad)
      .eq("empresa_id", perfil.empresaId)
      .maybeSingle();

    const { data: inquilino } = await supabase
      .from("inquilinos")
      .select("nombres, apellidos, telefono")
      .eq("dni", contrato.dni_inquilino)
      .single();
    if (!inquilino?.telefono) {
      omitidos += 1;
      continue;
    }

    // V2.013: antes usaba contrato.alquiler_calculado sin chequear si
    // era del mes actual — podía mandarle al inquilino un monto
    // inflado por WhatsApp. Ver lib/indices/alquilerVigente.ts.
    const alquiler = calcularAlquilerVigente(
      contrato.alquiler_calculado,
      contrato.alquiler_calculado_fecha,
      contrato.alquiler,
      contrato.monto_inicial
    );
    // Bug #2 corregido: el adicional suma cochera + expensas ad-hoc.
    const adicional = (contrato.cochera ?? 0) + (v.expensas_adhoc ?? 0);
    const total = alquiler + adicional;
    const direccion = `${propiedad?.calle ?? ""} ${propiedad?.numero ?? ""}`.trim();

    // Bug #3 corregido: exactamente 7 variables, mismo orden que v1.
    const ok = await enviarMensajeWhatsapp({
      phoneId: credenciales.phoneId,
      token: credenciales.token,
      numeroDestino: inquilino.telefono,
      templateName: "recibo_preliminar_alquiler",
      variables: [
        `${inquilino.nombres} ${inquilino.apellidos}`.trim(),
        nombreMes,
        direccion,
        formatMontoEntero(alquiler),
        formatMontoEntero(adicional),
        formatMontoEntero(total),
        fechaLimite,
      ],
    });
    if (ok) enviados += 1;
    else errores += 1;
  }

  return { enviados, errores, omitidos };
}
