"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";

export interface DatosGasto {
  propiedadId: number | null; // null si es compartido (usa grupo en su lugar)
  grupo: string | null; // si tiene valor, se reparte entre todas las propiedades de ese grupo
  fecha: string;
  categoria: string;
  descripcion: string;
  monto: number;
  proveedor: string;
  comprobante: string;
  pagadoPor: "Inmobiliaria" | "Propietario" | "Inquilino" | "Otro";
  observaciones: string;
  tipoGasto: string;
  cotizacionUsd: number | null;
}

/**
 * Puerto de la carga de gastos (app.py líneas 7833-7862). Individual, o
 * repartido en partes iguales entre las propiedades de un grupo/edificio
 * (`propiedades.grupo`, texto libre) — sin hallazgos de lógica de
 * negocio, se porta directo (ver DESIGN_LOG.md, Módulo 7).
 */
export async function crearGasto(datos: DatosGasto): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  if (datos.grupo) {
    const { data: propiedadesGrupo, error: errGrupo } = await supabase
      .from("propiedades")
      .select("id")
      .eq("empresa_id", perfil.empresaId)
      .eq("grupo", datos.grupo);

    if (errGrupo || !propiedadesGrupo || propiedadesGrupo.length === 0) {
      return { ok: false, error: "No se encontraron propiedades en ese grupo." };
    }

    const montoUnitario = Math.round((datos.monto / propiedadesGrupo.length) * 100) / 100;
    const descripcionCompartida = `${datos.descripcion.trim()} | EDIFICIO-PROPORCIONAL`;

    const filas = propiedadesGrupo.map((p) => ({
      empresa_id: perfil.empresaId,
      propiedad_id: p.id,
      fecha: datos.fecha,
      categoria: datos.categoria,
      descripcion: descripcionCompartida,
      monto: montoUnitario,
      proveedor: datos.proveedor || null,
      comprobante: datos.comprobante || null,
      pagado_por: datos.pagadoPor,
      observaciones: datos.observaciones || null,
      tipo_gasto: datos.tipoGasto,
      cotizacion_usd: datos.cotizacionUsd,
      cobrado: false,
    }));

    const { error } = await supabase.from("gastos_propiedades").insert(filas);
    if (error) return { ok: false, error: error.message };
  } else {
    if (!datos.propiedadId) return { ok: false, error: "Falta seleccionar la propiedad." };

    const { error } = await supabase.from("gastos_propiedades").insert({
      empresa_id: perfil.empresaId,
      propiedad_id: datos.propiedadId,
      fecha: datos.fecha,
      categoria: datos.categoria,
      descripcion: datos.descripcion,
      monto: datos.monto,
      proveedor: datos.proveedor || null,
      comprobante: datos.comprobante || null,
      pagado_por: datos.pagadoPor,
      observaciones: datos.observaciones || null,
      tipo_gasto: datos.tipoGasto,
      cotizacion_usd: datos.cotizacionUsd,
      cobrado: false,
    });
    if (error) return { ok: false, error: error.message };
  }

  revalidatePath("/gastos");
  return { ok: true };
}
