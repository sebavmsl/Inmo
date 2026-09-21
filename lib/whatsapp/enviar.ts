import { createClient } from "@/lib/supabase/server";

/**
 * Puerto de `_get_wa_credenciales()` (app.py líneas 2370-2415).
 *
 * Resuelve las credenciales de WhatsApp de una empresa: o bien sus
 * propias credenciales, o las del pool compartido del superadmin
 * (`whatsapp_numeros`). El token nunca viaja en texto plano por las
 * tablas normales — se lee desde Supabase Vault vía la función
 * `leer_token_whatsapp()`, que YA EXISTE en la base (la creó v1, se
 * reutiliza tal cual, no se toca).
 *
 * Devuelve null si WhatsApp no está habilitado para la empresa, o si
 * faltan credenciales — igual comportamiento que v1 (silencioso, no
 * tira error, el caller decide qué hacer con null).
 */
export async function getCredencialesWhatsapp(
  empresaId: number
): Promise<{ token: string; phoneId: string } | null> {
  const supabase = await createClient();

  const { data: cfg, error } = await supabase
    .from("configuraciones_empresa")
    .select(
      `
      whatsapp_habilitado,
      whatsapp_credenciales_propias,
      whatsapp_phone_id,
      whatsapp_token_secret_id,
      whatsapp_numero_id,
      whatsapp_numeros ( phone_id, token_secret_id )
    `
    )
    .eq("empresa_id", empresaId)
    .single();

  if (error || !cfg || !cfg.whatsapp_habilitado) return null;

  let secretId: string | null;
  let phoneId: string | null;

  if (cfg.whatsapp_credenciales_propias) {
    secretId = cfg.whatsapp_token_secret_id;
    phoneId = cfg.whatsapp_phone_id;
  } else {
    // TS ve whatsapp_numeros como array por el join, pero es 1:1 (FK simple)
    const pool = Array.isArray(cfg.whatsapp_numeros) ? cfg.whatsapp_numeros[0] : cfg.whatsapp_numeros;
    secretId = pool?.token_secret_id ?? null;
    phoneId = pool?.phone_id ?? null;
  }

  if (!secretId || !phoneId) return null;

  const { data: tokenRow, error: tokenError } = await supabase.rpc("leer_token_whatsapp", {
    secret_id: secretId,
  });

  if (tokenError || !tokenRow) return null;

  return { token: tokenRow as string, phoneId };
}

/**
 * Puerto de `_enviar_mensaje_whatsapp()` (app.py líneas 2418-2480).
 *
 * Envía un mensaje de plantilla (template) por la API de Meta, con
 * documento adjunto opcional (solo se usa para el comprobante de pago —
 * Módulo 4; el recibo preliminar de Módulo 3 nunca manda adjunto).
 */
export async function enviarMensajeWhatsapp(params: {
  phoneId: string;
  token: string;
  numeroDestino: string;
  templateName: string;
  variables: (string | number)[];
  documentoBytes?: Buffer;
  documentoNombre?: string;
}): Promise<boolean> {
  const { phoneId, token, numeroDestino, templateName, variables, documentoBytes, documentoNombre } =
    params;

  let mediaId: string | null = null;

  if (documentoBytes) {
    try {
      const form = new FormData();
      form.append("messaging_product", "whatsapp");
      form.append(
        "file",
        new Blob([new Uint8Array(documentoBytes)], { type: "application/pdf" }),
        documentoNombre ?? "documento.pdf"
      );

      const uploadResp = await fetch(`https://graph.facebook.com/v19.0/${phoneId}/media`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const uploadData = await uploadResp.json();
      mediaId = uploadData?.id ?? null;
    } catch (e) {
      console.warn("[WhatsApp] Error subiendo documento:", e);
    }
  }

  const components: Record<string, unknown>[] = [];
  if (mediaId) {
    components.push({
      type: "header",
      parameters: [
        { type: "document", document: { id: mediaId, filename: documentoNombre ?? "documento.pdf" } },
      ],
    });
  }
  if (variables.length > 0) {
    components.push({
      type: "body",
      parameters: variables.map((v) => ({ type: "text", text: String(v) })),
    });
  }

  try {
    const resp = await fetch(`https://graph.facebook.com/v19.0/${phoneId}/messages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to: numeroDestino,
        type: "template",
        template: {
          name: templateName,
          language: { code: "es_AR" },
          components,
        },
      }),
    });
    const data = await resp.json();
    if (resp.status === 200 && "messages" in data) {
      return true;
    }
    console.warn("[WhatsApp] Error enviando:", data);
    return false;
  } catch (e) {
    console.warn("[WhatsApp] Error de red enviando:", e);
    return false;
  }
}
