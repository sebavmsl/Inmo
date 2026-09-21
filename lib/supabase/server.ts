import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { createClient as createSupabaseClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/lib/types/database.types";

/**
 * Cliente Supabase para usar en Server Components, Server Actions y Route
 * Handlers. Lee/escribe la sesión desde las cookies de Next.js.
 *
 * Equivalente al `_pg_conn()` de app.py, pero autenticado como el usuario
 * (RLS aplica automáticamente) en vez de una conexión "admin" plana.
 *
 * El tipo de retorno se anota EXPLÍCITAMENTE (`Promise<SupabaseClient<Database>>`)
 * en vez de dejar que TypeScript lo infiera solo del `return` — con
 * generics tan anidados como los de Supabase, la inferencia implícita
 * puede colapsar de formas difíciles de rastrear.
 */
export async function createClient(): Promise<SupabaseClient<Database>> {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Se llama desde un Server Component (no puede setear cookies);
            // el middleware ya se encarga de refrescar la sesión en ese caso.
          }
        },
      },
    }
  );
}

/**
 * Cliente con la service_role key — bypassea RLS por completo.
 * SOLO para tareas administrativas server-side puntuales (ej: crear un
 * usuario de Supabase Auth desde el Panel de Gestión al dar de alta un
 * inquilino/usuario nuevo). Nunca usar para queries de datos de negocio.
 *
 * CORREGIDO: antes usaba require("@supabase/supabase-js") — TypeScript
 * no puede aplicar generics a una función obtenida así ("Untyped
 * function calls may not accept type arguments"). Ahora usa el import
 * normal de arriba.
 */
export function createAdminClient(): SupabaseClient<Database> {
  return createSupabaseClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}
