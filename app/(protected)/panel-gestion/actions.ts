"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { createAdminAuthClient } from "@/lib/supabase/admin";
import { requireSessionProfile } from "@/lib/auth/session";

/**
 * Alta de empresa + primer admin — puerto del flujo diseñado en
 * docs/DESIGN_LOG.md ("Alta de empresa nueva"). Único lugar del
 * proyecto, junto con enviarLinkAcceso, que usa service_role.
 */
export async function crearEmpresaConAdmin(datos: {
  nombreComercial: string;
  emailAdmin: string;
  usernameAdmin: string;
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") return { ok: false, error: "Solo superadmin puede crear empresas." };

  const adminAuth = createAdminAuthClient();
  const supabase = await createClient();

  // 1. Invitar por email — devuelve auth_user_id, sin generar/comunicar
  //    contraseña provisoria a mano.
  const { data: invitado, error: errorInvite } = await adminAuth.auth.admin.inviteUserByEmail(datos.emailAdmin);
  if (errorInvite || !invitado.user) {
    return { ok: false, error: `Error invitando al usuario: ${errorInvite?.message}` };
  }
  const authUserId = invitado.user.id;

  // 2. Empresa + usuario + configuración + permisos, en Postgres.
  //    Si algo de esto falla, limpieza de compensación (paso 3).
  try {
    const { data: empresa, error: errorEmpresa } = await supabase
      .from("empresas")
      .insert({
        nombre_comercial: datos.nombreComercial,
        // Columna vestigial (ver docs/DESIGN_LOG.md, "archivo_db no
        // apunta a nada real hoy") — probablemente NOT NULL igual que en
        // usuarios_central, así que se completa con un valor cualquiera
        // por seguridad, nunca se usa para nada funcional en v2.
        archivo_db: `v2-${Date.now()}`,
      })
      .select("id")
      .single();
    if (errorEmpresa || !empresa) throw new Error(errorEmpresa?.message ?? "Error creando la empresa.");

    const { error: errorUsuario } = await supabase.from("usuarios_central").insert({
      username: datos.usernameAdmin,
      email: datos.emailAdmin,
      auth_user_id: authUserId,
      nombre_empresa: datos.nombreComercial,
      empresa_id: empresa.id,
      rol: "admin",
      terminos_aceptados: false,
    });
    if (errorUsuario) throw new Error(errorUsuario.message);

    const { error: errorCfg } = await supabase.from("configuraciones_empresa").insert({
      empresa_id: empresa.id,
      cron_indices_habilitado: false,
      whatsapp_habilitado: false,
      actualizar_alquiler_auto: true,
    });
    if (errorCfg) throw new Error(errorCfg.message);

    const PESTANAS = ["dashboard", "planilla", "pagos", "historial_pagos", "carga", "auxiliares", "gastos", "rendicion"];
    const { error: errorPermisos } = await supabase
      .from("permisos_usuario")
      .insert(PESTANAS.map((pestana) => ({ username: datos.usernameAdmin, pestana })));
    if (errorPermisos) throw new Error(errorPermisos.message);

    revalidatePath("/panel-gestion");
    return { ok: true };
  } catch (e) {
    // 3. Limpieza de compensación — el usuario de Auth quedó huérfano,
    //    no dejar basura a medio crear.
    await adminAuth.auth.admin.deleteUser(authUserId);
    return { ok: false, error: e instanceof Error ? e.message : "Error creando la empresa." };
  }
}

/**
 * "Enviar link de acceso" — unifica migración v1→v2 y reset de
 * contraseña (ver DESIGN_LOG.md, "Editar Usuario"). `tabla` indica si es
 * un usuario del staff (usuarios_central) o un inquilino (Módulo 9).
 */
export async function enviarLinkAcceso(params: {
  tabla: "usuarios_central" | "inquilinos";
  identificador: { username?: string; dni?: string };
  email: string;
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") {
    return { ok: false, error: "No tenés permiso para esta acción." };
  }

  const supabase = await createClient();
  const adminAuth = createAdminAuthClient();

  const filtro = params.tabla === "usuarios_central" ? { username: params.identificador.username } : { dni: params.identificador.dni };

  // Admin (no superadmin) solo puede operar sobre usuarios de su propia
  // empresa — superadmin no tiene esa restricción. Se arma la query
  // condicionalmente en vez de pasar `undefined` a .eq() (no es válido
  // como "saltear el filtro" en Supabase-js).
  let queryFila = supabase.from(params.tabla).select("auth_user_id").match(filtro);
  if (perfil.rol !== "superadmin") {
    queryFila = queryFila.eq("empresa_id", perfil.empresaId ?? -1);
  }
  const { data: fila } = await queryFila.maybeSingle();

  if (!fila || !fila.auth_user_id) {
    // Primera vez para ESTA fila — pero el email puede ya tener cuenta
    // de Auth si la misma persona es inquilino de otra empresa (ver
    // DESIGN_LOG.md, caso de borde de multi-tenencia, Módulo 9).
    // inviteUserByEmail falla si el email ya existe — en ese caso,
    // reusamos el auth_user_id existente en vez de crear uno nuevo.
    let authUserId: string;
    const { data: invitado, error: errorInvite } = await adminAuth.auth.admin.inviteUserByEmail(params.email);

    if (invitado?.user) {
      authUserId = invitado.user.id;
    } else {
      const { data: listado } = await adminAuth.auth.admin.listUsers();
      const existente = listado?.users.find((u) => u.email === params.email);
      if (!existente) return { ok: false, error: errorInvite?.message ?? "Error al invitar." };
      authUserId = existente.id;
    }

    const { error: errorUpdate } = await supabase
      .from(params.tabla)
      .update({ auth_user_id: authUserId, email: params.email })
      .match(filtro);
    if (errorUpdate) return { ok: false, error: errorUpdate.message };
    return { ok: true };
  }

  // Ya migrado — reset de contraseña
  const { error } = await adminAuth.auth.resetPasswordForEmail(params.email);
  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function eliminarEmpresa(empresaId: number, confirmacionNombre: string): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") return { ok: false, error: "Solo superadmin puede eliminar empresas." };

  const supabase = await createClient();
  const { error } = await supabase.rpc("eliminar_empresa_completa", {
    p_empresa_id: empresaId,
    p_confirmacion_nombre: confirmacionNombre,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/panel-gestion");
  return { ok: true };
}

export async function borrarEnBloque(
  tabla: "contratos" | "inquilinos" | "propiedades" | "pagos_historial",
  ids: number[],
  confirmacion: string
): Promise<{ ok: boolean; eliminados?: number; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") return { ok: false, error: "Solo superadmin puede usar esta herramienta." };
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("eliminar_registros_bloque", {
    p_tabla: tabla,
    p_ids: ids,
    p_empresa_id: perfil.empresaId,
    p_confirmacion: confirmacion,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/panel-gestion");
  return { ok: true, eliminados: data as number };
}
