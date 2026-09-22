"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { createAdminAuthClient } from "@/lib/supabase/admin";
import { requireSessionProfile } from "@/lib/auth/session";
import { PESTANAS_MAESTRAS, PERMISOS_TRANSVERSALES } from "@/lib/auth/permissions";
import { verificarConflicto } from "@/lib/concurrencia/queries";
import type { Rol } from "@/lib/types/database.types";

/** Todas las claves de permiso administrables desde este editor (pestañas + transversales). */
const CLAVES_PERMISO_VALIDAS = [
  ...PESTANAS_MAESTRAS.map((p) => p.clave),
  ...PERMISOS_TRANSVERSALES.map((p) => p.clave),
];

/**
 * "El admin solo puede otorgar los permisos que él mismo tiene" —
 * regla confirmada por el usuario (ver docs/DESIGN_LOG.md). Se valida
 * acá ADEMÁS de en la UI (que ya deshabilita los checkboxes que el
 * admin no tiene) y además de la policy de RLS sobre permisos_usuario
 * (0013_panel_gestion_usuarios.sql) — tres capas de la misma regla.
 */
function permisosSonSubconjunto(permisosPedidos: string[], permisosDeQuienOtorga: string[]): boolean {
  return permisosPedidos.every((p) => permisosDeQuienOtorga.includes(p));
}

/**
 * admin: solo puede crear/editar usuarios "user" o "propietario" — no
 * puede crearse a sí mismo pares (otro admin) ni superadmins.
 * superadmin: puede asignar cualquier rol salvo "superadmin" (ese único
 * caso especial sigue viviendo en crearEmpresaConAdmin, que además crea
 * la empresa).
 */
function puedeAsignarRol(rolDeQuienOtorga: Rol, rolPedido: Rol): boolean {
  if (rolPedido === "superadmin") return false;
  if (rolDeQuienOtorga === "superadmin") return true;
  if (rolDeQuienOtorga === "admin") return rolPedido === "user" || rolPedido === "propietario";
  return false;
}

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

/**
 * `empresaId` viaja explícito desde el selector del componente (mismo
 * patrón que la Migración CSV) — antes se usaba `perfil.empresaId`
 * directo, lo que ataba esta herramienta a la empresa propia del
 * superadmin y no dejaba operar sobre ninguna otra empresa de la
 * plataforma (corregido esta sesión, a pedido del usuario).
 */
export async function borrarEnBloque(
  empresaId: number,
  tabla: "contratos" | "inquilinos" | "propiedades" | "pagos_historial",
  ids: number[],
  confirmacion: string
): Promise<{ ok: boolean; eliminados?: number; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") return { ok: false, error: "Solo superadmin puede usar esta herramienta." };

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("eliminar_registros_bloque", {
    p_tabla: tabla,
    p_ids: ids,
    p_empresa_id: empresaId,
    p_confirmacion: confirmacion,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/panel-gestion");
  return { ok: true, eliminados: data as number };
}

// =====================================================================
// Módulo 1 — Gestión de Usuarios (alta, edición, permisos)
//
// A diferencia de crearEmpresaConAdmin/enviarLinkAcceso, estas acciones
// usan el cliente normal (con sesión) — la autorización real la hacen
// las policies de RLS de 0013_panel_gestion_usuarios.sql, y acá se
// repiten los mismos chequeos para poder devolver un mensaje de error
// claro en vez de que la fila simplemente no se inserte/actualice.
//
// El alta acá NO crea la cuenta de Auth (auth_user_id queda null) — para
// eso se usa el botón "Enviar Link de Acceso" ya existente
// (enviarLinkAcceso), que sí necesita service_role.
// =====================================================================

export interface UsuarioEditable {
  id: number;
  username: string;
  email: string | null;
  telefono: string | null;
  rol: Rol;
  propietarioFiltro: string | null;
  tieneAcceso: boolean; // auth_user_id !== null
  permisos: string[];
  /** Optimistic locking — ver actualizarUsuario() y lib/concurrencia/queries.ts. */
  updatedAt: string;
}

export async function listarUsuariosEditables(empresaId: number): Promise<UsuarioEditable[]> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") return [];
  if (perfil.rol === "admin" && perfil.empresaId !== empresaId) return [];

  const supabase = await createClient();
  const { data: usuarios } = await supabase
    .from("usuarios_central")
    .select("id, username, email, telefono, rol, propietario_filtro, auth_user_id, updated_at")
    .eq("empresa_id", empresaId)
    .order("username");
  if (!usuarios) return [];

  const { data: permisos } = await supabase
    .from("permisos_usuario")
    .select("username, pestana")
    .in("username", usuarios.map((u) => u.username));

  return usuarios.map((u) => ({
    id: u.id,
    username: u.username,
    email: u.email,
    telefono: u.telefono,
    rol: u.rol,
    propietarioFiltro: u.propietario_filtro,
    tieneAcceso: u.auth_user_id !== null,
    permisos: (permisos ?? []).filter((p) => p.username === u.username).map((p) => p.pestana),
    updatedAt: u.updated_at,
  }));
}

export async function crearUsuarioEnEmpresa(datos: {
  empresaId: number;
  username: string;
  email: string;
  telefono: string;
  rol: Rol;
  propietarioFiltro: string | null;
  permisos: string[];
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") {
    return { ok: false, error: "No tenés permiso para esta acción." };
  }
  if (perfil.rol === "admin" && perfil.empresaId !== datos.empresaId) {
    return { ok: false, error: "No podés crear usuarios fuera de tu empresa." };
  }
  if (!puedeAsignarRol(perfil.rol, datos.rol)) {
    return { ok: false, error: "No tenés permiso para asignar ese rol." };
  }
  const permisosInvalidos = datos.permisos.filter((p) => !CLAVES_PERMISO_VALIDAS.includes(p));
  if (permisosInvalidos.length > 0) {
    return { ok: false, error: `Permiso desconocido: ${permisosInvalidos.join(", ")}` };
  }
  if (perfil.rol === "admin" && !permisosSonSubconjunto(datos.permisos, perfil.permisos)) {
    return { ok: false, error: "No podés otorgar un permiso que vos mismo no tenés." };
  }

  const supabase = await createClient();

  const { error: errorUsuario } = await supabase.from("usuarios_central").insert({
    username: datos.username,
    email: datos.email,
    telefono: datos.telefono || null,
    nombre_empresa: perfil.nombreEmpresa,
    empresa_id: datos.empresaId,
    rol: datos.rol,
    propietario_filtro: datos.rol === "propietario" ? datos.propietarioFiltro : null,
    terminos_aceptados: false,
  });
  if (errorUsuario) return { ok: false, error: errorUsuario.message };

  if (datos.permisos.length > 0) {
    const { error: errorPermisos } = await supabase
      .from("permisos_usuario")
      .insert(datos.permisos.map((pestana) => ({ username: datos.username, pestana })));
    if (errorPermisos) return { ok: false, error: errorPermisos.message };
  }

  revalidatePath("/panel-gestion");
  return { ok: true };
}

export async function actualizarUsuario(datos: {
  id: number;
  username: string;
  telefono: string;
  rol: Rol;
  propietarioFiltro: string | null;
  permisos: string[];
  /** updated_at que tenía el formulario al abrirse — ver módulo "Ediciones simultáneas". */
  updatedAtEsperado: string;
}): Promise<{ ok: boolean; error?: string; conflicto?: boolean; updatedAtActual?: string }> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") {
    return { ok: false, error: "No tenés permiso para esta acción." };
  }
  if (!puedeAsignarRol(perfil.rol, datos.rol)) {
    return { ok: false, error: "No tenés permiso para asignar ese rol." };
  }
  const permisosInvalidos = datos.permisos.filter((p) => !CLAVES_PERMISO_VALIDAS.includes(p));
  if (permisosInvalidos.length > 0) {
    return { ok: false, error: `Permiso desconocido: ${permisosInvalidos.join(", ")}` };
  }
  if (perfil.rol === "admin" && !permisosSonSubconjunto(datos.permisos, perfil.permisos)) {
    return { ok: false, error: "No podés otorgar un permiso que vos mismo no tenés." };
  }

  // Optimistic locking (ver docs/DESIGN_LOG.md, "Ediciones simultáneas")
  // — bloquea el guardado por igual a cualquier rol, incluido superadmin,
  // si alguien más guardó cambios sobre esta misma fila mientras se
  // editaba acá.
  const conflicto = await verificarConflicto("usuarios_central", String(datos.id), datos.updatedAtEsperado);
  if (conflicto.hayConflicto) {
    return {
      ok: false,
      conflicto: true,
      updatedAtActual: conflicto.updatedAtActual,
      error: "Alguien más guardó cambios sobre este usuario mientras lo editabas. Actualizá y volvé a intentar.",
    };
  }

  const supabase = await createClient();

  // empresa_id no se toca acá — RLS ("admin_edita_usuarios_empresa")
  // ya impide que un admin edite una fila fuera de su empresa o una
  // fila de rol superadmin; si igual se coló un id inválido, el update
  // simplemente afecta 0 filas y supabase-js no lo reporta como error,
  // así que se verifica explícitamente.
  const { data: actualizado, error: errorUsuario } = await supabase
    .from("usuarios_central")
    .update({
      telefono: datos.telefono || null,
      rol: datos.rol,
      propietario_filtro: datos.rol === "propietario" ? datos.propietarioFiltro : null,
    })
    .eq("id", datos.id)
    .select("id")
    .maybeSingle();
  if (errorUsuario) return { ok: false, error: errorUsuario.message };
  if (!actualizado) return { ok: false, error: "No se pudo editar ese usuario (¿permisos?)." };

  // Reemplazo completo de permisos: borrar todos los actuales e
  // insertar los nuevos, más simple y menos propenso a bugs que un
  // diff, y el volumen por usuario es chico (< 15 filas).
  const { error: errorBorrado } = await supabase.from("permisos_usuario").delete().eq("username", datos.username);
  if (errorBorrado) return { ok: false, error: errorBorrado.message };

  if (datos.permisos.length > 0) {
    const { error: errorInsercion } = await supabase
      .from("permisos_usuario")
      .insert(datos.permisos.map((pestana) => ({ username: datos.username, pestana })));
    if (errorInsercion) return { ok: false, error: errorInsercion.message };
  }

  revalidatePath("/panel-gestion");
  return { ok: true };
}

// ── Configuraciones de empresa (toggle de WhatsApp y de actualización
// automática de alquiler) — columnas ya existentes en
// configuraciones_empresa, edición nueva desde Panel de Gestión. ──────
export async function obtenerConfiguracionEmpresa(empresaId: number): Promise<{
  actualizarAlquilerAuto: boolean;
  whatsappHabilitado: boolean;
  timeoutInactividadMinutos: number;
} | null> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") return null;
  if (perfil.rol === "admin" && perfil.empresaId !== empresaId) return null;

  const supabase = await createClient();
  const { data } = await supabase
    .from("configuraciones_empresa")
    .select("actualizar_alquiler_auto, whatsapp_habilitado, timeout_inactividad_minutos")
    .eq("empresa_id", empresaId)
    .maybeSingle();
  if (!data) return null;
  return {
    actualizarAlquilerAuto: data.actualizar_alquiler_auto,
    whatsappHabilitado: data.whatsapp_habilitado,
    timeoutInactividadMinutos: data.timeout_inactividad_minutos,
  };
}

export async function actualizarConfiguracionEmpresa(
  empresaId: number,
  cambios: Partial<{
    actualizar_alquiler_auto: boolean;
    whatsapp_habilitado: boolean;
    timeout_inactividad_minutos: number;
  }>
): Promise<{ ok: boolean; error?: string }> {
  if (
    cambios.timeout_inactividad_minutos !== undefined &&
    (!Number.isInteger(cambios.timeout_inactividad_minutos) || cambios.timeout_inactividad_minutos < 1)
  ) {
    return { ok: false, error: "El tiempo de inactividad tiene que ser un número entero mayor a 0." };
  }
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") {
    return { ok: false, error: "No tenés permiso para esta acción." };
  }
  if (perfil.rol === "admin" && perfil.empresaId !== empresaId) {
    return { ok: false, error: "No podés editar la configuración de otra empresa." };
  }

  const supabase = await createClient();
  const { error } = await supabase.from("configuraciones_empresa").update(cambios).eq("empresa_id", empresaId);
  if (error) return { ok: false, error: error.message };

  revalidatePath("/panel-gestion");
  return { ok: true };
}
