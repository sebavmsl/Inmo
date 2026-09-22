import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import { esSoloLectura, tieneWhatsapp } from "@/lib/auth/permissions";
import { getCobranzasDelMes } from "@/lib/planilla/queries";
import { createClient } from "@/lib/supabase/server";
import { TablaCobranzas } from "@/components/planilla/TablaCobranzas";
import { BotonActualizarIndices } from "@/components/planilla/BotonActualizarIndices";
import { BotonEnviarMasivo } from "@/components/planilla/BotonEnviarMasivo";
import { SelectorEmpresaPlanilla } from "@/components/planilla/SelectorEmpresaPlanilla";

/**
 * Puerto de "PESTAÑA 2: PLANILLA DE COBRANZAS" (app.py, Módulo 3).
 * Ver docs/DESIGN_LOG.md para el diseño completo (motor de índices,
 * vencimiento automático, archivado, verificación persistida).
 */
export default async function PlanillaPage({
  searchParams,
}: {
  searchParams: Promise<{ empresa?: string }>;
}) {
  const perfil = await requireSessionProfileConPermiso("planilla");
  const soloLectura = esSoloLectura(perfil.rol);
  const esSuperadmin = perfil.rol === "superadmin";

  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  // superadmin no tiene empresa_id propio: por defecto (sin ?empresa= en la
  // URL) se le muestran los contratos sin empresa asignada, nunca todas las
  // inmobiliarias mezcladas — ver SelectorEmpresaPlanilla.tsx. Los demás
  // roles ya quedan acotados a la suya por RLS, así que pasan `undefined`
  // (sin filtro adicional acá).
  const { empresa: empresaParam } = await searchParams;
  const empresaFiltro: number | null | undefined = esSuperadmin ? (empresaParam ? Number(empresaParam) : null) : undefined;

  const empresas = esSuperadmin
    ? ((await (await createClient()).from("empresas").select("id, nombre_comercial").order("nombre_comercial")).data ?? []).map(
        (e) => ({ id: e.id, nombreComercial: e.nombre_comercial })
      )
    : [];

  const filas = await getCobranzasDelMes(propietarioFiltro, empresaFiltro);

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
        {esSuperadmin &&
          (empresaFiltro === null
            ? " · contratos sin empresa asignada"
            : ` · ${empresas.find((e) => e.id === empresaFiltro)?.nombreComercial ?? "empresa #" + empresaFiltro}`)}
      </p>

      {esSuperadmin && (
        <div className="mb-4">
          <SelectorEmpresaPlanilla empresas={empresas} seleccionado={empresaFiltro ?? null} />
        </div>
      )}

      {!soloLectura && (
        <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-brand-100 bg-white p-3">
          <BotonActualizarIndices />
          {whatsappHabilitado && <BotonEnviarMasivo />}
          <a
            href={esSuperadmin && empresaFiltro !== null ? `/api/planilla/pdf?empresa=${empresaFiltro}` : "/api/planilla/pdf"}
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
