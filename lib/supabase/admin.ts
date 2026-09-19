import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/lib/types/database.types";

/**
 * Cliente con la service_role key — el ÚNICO lugar de todo el proyecto
 * que la usa (ver docs/DESIGN_LOG.md, "Alta de empresa nueva — único
 * lugar de v2 que necesita service_role"). Se usa exclusivamente para
 * llamar a la Admin API de Supabase Auth (crear usuarios, invitar,
 * resetear contraseñas) — operaciones que no son de base de datos y por
 * lo tanto no pueden resolverse con una función SECURITY DEFINER como
 * el resto del proyecto.
 *
 * NUNCA importar este archivo desde un Client Component ni exponer la
 * key al navegador — server-only, siempre detrás de un chequeo de rol
 * superadmin/admin en el Server Action que lo use.
 */
export function createAdminAuthClient() {
  return createSupabaseClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}
