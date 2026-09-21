import { requireSessionProfile } from "@/lib/auth/session";
import { esSoloLectura } from "@/lib/auth/permissions";
import { createClient } from "@/lib/supabase/server";
import { FormularioGasto } from "@/components/gastos/FormularioGasto";

export default async function GastosPage() {
  const perfil = await requireSessionProfile();
  const soloLectura = esSoloLectura(perfil.rol);

  const supabase = await createClient();
  const { data: propiedades } = await supabase
    .from("propiedades")
    .select("id, alias_propiedad, grupo")
    .order("alias_propiedad");

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-brand-900">🔧 Gastos de Propiedades</h1>
      <p className="mb-4 text-sm text-brand-500">{perfil.nombreEmpresa}</p>

      {!soloLectura && (
        <FormularioGasto
          propiedades={(propiedades ?? []).map((p) => ({ id: p.id, aliasPropiedad: p.alias_propiedad, grupo: p.grupo }))}
        />
      )}
    </div>
  );
}
