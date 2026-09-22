import { requireSessionProfile } from "@/lib/auth/session";
import { pestanasVisibles } from "@/lib/auth/permissions";
import { createClient } from "@/lib/supabase/server";
import { Sidebar } from "@/components/layout/Sidebar";
import { InactivityGuard } from "@/components/InactivityGuard";

/**
 * Layout para todo lo que requiere sesión iniciada. Arma el menú lateral
 * según rol + permisos — puerto de "CONFIGURACIÓN DINÁMICA DE PESTAÑAS
 * SEGÚN PERMISOS Y ROL" de app.py (líneas ~2070-2150).
 *
 * El bloqueo por Términos y Condiciones no vive acá: lo resuelve el
 * middleware (ve la ruta actual, evita el loop de redirigir /terminos a
 * sí mismo) antes de que este layout llegue a renderizar.
 */
export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const perfil = await requireSessionProfile();

  const pestanas = pestanasVisibles(perfil.rol, perfil.permisos);
  const esSuperadmin = perfil.rol === "superadmin";

  // Lista para el selector global de empresa (SelectorEmpresaActiva,
  // dentro del Sidebar) — solo superadmin la necesita, ver
  // lib/auth/session.ts sobre cómo la elección scopea toda la sesión.
  const empresas = esSuperadmin
    ? ((await (await createClient()).from("empresas").select("id, nombre_comercial").order("nombre_comercial")).data ?? []).map(
        (e) => ({ id: e.id, nombreComercial: e.nombre_comercial })
      )
    : [];

  return (
    <div className="flex min-h-screen bg-brand-50">
      <Sidebar
        pestanas={pestanas}
        nombreEmpresa={perfil.nombreEmpresa}
        username={perfil.username}
        esSuperadmin={esSuperadmin}
        empresaIdActual={esSuperadmin ? perfil.empresaId : null}
        empresas={empresas}
      />
      <main className="flex-1 p-6">{children}</main>
      <InactivityGuard timeoutMinutos={perfil.timeoutInactividadMinutos} />
    </div>
  );
}
