import { requireSessionProfile } from "@/lib/auth/session";
import { getPropietarios, calcularResumenRendicion } from "@/lib/rendicion/queries";
import { ResumenLiquidacion } from "@/components/rendicion/ResumenLiquidacion";

export default async function RendicionPage({
  searchParams,
}: {
  searchParams: Promise<{ propietario?: string; periodo?: string }>;
}) {
  const perfil = await requireSessionProfile();
  const { propietario, periodo } = await searchParams;

  const hoy = new Date();
  const periodoDefault = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
  const periodoElegido = periodo ?? periodoDefault;

  const propietarios = perfil.empresaId ? await getPropietarios(perfil.empresaId) : [];

  const resumen =
    propietario && perfil.empresaId
      ? await calcularResumenRendicion(perfil.empresaId, propietario, periodoElegido)
      : null;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">📑 Rendición a Propietarios</h1>
      <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>

      <ResumenLiquidacion
        propietarios={propietarios}
        resumenInicial={resumen}
        propietarioInicial={propietario ?? ""}
        periodoInicial={periodoElegido}
      />
    </div>
  );
}
