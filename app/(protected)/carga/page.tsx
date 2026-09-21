import { requireSessionProfile } from "@/lib/auth/session";
import { esSoloLectura } from "@/lib/auth/permissions";
import { FormularioContrato } from "@/components/carga/FormularioContrato";

export default async function CargaPage() {
  const perfil = await requireSessionProfile();

  if (esSoloLectura(perfil.rol)) {
    return (
      <div className="rounded-lg border border-brand-100 bg-white p-6 text-sm text-brand-500">
        Tu rol tiene acceso de solo lectura — no podés cargar contratos.
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">📝 Carga de Contratos</h1>
      <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>
      <FormularioContrato />
    </div>
  );
}
