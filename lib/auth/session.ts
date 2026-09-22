import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import { puedeAcceder } from "@/lib/auth/permissions";
import { EMPRESA_ACTIVA_COOKIE } from "@/lib/auth/empresaActivaCookie";
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
  /**
   * Minutos de inactividad antes del cierre automático de sesión (ver
   * InactivityGuard.tsx). Configurable por empresa
   * (configuraciones_empresa.timeout_inactividad_minutos); si superadmin
   * no tiene empresa activa elegida, usa el default parejo (30 min).
   */
  timeoutInactividadMinutos: number;
  /**
   * Solo relevante para superadmin: true si `empresaId`/`nombreEmpresa`
   * vienen de la empresa que eligió en el selector global (ver
   * SelectorEmpresaActiva.tsx), no de su propia fila. Para los demás
   * roles siempre false (ya vienen scopeados a la suya).
   */
  empresaActivaElegida: boolean;
}

const TIMEOUT_INACTIVIDAD_DEFAULT_MINUTOS = 30;

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

  // superadmin no tiene empresa_id propio: opera "como" la empresa que
  // eligió en el selector global (SelectorEmpresaActiva.tsx, guardado en
  // la cookie EMPRESA_ACTIVA_COOKIE, seteada por
  // app/(protected)/actions.ts::seleccionarEmpresaActiva). Por defecto
  // (sin cookie, o empresa borrada/inválida) trabaja con el grupo "sin
  // empresa asignada" (empresa_id IS NULL) — mismo criterio en TODOS los
  // módulos, no solo lectura: las Server Actions de alta/edición usan
  // este mismo `empresaId` para saber en qué empresa escribir, así que
  // este es el ÚNICO lugar donde hace falta resolver esto.
  let empresaId = perfil.empresa_id;
  let nombreEmpresa = perfil.nombre_empresa;
  let empresaActivaElegida = false;
  if (perfil.rol === "superadmin") {
    const cookieStore = await cookies();
    const valorCookie = cookieStore.get(EMPRESA_ACTIVA_COOKIE)?.value;
    const empresaIdCookie = valorCookie ? Number(valorCookie) : null;
    if (empresaIdCookie !== null && !Number.isNaN(empresaIdCookie)) {
      const { data: empresaActiva } = await supabase
        .from("empresas")
        .select("nombre_comercial")
        .eq("id", empresaIdCookie)
        .maybeSingle();
      if (empresaActiva) {
        empresaId = empresaIdCookie;
        nombreEmpresa = empresaActiva.nombre_comercial;
        empresaActivaElegida = true;
      }
      // si la empresa de la cookie ya no existe (borrada), se ignora
      // silenciosamente y queda en el default (sin empresa asignada) —
      // evita que superadmin quede "trabado" con un id inválido.
    }
  }

  let timeoutInactividadMinutos = TIMEOUT_INACTIVIDAD_DEFAULT_MINUTOS;
  if (empresaId) {
    const { data: cfg } = await supabase
      .from("configuraciones_empresa")
      .select("timeout_inactividad_minutos")
      .eq("empresa_id", empresaId)
      .maybeSingle();
    if (cfg) timeoutInactividadMinutos = cfg.timeout_inactividad_minutos;
  }

  return {
    authUserId: user.id,
    email: user.email ?? perfil.email,
    username: perfil.username,
    nombreEmpresa,
    empresaId,
    rol: perfil.rol,
    propietarioFiltro: perfil.propietario_filtro,
    terminosAceptados: perfil.terminos_aceptados,
    permisos,
    timeoutInactividadMinutos,
    empresaActivaElegida,
  };
}

/** Para Server Pages protegidas: redirige a /login si no hay sesión válida. */
export async function requireSessionProfile(): Promise<SessionProfile> {
  const perfil = await getSessionProfile();
  if (!perfil) redirect("/login");
  return perfil;
}

/**
 * Igual que requireSessionProfile(), pero además exige el permiso de la
 * pestaña indicada — este es el chequeo real que faltaba (ver bug de
 * seguridad en docs/DESIGN_LOG.md). Cada page.tsx de un módulo debe
 * usar esta función en vez de requireSessionProfile() a secas.
 * Sin el permiso: redirige a /dashboard (no a /login, ya tiene sesión
 * válida, solo no le corresponde esa pestaña).
 */
export async function requireSessionProfileConPermiso(pestana: string): Promise<SessionProfile> {
  const perfil = await requireSessionProfile();
  if (!puedeAcceder(perfil.rol, perfil.permisos, pestana)) {
    redirect("/dashboard");
  }
  return perfil;
}

/**
 * Para usar al principio de cada Server Action de escritura — misma
 * validación que requireSessionProfileConPermiso(), pero lanza un error
 * en vez de redirigir (una action no navega, y el cliente ya sabe
 * mostrar el mensaje de error de una action fallida). Segunda capa de
 * la misma defensa: aunque alguien invoque la action directo sin pasar
 * por la página, igual se valida acá.
 */
export async function requirePermisoAction(pestana: string): Promise<SessionProfile> {
  const perfil = await requireSessionProfile();
  if (!puedeAcceder(perfil.rol, perfil.permisos, pestana)) {
    throw new Error("No tenés permiso para esta acción.");
  }
  return perfil;
}
