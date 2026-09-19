"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/lib/types/database.types";

/**
 * Cliente Supabase para usar dentro de Client Components ("use client").
 * Usa la anon key — la seguridad real la da RLS, no este cliente.
 *
 * Uso:
 *   const supabase = createClient();
 *   const { data } = await supabase.from("contratos").select("*");
 */
export function createClient(): SupabaseClient<Database> {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
