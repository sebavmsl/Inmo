import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { getComprobantes, getReclamos } from "@/lib/portal-inquilino/queries";
import { TabsPortalInquilino } from "@/components/portal-inquilino/TabsPortalInquilino";

/**
 * Bandejas del staff para las dos acciones que el inquilino puede hacer
 * desde su Portal (Módulo 9, sin equivalente en v1 — ver
 * docs/DESIGN_LOG.md): comprobantes subidos a revisar, y reclamos
 * avisados a resolver.
 */
export default async function PortalInquilinoPage() {
  const perfil = await requireSessionProfileConPermiso("portal_inquilino");

  const [comprobantes, reclamos] = await Promise.all([getComprobantes(), getReclamos()]);

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">📮 Portal Inquilino</h1>
      <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>

      <TabsPortalInquilino comprobantesIniciales={comprobantes} reclamosIniciales={reclamos} />
    </div>
  );
}
