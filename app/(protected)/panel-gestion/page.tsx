import { requireSessionProfile } from "@/lib/auth/session";
import { createClient } from "@/lib/supabase/server";
import { AltaEmpresa } from "@/components/panel-gestion/AltaEmpresa";
import { EditarUsuario } from "@/components/panel-gestion/EditarUsuario";
import { EliminarEmpresa } from "@/components/panel-gestion/EliminarEmpresa";
import { BorradoEnBloque } from "@/components/panel-gestion/BorradoEnBloque";

export default async function PanelGestionPage() {
  const perfil = await requireSessionProfile();

  if (perfil.rol !== "superadmin") {
    return (
      <div className="rounded-lg border border-brand-100 bg-white p-6 text-sm text-brand-500">
        Solo el superadmin puede acceder al Panel de Gestión.
      </div>
    );
  }

  const supabase = await createClient();
  const { data: empresas } = await supabase.from("empresas").select("id, nombre_comercial").order("nombre_comercial");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-brand-900">⚙️ Panel de Gestión</h1>
        <p className="mb-4 text-sm text-brand-500">Solo superadmin</p>
      </div>

      <AltaEmpresa />
      <EditarUsuario />
      <EliminarEmpresa empresas={(empresas ?? []).map((e) => ({ id: e.id, nombreComercial: e.nombre_comercial }))} />
      <BorradoEnBloque />
    </div>
  );
}
