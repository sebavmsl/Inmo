"use server";

import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";

/**
 * Módulo transversal "Ediciones simultáneas" (ver docs/DESIGN_LOG.md y
 * supabase/migrations/0014_edicion_concurrente.sql). Dos mecanismos
 * independientes que se usan juntos en cada formulario de edición:
 *
 *   1. Presencia en vivo (registrarPresencia/quitarPresencia/listarPresencia):
 *      solo informativo — "quién más tiene este formulario abierto ahora".
 *   2. Optimistic locking (verificarConflicto): el chequeo real que
 *      bloquea el guardado si alguien más guardó primero.
 *
 * Ambos viven acá (no en cada módulo) porque son exactamente el mismo
 * mecanismo para cualquier tabla — Panel de Gestión (usuarios), Auxiliares
 * (inquilinos/propiedades) y Carga (contratos) lo comparten.
 */

export const TABLAS_CON_LOCK = ["usuarios_central", "propiedades", "inquilinos", "contratos"] as const;
export type TablaConLock = (typeof TABLAS_CON_LOCK)[number];

const COLUMNA_ID: Record<TablaConLock, string> = {
  usuarios_central: "id",
  propiedades: "id",
  inquilinos: "id",
  contratos: "codigo",
};

const VENCIMIENTO_SEGUNDOS = 60;

export async function registrarPresencia(tabla: TablaConLock, registroId: string): Promise<void> {
  const perfil = await requireSessionProfile();
  if (!perfil.empresaId) return;
  const supabase = await createClient();
  await supabase.from("ediciones_presencia").upsert(
    {
      empresa_id: perfil.empresaId,
      tabla,
      registro_id: registroId,
      username: perfil.username,
      actualizado_en: new Date().toISOString(),
    },
    { onConflict: "tabla,registro_id,username" }
  );
}

export async function quitarPresencia(tabla: TablaConLock, registroId: string): Promise<void> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();
  await supabase
    .from("ediciones_presencia")
    .delete()
    .eq("tabla", tabla)
    .eq("registro_id", registroId)
    .eq("username", perfil.username);
}

export interface EditorPresente {
  username: string;
}

/**
 * Quiénes más están editando este registro ahora mismo. Excluye
 * siempre al propio usuario, y excluye siempre a superadmin —regla
 * confirmada por el usuario: nunca se revela que superadmin es uno de
 * los que está editando, ni directa ni indirectamente (si es el único
 * otro presente, esta función devuelve lista vacía, como si nadie más
 * estuviera).
 */
export async function listarPresencia(tabla: TablaConLock, registroId: string): Promise<EditorPresente[]> {
  const perfil = await requireSessionProfile();
  const supabase = await createClient();

  const limite = new Date(Date.now() - VENCIMIENTO_SEGUNDOS * 1000).toISOString();
  const { data } = await supabase
    .from("ediciones_presencia")
    .select("username")
    .eq("tabla", tabla)
    .eq("registro_id", registroId)
    .gte("actualizado_en", limite);
  if (!data) return [];

  const usernames = [...new Set(data.map((d) => d.username))].filter((u) => u !== perfil.username);
  if (usernames.length === 0) return [];

  const { data: usuarios } = await supabase.from("usuarios_central").select("username, rol").in("username", usernames);

  return (usuarios ?? []).filter((u) => u.rol !== "superadmin").map((u) => ({ username: u.username }));
}

export interface ResultadoConflicto {
  hayConflicto: boolean;
  updatedAtActual?: string;
}

/**
 * Optimistic locking: compara el `updated_at` que el formulario tenía
 * al abrirse contra el actual en la base. Si difieren, alguien más
 * guardó primero — se bloquea el guardado, para TODOS los roles por
 * igual (incluido superadmin), y se pide refrescar antes de reintentar.
 */
export async function verificarConflicto(
  tabla: TablaConLock,
  registroId: string,
  updatedAtCliente: string
): Promise<ResultadoConflicto> {
  const supabase = await createClient();
  const columnaId = COLUMNA_ID[tabla];

  const { data } = await supabase.from(tabla).select("updated_at").eq(columnaId, registroId).maybeSingle();
  if (!data) return { hayConflicto: false };

  const actual = (data as { updated_at: string }).updated_at;
  return actual === updatedAtCliente ? { hayConflicto: false } : { hayConflicto: true, updatedAtActual: actual };
}
