import { requireInquilinoContratos } from "@/lib/inquilino/session";
import { FormularioSubirComprobante } from "@/components/portal/FormularioSubirComprobante";

export default async function SubirComprobantePage() {
  const contratos = await requireInquilinoContratos();
  return <FormularioSubirComprobante contratos={contratos} />;
}
