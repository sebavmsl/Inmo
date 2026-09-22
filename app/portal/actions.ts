"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { getInquilinoContratos } from "@/lib/inquilino/session";

/**
 * Subir comprobante — NO carga un pago real en pagos_historial
 * automáticamente (ver docs/DESIGN_LOG.md, Módulo 9). Queda pendiente
 * de revisión para que el staff lo registre por el flujo normal.
 */
export async function subirComprobante(
  codigoContrato: string,
  montoDeclarado: number,
  archivo: File
): Promise<{ ok: boolean; error?: string }> {
  const contratos = await getInquilinoContratos();
  const contrato = contratos.find((c) => c.codigoContrato === codigoContrato);
  if (!contrato) return { ok: false, error: "No tenés acceso a ese contrato." };

  const supabase = await createClient();
  const path = `${contrato.empresaId}/${codigoContrato}/${Date.now()}-${archivo.name}`;

  const { error: errorUpload } = await supabase.storage.from("comprobantes-inquilino").upload(path, archivo);
  if (errorUpload) return { ok: false, error: errorUpload.message };

  const { error } = await supabase.from("comprobantes_inquilino").insert({
    empresa_id: contrato.empresaId,
    codigo_contrato: codigoContrato,
    storage_path: path,
    monto_declarado: montoDeclarado,
    estado: "pendiente",
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/portal/subir-comprobante");
  return { ok: true };
}

export async function crearReclamo(codigoContrato: string, descripcion: string): Promise<{ ok: boolean; error?: string }> {
  const contratos = await getInquilinoContratos();
  const contrato = contratos.find((c) => c.codigoContrato === codigoContrato);
  if (!contrato) return { ok: false, error: "No tenés acceso a ese contrato." };

  const supabase = await createClient();
  const { error } = await supabase.from("reclamos_inquilino").insert({
    empresa_id: contrato.empresaId,
    codigo_contrato: codigoContrato,
    descripcion,
    estado: "abierto",
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/portal/reclamos");
  return { ok: true };
}
