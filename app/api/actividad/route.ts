import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase/server";

/**
 * Ping de actividad — lo llama InactivityGuard.tsx cada vez que detecta
 * interacción real del usuario (throttleado del lado del cliente, no en
 * cada evento). Guarda la marca de tiempo en una cookie httpOnly que el
 * middleware compara en cada request (capa 2, server-side, ver
 * lib/supabase/middleware.ts) — así el cierre por inactividad no
 * depende de que el JS del cliente siga corriendo.
 */
export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "No autenticado." }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  const timeoutPedido = Number((body as { timeoutMinutos?: unknown })?.timeoutMinutos);
  // Clamp defensivo — nunca confiar ciegamente en lo que manda el
  // cliente (podría estar manipulado); 1..1440 min (1 día) es un rango
  // razonable para cualquier configuración real de empresa.
  const timeoutValidado = Number.isFinite(timeoutPedido)
    ? Math.min(Math.max(Math.round(timeoutPedido), 1), 1440)
    : 30;

  const cookieStore = await cookies();
  const opciones = { httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 60 * 60 * 24 };
  cookieStore.set("ult_actividad", String(Date.now()), opciones);
  cookieStore.set("ult_actividad_timeout", String(timeoutValidado), opciones);

  return NextResponse.json({ ok: true });
}
