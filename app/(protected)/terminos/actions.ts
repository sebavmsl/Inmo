"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";

/**
 * Puerto del botón "Continuar →" de app.py (líneas ~1257-1270): marca
 * `terminos_aceptados = TRUE` y `terminos_fecha = now()` para el usuario
 * actual, protegido por RLS (solo puede tocar su propia fila).
 */
export async function aceptarTerminos() {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const { error } = await supabase
    .from("usuarios_central")
    .update({
      terminos_aceptados: true,
      terminos_fecha: new Date().toISOString(),
    })
    .eq("username", perfil.username);

  if (error) {
    throw new Error(`Error al guardar la aceptación: ${error.message}`);
  }

  redirect("/dashboard");
}
