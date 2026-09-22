import { requireSessionProfileConPermiso } from "@/lib/auth/session";
import {
  getPropietarios,
  getRendicionAgrupada,
  getDetalleRendicion,
  calcularResumenRendicion,
  obtenerLiquidacionExistente,
} from "@/lib/rendicion/queries";
import { SelectorRendicion } from "@/components/rendicion/SelectorRendicion";
import { TablaPropiedadesRendicion } from "@/components/rendicion/TablaPropiedadesRendicion";
import { DetalleRecibosRendicion } from "@/components/rendicion/DetalleRecibosRendicion";
import { ResumenLiquidacion } from "@/components/rendicion/ResumenLiquidacion";

export default async function RendicionPage({
  searchParams,
}: {
  searchParams: Promise<{ propietario?: string; periodo?: string }>;
}) {
  const perfil = await requireSessionProfileConPermiso("rendicion");
  const { propietario, periodo } = await searchParams;

  const esPropietario = perfil.rol === "propietario" && !!perfil.propietarioFiltro;

  // "" = Todos los propietarios (solo para staff — el rol propietario
  // queda fijo a lo suyo, igual que v1). "todos" = Todos los períodos.
  const propietarioSel = esPropietario ? perfil.propietarioFiltro! : propietario ?? "";
  const periodoSel = periodo ?? "todos";
  const periodoFiltro = periodoSel === "todos" ? null : periodoSel;
  const propietarioFiltro = propietarioSel || null;

  const propietarios = perfil.empresaId && !esPropietario ? await getPropietarios(perfil.empresaId) : [];

  const { filas, totales } = perfil.empresaId
    ? await getRendicionAgrupada(perfil.empresaId, propietarioFiltro, periodoFiltro)
    : { filas: [], totales: null };

  const detalle = perfil.empresaId ? await getDetalleRendicion(perfil.empresaId, propietarioFiltro, periodoFiltro) : [];

  // La sección de Liquidación (registrar + PDF) solo aplica a una
  // combinación específica de propietario + período — igual que v1.
  const combinacionEspecifica = !!propietarioFiltro && !!periodoFiltro;
  const [resumenLiquidacion, liquidacionExistente] =
    combinacionEspecifica && perfil.empresaId
      ? await Promise.all([
          calcularResumenRendicion(perfil.empresaId, propietarioFiltro!, periodoFiltro!),
          obtenerLiquidacionExistente(perfil.empresaId, propietarioFiltro!, periodoFiltro!),
        ])
      : [null, null];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-brand-900">📑 Rendición a Propietarios</h1>
        <p className="mb-4 text-sm text-brand-500">
          {perfil.nombreEmpresa} — lo cobrado por propiedad, con la comisión administrativa ya descontada.
        </p>
      </div>

      <SelectorRendicion
        propietarios={propietarios}
        propietarioInicial={propietarioSel}
        periodoInicial={periodoSel}
        soloPropioPropietario={esPropietario}
      />

      {!totales ? (
        <p className="text-sm text-brand-500">Todavía no hay cobros registrados para generar una rendición.</p>
      ) : (
        <>
          <TablaPropiedadesRendicion
            filas={filas}
            totales={totales}
            propietarioLabel={propietarioSel || "Todos"}
            periodoLabel={periodoSel === "todos" ? "Todos" : periodoSel}
          />

          <DetalleRecibosRendicion filas={detalle} />

          <div>
            <h2 className="mb-3 text-base font-semibold text-brand-900">💵 Liquidación</h2>
            {!combinacionEspecifica ? (
              <p className="rounded-lg border border-brand-100 bg-white p-4 text-sm text-brand-500">
                Elegí un <strong>propietario</strong> y un <strong>período</strong> específicos (no &quot;Todos&quot;) para registrar la liquidación y generar el PDF.
              </p>
            ) : (
              resumenLiquidacion && <ResumenLiquidacion key={`${propietarioSel}-${periodoSel}`} resumen={resumenLiquidacion} liquidacionExistente={liquidacionExistente} />
            )}
          </div>
        </>
      )}
    </div>
  );
}
