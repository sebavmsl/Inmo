import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Refresca el token de sesión de Supabase en cada request y decide los
 * redirects base de autenticación. Llamado desde middleware.ts (raíz).
 */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // IMPORTANTE: no borrar este await. Refresca el token si expiró.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;
  const esRutaPortal = path.startsWith("/portal");
  const loginPath = esRutaPortal ? "/portal/login" : "/login";
  const homePath = esRutaPortal ? "/portal/mi-cuenta" : "/dashboard";
  const RUTA_LOGOUT_INACTIVIDAD = "/auth/cerrar-por-inactividad";
  const RUTA_PING_ACTIVIDAD = "/api/actividad";
  const esRutaPublica =
    path === loginPath ||
    path.startsWith("/api/whatsapp") ||
    path === RUTA_LOGOUT_INACTIVIDAD ||
    path === RUTA_PING_ACTIVIDAD;

  if (!user && !esRutaPublica) {
    const url = request.nextUrl.clone();
    url.pathname = loginPath;
    return NextResponse.redirect(url);
  }

  if (user && path === loginPath) {
    const url = request.nextUrl.clone();
    url.pathname = homePath;
    return NextResponse.redirect(url);
  }

  // ── Cierre de sesión por inactividad — capa 2 (server-side) ─────────
  // Capa 1 (InactivityGuard.tsx, cliente) avisa y cierra sola con JS.
  // Esta capa no depende de que el JS del cliente haya corrido: alcanza
  // con la cookie httpOnly que /api/actividad va renovando mientras hay
  // interacción real. Si no hay cookie (sesión recién iniciada, todavía
  // no llegó el primer ping) no se corta nada — más vale un falso
  // negativo acá que cortar sesiones nuevas por error.
  //
  // Por ahora solo el staff (InactivityGuard está en el layout
  // protegido, no en /portal) manda el ping que arma la cookie — así
  // que se restringe explícitamente a rutas de staff para no dejar una
  // condición que nunca hace nada en /portal/*.
  if (user && !esRutaPortal && !esRutaPublica) {
    const ultimaActividad = request.cookies.get("ult_actividad")?.value;
    const timeoutMin = request.cookies.get("ult_actividad_timeout")?.value;
    if (ultimaActividad && timeoutMin) {
      const minutosInactivo = (Date.now() - Number(ultimaActividad)) / 60_000;
      if (minutosInactivo > Number(timeoutMin)) {
        const url = request.nextUrl.clone();
        url.pathname = RUTA_LOGOUT_INACTIVIDAD;
        url.search = "";
        url.searchParams.set("volver", path);
        return NextResponse.redirect(url);
      }
    }
  }

  // El bloque de Términos y Condiciones (abajo) es exclusivo del staff
  // (usuarios_central) — las rutas /portal/* del inquilino no pasan por
  // acá, evita una consulta innecesaria en cada request del Portal.
  if (esRutaPortal) return response;

  // Puerto del bloque "Verificar aceptación de términos" de app.py
  // (líneas ~1229-1271): mientras no acepte T&C, cualquier pestaña que no
  // sea /terminos redirige ahí. El superadmin queda exento, igual que v1.
  if (user && !esRutaPublica && path !== "/terminos") {
    const { data: perfil } = await supabase
      .from("usuarios_central")
      .select("rol, terminos_aceptados")
      .eq("auth_user_id", user.id)
      .single();

    if (perfil && perfil.rol !== "superadmin" && !perfil.terminos_aceptados) {
      const url = request.nextUrl.clone();
      url.pathname = "/terminos";
      return NextResponse.redirect(url);
    }
  }

  return response;
}
