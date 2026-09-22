import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { esSoloLectura } from "@/lib/auth/permissions";
import { FormularioPropiedad } from "@/components/carga/FormularioPropiedad";
import { FormularioInquilino } from "@/components/carga/FormularioInquilino";
import { FormularioGrupo } from "@/components/auxiliares/FormularioGrupo";
import { EditarPropiedad } from "@/components/auxiliares/EditarPropiedad";
import { EditarInquilino } from "@/components/auxiliares/EditarInquilino";

export default async function AuxiliaresPage() {
  const perfil = await requireSessionProfileConPermiso("auxiliares");

  if (esSoloLectura(perfil.rol)) {
    return (
      <div className="rounded-lg border border-brand-100 bg-white p-6 text-sm text-brand-500">
        Tu rol tiene acceso de solo lectura.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-brand-900">⚙️ Cargar Inquilinos / Propiedades</h1>
        <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>
      </div>
      <FormularioInquilino />
      <FormularioPropiedad />
      <FormularioGrupo />

      <div>
        <h2 className="mb-3 mt-2 text-base font-semibold text-brand-900">🔄 Modificar Datos Existentes</h2>
        <div className="space-y-6">
          <EditarInquilino />
          <EditarPropiedad />
        </div>
      </div>
    </div>
  );
}
