import { requireSessionProfile } from "@/lib/auth/session";
import { esSoloLectura } from "@/lib/auth/permissions";
import { getContratoParaPago, getContratosActivosParaSelector } from "@/lib/pagos/queries";
import { SelectorContrato } from "@/components/pagos/SelectorContrato";
import { FormularioConceptos } from "@/components/pagos/FormularioConceptos";

/**
 * Puerto de "PESTAÑA 3: CONTROL DE COBRANZAS... RECIBO PDF/WHATSAPP"
 * (Módulo 4). Ver docs/DESIGN_LOG.md para el diseño completo.
 */
export default async function PagosPage({
  searchParams,
}: {
  searchParams: Promise<{ contrato?: string }>;
}) {
  const perfil = await requireSessionProfile();
  const { contrato: codigoSeleccionado } = await searchParams;

  if (esSoloLectura(perfil.rol)) {
    return (
      <div className="rounded-lg border border-brand-100 bg-white p-6 text-sm text-brand-500">
        Tu rol tiene acceso de solo lectura — no podés registrar cobros.
      </div>
    );
  }

  const contratos = await getContratosActivosParaSelector();
  const contratoSeleccionado = codigoSeleccionado ? await getContratoParaPago(codigoSeleccionado) : null;

  const hoy = new Date();
  const periodoSugerido = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">💰 Registrar Cobro Mensual y Emitir Comprobantes</h1>
      <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>

      <div className="mb-5">
        <SelectorContrato contratos={contratos} seleccionado={codigoSeleccionado} />
      </div>

      {contratoSeleccionado ? (
        <FormularioConceptos contrato={contratoSeleccionado} periodoSugerido={periodoSugerido} />
      ) : codigoSeleccionado ? (
        <p className="text-sm text-red-600">No se encontró el contrato seleccionado.</p>
      ) : (
        <p className="text-sm text-brand-500">Seleccioná un contrato para empezar.</p>
      )}
    </div>
  );
}
