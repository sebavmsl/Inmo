"use server";

import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { getCredencialesWhatsapp, enviarMensajeWhatsapp } from "@/lib/whatsapp/enviar";
import { tieneWhatsapp } from "@/lib/auth/permissions";
import { generarPdfComprobante } from "@/lib/pagos/pdf";

/**
 * Envío del comprobante definitivo por WhatsApp — CON el PDF adjunto
 * (a diferencia del recibo preliminar de Módulo 3, que es solo texto).
 * Plantillas ya aprobadas por Meta, confirmado por el usuario — ver
 * docs/DESIGN_LOG.md.
 */
export async function enviarComprobanteWhatsapp(nroComprobante: string): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { data: cfg } = await supabase
    .from("configuraciones_empresa")
    .select("whatsapp_habilitado")
    .eq("empresa_id", perfil.empresaId)
    .single();

  if (!tieneWhatsapp(perfil.rol, perfil.permisos, cfg?.whatsapp_habilitado ?? false)) {
    return { ok: false, error: "No tenés permiso para enviar por WhatsApp." };
  }

  const { data: pago } = await supabase
    .from("pagos_historial")
    .select("codigo_contrato, periodo, propiedad, monto_abonado, fecha, metodo_pago")
    .eq("nro_comprobante", nroComprobante)
    .single();
  if (!pago) return { ok: false, error: "Comprobante no encontrado." };

  const { data: contrato } = await supabase
    .from("contratos")
    .select("dni_inquilino")
    .eq("codigo", pago.codigo_contrato)
    .single();
  if (!contrato) return { ok: false, error: "Contrato no encontrado." };

  const { data: inquilino } = await supabase
    .from("inquilinos")
    .select("nombres, apellidos, telefono")
    .eq("dni", contrato.dni_inquilino)
    .single();
  if (!inquilino?.telefono) return { ok: false, error: "El inquilino no tiene teléfono cargado." };

  const credenciales = await getCredencialesWhatsapp(perfil.empresaId);
  if (!credenciales) return { ok: false, error: "WhatsApp no está configurado para esta empresa." };

  // Llamado directo a la función compartida — NO un fetch() interno a la
  // ruta HTTP (que rompería por no reenviar la sesión, ver
  // lib/pagos/pdf.ts para el detalle de este hallazgo).
  const pdfBuffer = await generarPdfComprobante(nroComprobante);
  if (!pdfBuffer) return { ok: false, error: "No se pudo generar el PDF del comprobante." };

  const ok = await enviarMensajeWhatsapp({
    phoneId: credenciales.phoneId,
    token: credenciales.token,
    numeroDestino: inquilino.telefono,
    templateName: "comprobante_pago_alquiler",
    variables: [
      `${inquilino.nombres} ${inquilino.apellidos}`.trim(),
      pago.periodo,
      pago.propiedad,
      String(pago.monto_abonado),
      new Date(pago.fecha).toLocaleDateString("es-AR"),
      pago.metodo_pago ?? "-",
    ],
    documentoBytes: pdfBuffer,
    documentoNombre: `${nroComprobante}.pdf`,
  });

  return ok ? { ok: true } : { ok: false, error: "Error al enviar el mensaje." };
}
