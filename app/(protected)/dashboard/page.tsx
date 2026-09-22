import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { getContratosActivosDashboard, getCajaHistorica } from "@/lib/dashboard/queries";
import { calcularMetricasDashboard } from "@/lib/dashboard/metrics";
import { formatMoneda } from "@/lib/format";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ListaAlertasVencimiento, ListaAlertasActualizacion } from "@/components/dashboard/AlertList";

/**
 * Puerto de "PESTAÑA 1: DASHBOARD" (app.py líneas 2518-2620).
 *
 * Diferencia clave con v1: acá el filtro por propietario se resuelve
 * antes de la query (getContratosActivosDashboard recibe el alias del
 * propietario si corresponde), en vez de pedir todo y filtrar en
 * pandas — RLS ya se encarga del aislamiento por empresa.
 */
export default async function DashboardPage() {
  const perfil = await requireSessionProfileConPermiso("dashboard");

  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  const [contratos, cajaHistorica] = await Promise.all([
    getContratosActivosDashboard(propietarioFiltro),
    getCajaHistorica(propietarioFiltro),
  ]);

  const metricas = calcularMetricasDashboard(contratos, cajaHistorica);

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">
        ⚡ Alertas Estratégicas y Métricas Generales
      </h1>
      <p className="mb-4 text-sm text-brand-500">
        {perfil.nombreEmpresa}
        {propietarioFiltro && ` · filtrado a ${propietarioFiltro}`}
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard titulo="Contratos Activos" valor={metricas.totalActivos} />
        <KpiCard
          titulo="Ajustes este Mes"
          valor={metricas.actualizanEsteMes}
          detalle={metricas.actualizanEsteMes > 0 ? `${metricas.actualizanEsteMes} requeridos` : undefined}
          tono={metricas.actualizanEsteMes > 0 ? "alerta" : "neutral"}
        />
        <KpiCard
          titulo="Próximos Vencimientos (60d)"
          valor={metricas.vencenPronto}
          detalle={metricas.vencenPronto > 0 ? `${metricas.vencenPronto} alertas` : undefined}
        />
        <KpiCard titulo="Recaudación Total de Caja" valor={formatMoneda(metricas.cajaHistorica)} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold text-brand-800">
            📅 Alertas de Vencimiento de Plazos
          </h2>
          <ListaAlertasVencimiento alertas={metricas.alertasVencimiento} />
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold text-brand-800">
            📈 Alertas de Actualización de Valores (Índices)
          </h2>
          <ListaAlertasActualizacion alertas={metricas.alertasActualizacion} />
        </div>
      </div>
    </div>
  );
}
