"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";

export async function crearPropiedad(datos: {
  aliasPropiedad: string;
  calle: string;
  numero: string;
  propietario: string;
  grupo: string | null; // texto libre para gastos compartidos (ver DESIGN_LOG.md Módulo 7)
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { error } = await supabase.from("propiedades").insert({
    empresa_id: perfil.empresaId,
    alias_propiedad: datos.aliasPropiedad,
    calle: datos.calle,
    numero: datos.numero,
    propietario: datos.propietario,
    grupo: datos.grupo,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}

export async function crearInquilino(datos: {
  dni: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  email: string;
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { error } = await supabase.from("inquilinos").insert({
    empresa_id: perfil.empresaId,
    dni: datos.dni,
    nombres: datos.nombres,
    apellidos: datos.apellidos,
    telefono: datos.telefono,
    email: datos.email,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}
