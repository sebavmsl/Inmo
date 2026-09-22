import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { esSoloLectura } from "@/lib/auth/permissions";
import { createClient } from "@/lib/supabase/server";
import { getHistorialGastos } from "@/lib/gastos/queries";
import { getDatosMetricasGastos } from "@/lib/gastos/metricas";
import { TabsGastos } from "@/components/gastos/TabsGastos";

export default async function GastosPage() {
  const perfil = await requireSessionProfileConPermiso("gastos");
  const soloLectura = esSoloLectura(perfil.rol);
  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;

  const supabase = await createClient();
  let propiedadesQuery = supabase.from("propiedades").select("id, alias_propiedad, grupo").order("alias_propiedad");
  if (empresaFiltro !== undefined) {
    propiedadesQuery =
      empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
  }

  const [{ data: propiedades }, historial, metricas] = await Promise.all([
    propiedadesQuery,
    getHistorialGastos(propietarioFiltro, empresaFiltro),
    getDatosMetricasGastos(propietarioFiltro, empresaFiltro),
  ]);

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">🔧 Gastos de Propiedades</h1>
      <p className="mb-4 text-sm text-brand-500">
        {perfil.nombreEmpresa}
        {propietarioFiltro && ` · filtrado a ${propietarioFiltro}`}
      </p>

      <TabsGastos
        mostrarAlta={!soloLectura}
        propiedades={(propiedades ?? []).map((p) => ({ id: p.id, aliasPropiedad: p.alias_propiedad, grupo: p.grupo }))}
        historial={historial}
        metricas={metricas}
        ocultarFiltroPropietario={!!propietarioFiltro}
      />
    </div>
  );
}
