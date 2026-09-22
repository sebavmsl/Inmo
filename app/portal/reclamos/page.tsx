import { requireInquilinoContratos } from "@/lib/inquilino/session";
import { FormularioReclamo } from "@/components/portal/FormularioReclamo";

export default async function ReclamosPage() {
  const contratos = await requireInquilinoContratos();
  return <FormularioReclamo contratos={contratos} />;
}
