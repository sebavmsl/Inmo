import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { getHistorialPagos } from "@/lib/historial/queries";
import { TablaHistorial } from "@/components/historial/TablaHistorial";
import { ReporteCobros } from "@/components/historial/ReporteCobros";

export default async function HistorialPagosPage() {
  const perfil = await requireSessionProfileConPermiso("historial_pagos");

  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  const filas = await getHistorialPagos(propietarioFiltro);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-brand-900">🗄️ Historial de Caja</h1>
        <p className="mb-4 text-sm text-brand-500">
          {perfil.nombreEmpresa}
          {propietarioFiltro && ` · filtrado a ${propietarioFiltro}`}
        </p>
      </div>
      <ReporteCobros filas={filas} />
      <TablaHistorial filas={filas} />
    </div>
  );
}
