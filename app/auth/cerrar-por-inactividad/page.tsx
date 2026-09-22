import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase/server";

/**
 * Destino al que redirige el middleware (capa 2 de "Cierre de sesión
 * por inactividad") cuando detecta que pasó el tiempo configurado sin
 * actividad — ver lib/supabase/middleware.ts. También es a donde cae
 * InactivityGuard.tsx (capa 1, cliente) cuando el countdown de la
 * capa 1 llega a cero, para que el cierre real (signOut + borrado de
 * las cookies de actividad) pase siempre por acá, en un único lugar.
 */
export default async function CerrarPorInactividadPage({
  searchParams,
}: {
  searchParams: Promise<{ volver?: string }>;
}) {
  const { volver } = await searchParams;

  const supabase = await createClient();
  await supabase.auth.signOut();

  const cookieStore = await cookies();
  cookieStore.delete("ult_actividad");
  cookieStore.delete("ult_actividad_timeout");

  const loginPath = volver?.startsWith("/portal") ? "/portal/login" : "/login";
  redirect(`${loginPath}?motivo=inactividad`);
}
