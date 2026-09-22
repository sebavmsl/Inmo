"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { verificarConflicto } from "@/lib/concurrencia/queries";

export interface DatosPropiedad {
  aliasPropiedad: string;
  calle: string;
  numero: string;
  departamento: string;
  propietario: string;
  ciudad: string;
  provincia: string;
  tipo: string;
  nis: string;
  cuentaGas: string;
  finca: string;
  cuentaOoss: string;
  nroPadron: string;
  grupo: string | null; // texto libre para gastos compartidos (ver DESIGN_LOG.md Módulo 7)
  /** Ver 0018_rendicion_expensas_flag.sql — feature nueva de v2, sin equivalente en v1. */
  expensasAdministradaPorPropietario: boolean;
}

export interface PropiedadEditable {
  id: number;
  aliasPropiedad: string;
  calle: string;
  numero: string;
  departamento: string | null;
  propietario: string;
  ciudad: string | null;
  provincia: string | null;
  tipo: string | null;
  nis: string | null;
  cuentaGas: string | null;
  finca: string | null;
  cuentaOoss: string | null;
  nroPadron: string | null;
  grupo: string | null;
  expensasAdministradaPorPropietario: boolean;
  updatedAt: string;
}

/** RLS (0001_v2_auth_setup.sql) ya restringe por empresa — no hace falta filtrar acá. */
export async function listarPropiedades(): Promise<PropiedadEditable[]> {
  await requirePermisoAction("auxiliares");
  const supabase = await createClient();
  const { data } = await supabase.from("propiedades").select("*").order("alias_propiedad");
  return (data ?? []).map((p) => ({
    id: p.id,
    aliasPropiedad: p.alias_propiedad,
    calle: p.calle,
    numero: p.numero,
    departamento: p.departamento,
    propietario: p.propietario,
    ciudad: p.ciudad,
    provincia: p.provincia,
    tipo: p.tipo,
    nis: p.nis,
    cuentaGas: p.cuenta_gas,
    finca: p.finca,
    cuentaOoss: p.cuenta_ooss,
    nroPadron: p.nro_padron,
    grupo: p.grupo,
    expensasAdministradaPorPropietario: p.expensas_administrada_por_propietario,
    updatedAt: p.updated_at,
  }));
}

export interface InquilinoEditable {
  id: number;
  dni: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  email: string | null;
  updatedAt: string;
}

export async function listarInquilinos(): Promise<InquilinoEditable[]> {
  await requirePermisoAction("auxiliares");
  const supabase = await createClient();
  const { data } = await supabase.from("inquilinos").select("*").order("apellidos");
  return (data ?? []).map((i) => ({
    id: i.id,
    dni: i.dni,
    nombres: i.nombres,
    apellidos: i.apellidos,
    telefono: i.telefono,
    email: i.email,
    updatedAt: i.updated_at,
  }));
}

export async function crearPropiedad(datos: DatosPropiedad): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("auxiliares");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { error } = await supabase.from("propiedades").insert({
    empresa_id: perfil.empresaId,
    alias_propiedad: datos.aliasPropiedad,
    calle: datos.calle,
    numero: datos.numero,
    departamento: datos.departamento || null,
    propietario: datos.propietario,
    ciudad: datos.ciudad || null,
    provincia: datos.provincia || null,
    tipo: datos.tipo || null,
    nis: datos.nis || null,
    cuenta_gas: datos.cuentaGas || null,
    finca: datos.finca || null,
    cuenta_ooss: datos.cuentaOoss || null,
    nro_padron: datos.nroPadron || null,
    grupo: datos.grupo,
    expensas_administrada_por_propietario: datos.expensasAdministradaPorPropietario,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}

/**
 * Edición completa de propiedad — a diferencia de v1 (ver
 * 0017_auxiliares_completo.sql), acá SÍ se puede tocar el propietario y
 * las 8 columnas extendidas, no solo alias/calle/número/depto/grupo.
 * Protegido con optimistic locking (Módulo transversal "Ediciones
 * simultáneas").
 */
export async function actualizarPropiedad(datos: {
  id: number;
  aliasPropiedad: string;
  calle: string;
  numero: string;
  departamento: string;
  propietario: string;
  ciudad: string;
  provincia: string;
  tipo: string;
  nis: string;
  cuentaGas: string;
  finca: string;
  cuentaOoss: string;
  nroPadron: string;
  grupo: string | null;
  expensasAdministradaPorPropietario: boolean;
  updatedAtEsperado: string;
}): Promise<{ ok: boolean; error?: string; conflicto?: boolean }> {
  await requirePermisoAction("auxiliares");

  const conflicto = await verificarConflicto("propiedades", String(datos.id), datos.updatedAtEsperado);
  if (conflicto.hayConflicto) {
    return { ok: false, conflicto: true, error: "Alguien más guardó cambios sobre esta propiedad mientras la editabas. Actualizá y volvé a intentar." };
  }

  const supabase = await createClient();
  const { error } = await supabase
    .from("propiedades")
    .update({
      alias_propiedad: datos.aliasPropiedad,
      calle: datos.calle,
      numero: datos.numero,
      departamento: datos.departamento || null,
      propietario: datos.propietario,
      ciudad: datos.ciudad || null,
      provincia: datos.provincia || null,
      tipo: datos.tipo || null,
      nis: datos.nis || null,
      cuenta_gas: datos.cuentaGas || null,
      finca: datos.finca || null,
      cuenta_ooss: datos.cuentaOoss || null,
      nro_padron: datos.nroPadron || null,
      grupo: datos.grupo,
      expensas_administrada_por_propietario: datos.expensasAdministradaPorPropietario,
    })
    .eq("id", datos.id);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}

/**
 * Alta o actualización de un grupo/edificio: asigna el mismo `grupo` a
 * varias propiedades de una sola vez (puerto de la subpestaña
 * "🏢 Nuevo Edificio/Grupo" de app.py).
 */
export async function asignarGrupo(nombreGrupo: string, propiedadIds: number[]): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("auxiliares");
  if (!nombreGrupo.trim()) return { ok: false, error: "Ingresá un nombre para el grupo." };
  if (propiedadIds.length < 2) return { ok: false, error: "Seleccioná al menos 2 propiedades." };
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const supabase = await createClient();
  const { error } = await supabase
    .from("propiedades")
    .update({ grupo: nombreGrupo.trim() })
    .eq("empresa_id", perfil.empresaId)
    .in("id", propiedadIds);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}

export async function crearInquilino(datos: {
  dni: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  email: string;
}): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("auxiliares");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { error } = await supabase.from("inquilinos").insert({
    empresa_id: perfil.empresaId,
    dni: datos.dni,
    nombres: datos.nombres,
    apellidos: datos.apellidos,
    telefono: datos.telefono,
    email: datos.email,
  });

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}

/**
 * Edición de inquilino. `confirmoCambioDni` es una segunda confirmación
 * explícita del cliente cuando el DNI cambia — hallazgo de esta sesión:
 * `contratos.dni_inquilino` referencia este DNI por texto (no hay FK en
 * la base real), así que cambiarlo puede desvincular en silencio los
 * contratos ya cargados de este inquilino. v1 no avisaba nada de esto.
 */
export async function actualizarInquilino(datos: {
  id: number;
  dni: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  email: string;
  confirmoCambioDni: boolean;
  updatedAtEsperado: string;
}): Promise<{ ok: boolean; error?: string; conflicto?: boolean; requiereConfirmacionDni?: boolean }> {
  await requirePermisoAction("auxiliares");

  const conflicto = await verificarConflicto("inquilinos", String(datos.id), datos.updatedAtEsperado);
  if (conflicto.hayConflicto) {
    return { ok: false, conflicto: true, error: "Alguien más guardó cambios sobre este inquilino mientras lo editabas. Actualizá y volvé a intentar." };
  }

  const supabase = await createClient();

  const { data: actual } = await supabase.from("inquilinos").select("dni").eq("id", datos.id).maybeSingle();
  if (actual && actual.dni !== datos.dni && !datos.confirmoCambioDni) {
    return {
      ok: false,
      requiereConfirmacionDni: true,
      error: "Este cambio de DNI puede desvincular contratos ya cargados con el DNI anterior. Confirmá para continuar.",
    };
  }

  const { error } = await supabase
    .from("inquilinos")
    .update({
      dni: datos.dni,
      nombres: datos.nombres,
      apellidos: datos.apellidos,
      telefono: datos.telefono,
      email: datos.email,
    })
    .eq("id", datos.id);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/auxiliares");
  return { ok: true };
}
