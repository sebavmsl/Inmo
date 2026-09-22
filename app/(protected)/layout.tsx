import { requireSessionProfile } from "@/lib/auth/session";
import { pestanasVisibles } from "@/lib/auth/permissions";
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

  return (
    <div className="flex min-h-screen bg-brand-50">
      <Sidebar pestanas={pestanas} nombreEmpresa={perfil.nombreEmpresa} username={perfil.username} />
      <main className="flex-1 p-6">{children}</main>
      <InactivityGuard timeoutMinutos={perfil.timeoutInactividadMinutos} />
    </div>
  );
}
