import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Rol } from "@/lib/types/database.types";

export interface SessionProfile {
  authUserId: string;
  email: string | null;
  username: string;
  nombreEmpresa: string;
  empresaId: number | null;
  rol: Rol;
  propietarioFiltro: string | null;
  terminosAceptados: boolean;
  permisos: string[];
}

/**
 * Equivalente a la sección "INICIALIZACIÓN DE SESIÓN" de app.py, pero para
 * el mundo Server Component: en vez de `st.session_state`, la sesión vive en
 * las cookies de Supabase Auth y el perfil se lee de `usuarios_central` en
 * cada request (Next.js cachea la request dentro del mismo render, así que
 * no repite la query en Server Components anidados).
 *
 * Uso en una Server Page:
 *   const perfil = await requireSessionProfile();
 */
export async function getSessionProfile(): Promise<SessionProfile | null> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const { data: perfil, error } = await supabase
    .from("usuarios_central")
    .select(
      "username, email, nombre_empresa, empresa_id, rol, propietario_filtro, terminos_aceptados"
    )
    .eq("auth_user_id", user.id)
    .single();

  if (error || !perfil) return null;

  let permisos: string[] = [];
  if (perfil.rol === "user" || perfil.rol === "admin") {
    const { data: filas } = await supabase
      .from("permisos_usuario")
      .select("pestana")
      .eq("username", perfil.username);
    permisos = (filas ?? []).map((f) => f.pestana);
  }

  return {
    authUserId: user.id,
    email: user.email ?? perfil.email,
    username: perfil.username,
    nombreEmpresa: perfil.nombre_empresa,
    empresaId: perfil.empresa_id,
    rol: perfil.rol,
    propietarioFiltro: perfil.propietario_filtro,
    terminosAceptados: perfil.terminos_aceptados,
    permisos,
  };
}

/** Para Server Pages protegidas: redirige a /login si no hay sesión válida. */
export async function requireSessionProfile(): Promise<SessionProfile> {
  const perfil = await getSessionProfile();
  if (!perfil) redirect("/login");
  return perfil;
}
