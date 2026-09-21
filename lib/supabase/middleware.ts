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
  const esRutaPublica = path === loginPath || path.startsWith("/api/whatsapp");

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
