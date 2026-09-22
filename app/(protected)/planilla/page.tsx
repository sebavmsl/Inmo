import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { esSoloLectura, tieneWhatsapp } from "@/lib/auth/permissions";
import { getCobranzasDelMes } from "@/lib/planilla/queries";
import { createClient } from "@/lib/supabase/server";
import { TablaCobranzas } from "@/components/planilla/TablaCobranzas";
import { BotonActualizarIndices } from "@/components/planilla/BotonActualizarIndices";
import { BotonEnviarMasivo } from "@/components/planilla/BotonEnviarMasivo";

/**
 * Puerto de "PESTAÑA 2: PLANILLA DE COBRANZAS" (app.py, Módulo 3).
 * Ver docs/DESIGN_LOG.md para el diseño completo (motor de índices,
 * vencimiento automático, archivado, verificación persistida).
 */
export default async function PlanillaPage() {
  const perfil = await requireSessionProfileConPermiso("planilla");
  const soloLectura = esSoloLectura(perfil.rol);

  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  const filas = await getCobranzasDelMes(propietarioFiltro);

  let whatsappHabilitado = false;
  if (perfil.empresaId) {
    const supabase = await createClient();
    const { data: cfg } = await supabase
      .from("configuraciones_empresa")
      .select("whatsapp_habilitado")
      .eq("empresa_id", perfil.empresaId)
      .single();
    whatsappHabilitado = tieneWhatsapp(perfil.rol, perfil.permisos, cfg?.whatsapp_habilitado ?? false);
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">📊 Planilla de Contratos</h1>
      <p className="mb-4 text-sm text-brand-500">
        {perfil.nombreEmpresa}
        {propietarioFiltro && ` · filtrado a ${propietarioFiltro}`}
      </p>

      {!soloLectura && (
        <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-brand-100 bg-white p-3">
          <BotonActualizarIndices />
          {whatsappHabilitado && <BotonEnviarMasivo />}
          <a
            href="/api/planilla/pdf"
            className="rounded-lg border border-brand-200 px-4 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-50"
          >
            📄 Descargar PDF
          </a>
        </div>
      )}

      <TablaCobranzas filas={filas} soloLectura={soloLectura} />
    </div>
  );
}
