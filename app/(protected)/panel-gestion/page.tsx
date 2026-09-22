import { requireSessionProfile } from "@/lib/auth/session";
import { createClient } from "@/lib/supabase/server";
import { AltaEmpresa } from "@/components/panel-gestion/AltaEmpresa";
import { EditarUsuario } from "@/components/panel-gestion/EditarUsuario";
import { EliminarEmpresa } from "@/components/panel-gestion/EliminarEmpresa";
import { BorradoEnBloque } from "@/components/panel-gestion/BorradoEnBloque";
import { PanelUsuariosYConfig } from "@/components/panel-gestion/PanelUsuariosYConfig";
import { MigracionCsv } from "@/components/panel-gestion/MigracionCsv";

/**
 * "panel_gestion" no es una pestaña de permisos_usuario (superadmin y
 * admin la tienen siempre, ver pestanasVisibles()) — el control de
 * acceso acá es por ROL directamente, no por permiso, así que alcanza
 * con requireSessionProfile() (exige sesión válida) y el filtro fino
 * de abajo.
 */
export default async function PanelGestionPage() {
  const perfil = await requireSessionProfile();

  if (perfil.rol !== "superadmin" && perfil.rol !== "admin") {
    return (
      <div className="rounded-lg border border-brand-100 bg-white p-6 text-sm text-brand-500">
        No tenés acceso al Panel de Gestión.
      </div>
    );
  }

  const esSuperadmin = perfil.rol === "superadmin";
  const supabase = await createClient();

  const empresas = esSuperadmin
    ? ((await supabase.from("empresas").select("id, nombre_comercial").order("nombre_comercial")).data ?? []).map(
        (e) => ({ id: e.id, nombreComercial: e.nombre_comercial })
      )
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-brand-900">⚙️ Panel de Gestión</h1>
        <p className="mb-4 text-sm text-brand-500">
          {esSuperadmin ? "Superadmin" : `Administrador — ${perfil.nombreEmpresa}`}
        </p>
      </div>

      {esSuperadmin && <AltaEmpresa />}

      <PanelUsuariosYConfig
        rolViewer={perfil.rol}
        permisosViewer={perfil.permisos}
        empresas={empresas}
        empresaIdFija={esSuperadmin ? null : perfil.empresaId}
      />

      <EditarUsuario />

      {esSuperadmin && (
        <>
          <MigracionCsv empresas={empresas} />
          <EliminarEmpresa empresas={empresas} />
          <BorradoEnBloque empresas={empresas} />
        </>
      )}
    </div>
  );
}
