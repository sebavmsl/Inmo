import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export interface InquilinoContrato {
  empresaId: number;
  nombreEmpresa: string;
  dni: string;
  nombreCompleto: string;
  codigoContrato: string;
  aliasPropiedad: string;
}

/**
 * A diferencia de usuarios_central (Módulo 1), acá una persona puede
 * tener VARIAS filas en `inquilinos` — la misma persona real puede ser
 * inquilino de más de una empresa (ver docs/DESIGN_LOG.md, "caso de
 * borde de multi-tenencia"). Se devuelven todos sus contratos activos,
 * de cualquier empresa, y la UI deja elegir cuál ver si hay más de uno.
 */
export async function getInquilinoContratos(): Promise<InquilinoContrato[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return [];

  const { data: filasInquilino } = await supabase
    .from("inquilinos")
    .select("dni, nombres, apellidos, empresa_id")
    .eq("auth_user_id", user.id);

  if (!filasInquilino || filasInquilino.length === 0) return [];

  const resultado: InquilinoContrato[] = [];

  for (const fila of filasInquilino) {
    const { data: empresa } = await supabase
      .from("empresas")
      .select("nombre_comercial")
      .eq("id", fila.empresa_id)
      .single();

    const { data: contratos } = await supabase
      .from("contratos")
      .select("codigo, alias_propiedad")
      .eq("dni_inquilino", fila.dni)
      .eq("empresa_id", fila.empresa_id)
      .eq("estado", "Activo");

    for (const c of contratos ?? []) {
      resultado.push({
        empresaId: fila.empresa_id,
        nombreEmpresa: empresa?.nombre_comercial ?? "",
        dni: fila.dni,
        nombreCompleto: `${fila.nombres} ${fila.apellidos}`.trim(),
        codigoContrato: c.codigo,
        aliasPropiedad: c.alias_propiedad,
      });
    }
  }

  return resultado;
}

/** Guardia de sesión para el grupo de rutas (inquilino) — redirige si no hay sesión válida como inquilino. */
export async function requireInquilinoContratos(): Promise<InquilinoContrato[]> {
  const contratos = await getInquilinoContratos();
  if (contratos.length === 0) redirect("/portal/login");
  return contratos;
}
