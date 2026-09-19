import { createClient } from "@/lib/supabase/server";
import { enviarMensajeWhatsapp } from "@/lib/whatsapp/enviar";

/**
 * Motor de recordatorios automáticos — Módulo 8.
 *
 * Puerto CORREGIDO del bloque "Envío automático de recordatorios
 * WhatsApp" de app.py (líneas 2129-2253). El bug original comparaba
 * `dia_del_mes` contra el día calendario de hoy y mandaba a TODOS los
 * contratos activos sin mirar su fecha real — ver docs/DESIGN_LOG.md,
 * sección "Bug GRAVE confirmado". Acá cada contrato se compara contra
 * SU propia fecha (`obtener_recordatorios_pendientes()` ya hace esa
 * comparación correcta, del lado de la base).
 *
 * Pensado para ser llamado desde el Route Handler de cron
 * (app/api/cron/motor-diario/route.ts), como uno de los pasos del cron
 * diario consolidado — nunca desde una sesión de usuario normal.
 */

const TEMPLATE_VENCIMIENTO = "recordatorio_vencimiento_contrato";
const TEMPLATE_ACTUALIZACION = "recordatorio_actualizacion_alquiler";

export interface ResultadoRecordatorios {
  procesados: number;
  enviados: number;
  reservasFallidas: number; // ya estaban enviados/reservados por otra corrida
  erroresEnvio: number;
}

export async function procesarRecordatoriosAutomaticos(
  secretCron: string
): Promise<ResultadoRecordatorios> {
  const supabase = await createClient();

  const { data: pendientes, error } = await supabase.rpc("obtener_recordatorios_pendientes", {
    p_secret_cron: secretCron,
  });

  if (error) {
    throw new Error(`[Recordatorios] Error obteniendo pendientes: ${error.message}`);
  }

  const resultado: ResultadoRecordatorios = {
    procesados: 0,
    enviados: 0,
    reservasFallidas: 0,
    erroresEnvio: 0,
  };

  if (!pendientes || pendientes.length === 0) return resultado;

  // Cachear credenciales por empresa — varios contratos pueden compartir
  // la misma empresa, no hace falta pedirlas de nuevo cada vez.
  const credencialesCache = new Map<number, { phoneId: string; token: string } | null>();

  for (const rec of pendientes) {
    resultado.procesados += 1;

    // 1. Reservar ATÓMICAMENTE antes de mandar nada — evita reenvíos
    //    duplicados si el cron corriera dos veces (ver DESIGN_LOG.md,
    //    sección "Deduplicación").
    const { data: reservado, error: errorReserva } = await supabase.rpc(
      "intentar_reservar_recordatorio",
      {
        p_empresa_id: rec.empresa_id,
        p_codigo_contrato: rec.codigo_contrato,
        p_tipo: rec.tipo,
        p_secret_cron: secretCron,
      }
    );

    if (errorReserva || !reservado) {
      resultado.reservasFallidas += 1;
      continue;
    }

    // 2. Resolver credenciales de la empresa (con caché)
    if (!credencialesCache.has(rec.empresa_id)) {
      const { data: creds } = await supabase.rpc("obtener_credenciales_whatsapp_cron", {
        p_empresa_id: rec.empresa_id,
        p_secret_cron: secretCron,
      });
      const fila = Array.isArray(creds) ? creds[0] : creds;
      credencialesCache.set(
        rec.empresa_id,
        fila?.phone_id && fila?.token ? { phoneId: fila.phone_id, token: fila.token } : null
      );
    }
    const credenciales = credencialesCache.get(rec.empresa_id);

    if (!credenciales || !rec.telefono || !rec.fecha_evento) {
      resultado.erroresEnvio += 1;
      continue;
    }

    // 3. Armar y mandar el mensaje — mismos templates y variables que v1
    const fechaFormateada = formatearFechaArgentina(rec.fecha_evento);

    const enviado =
      rec.tipo === "vencimiento"
        ? await enviarMensajeWhatsapp({
            phoneId: credenciales.phoneId,
            token: credenciales.token,
            numeroDestino: rec.telefono,
            templateName: TEMPLATE_VENCIMIENTO,
            variables: [rec.nombre ?? "", rec.direccion ?? "", fechaFormateada],
          })
        : rec.tipo === "actualizacion"
        ? await enviarMensajeWhatsapp({
            phoneId: credenciales.phoneId,
            token: credenciales.token,
            numeroDestino: rec.telefono,
            templateName: TEMPLATE_ACTUALIZACION,
            variables: [rec.nombre ?? "", fechaFormateada, rec.direccion ?? "", rec.indice ?? "ICL"],
          })
        : false;

    if (enviado) {
      resultado.enviados += 1;
    } else {
      // Ya reservamos el slot en el paso 1 — si el envío falla acá, no
      // reintenta hoy (mismo criterio "no reintentos infinitos" de v1).
      // El recordatorio de mañana (si vuelve a coincidir el offset con
      // otro tipo) no se ve afectado; este contrato+tipo puntual espera
      // al próximo evento.
      resultado.erroresEnvio += 1;
    }
  }

  return resultado;
}

function formatearFechaArgentina(fechaISO: string): string {
  const [anio, mes, dia] = fechaISO.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}
