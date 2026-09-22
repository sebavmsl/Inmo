"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { registrarCotizacionUsada } from "@/lib/cotizacion/queries";
import { getGastosRecientesPropiedad, type EstadoReclamo, type GastoReciente } from "@/lib/portal-inquilino/queries";

const RUTA = "/portal-inquilino";

/**
 * Aprobar/rechazar un comprobante subido por un inquilino (Módulo 9). NO
 * registra ningún pago — ver docs/DESIGN_LOG.md: aprobar acá es solo el
 * visto bueno del staff sobre el archivo/monto declarado; si corresponde
 * cargar el cobro real, se sigue haciendo por el flujo normal de Pagos,
 * con este comprobante como respaldo visual.
 */
export async function revisarComprobante(
  id: number,
  decision: "aprobado" | "rechazado"
): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("portal_inquilino");
  const supabase = await createClient();

  // superadmin bypassea RLS por empresa (auth_rol() = 'superadmin' OR
  // empresa_id = auth_empresa_id()): sin este filtro podría revisar el
  // comprobante de CUALQUIER empresa conociendo/adivinando su id, sin
  // importar cuál tenga elegida en el selector global (Sidebar). Acá se
  // hace cumplir la empresa activa también en escritura por id — mismo
  // criterio que ya se usa para lectura en lib/portal-inquilino/queries.ts.
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  let query = supabase
    .from("comprobantes_inquilino")
    .update({ estado: decision, revisado_por: perfil.username, fecha_revision: new Date().toISOString() })
    .eq("id", id);
  if (empresaFiltro !== undefined) {
    query = empresaFiltro === null ? query.is("empresa_id", null) : query.eq("empresa_id", empresaFiltro);
  }

  const { data, error } = await query.select("id");
  if (error) return { ok: false, error: error.message };
  if (empresaFiltro !== undefined && (!data || data.length === 0)) {
    return { ok: false, error: "El comprobante no pertenece a la empresa activa." };
  }
  revalidatePath(RUTA);
  return { ok: true };
}

/** Actualiza estado + respuesta del staff sobre un reclamo, en un solo guardado. */
export async function actualizarReclamo(
  id: number,
  estado: EstadoReclamo,
  respuestaStaff: string
): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("portal_inquilino");
  const supabase = await createClient();

  // Mismo criterio que revisarComprobante: para superadmin, la empresa
  // activa del selector global también manda en la escritura por id.
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  let query = supabase
    .from("reclamos_inquilino")
    .update({ estado, respuesta_staff: respuestaStaff || null })
    .eq("id", id);
  if (empresaFiltro !== undefined) {
    query = empresaFiltro === null ? query.is("empresa_id", null) : query.eq("empresa_id", empresaFiltro);
  }

  const { data, error } = await query.select("id");
  if (error) return { ok: false, error: error.message };
  if (empresaFiltro !== undefined && (!data || data.length === 0)) {
    return { ok: false, error: "El reclamo no pertenece a la empresa activa." };
  }
  revalidatePath(RUTA);
  return { ok: true };
}

/** Últimos gastos de la propiedad del reclamo, para el selector "vincular a uno ya cargado". */
export async function listarGastosRecientesAction(propiedadId: number): Promise<GastoReciente[]> {
  await requirePermisoAction("portal_inquilino");
  return getGastosRecientesPropiedad(propiedadId);
}

/** Vincula un reclamo a un gasto YA cargado aparte (ver DESIGN_LOG.md, trazabilidad en los dos sentidos). */
export async function vincularGastoAReclamo(reclamoId: number, gastoId: number): Promise<{ ok: boolean; error?: string }> {
  const perfil = await requirePermisoAction("portal_inquilino");
  const supabase = await createClient();

  // Mismo criterio que revisarComprobante/actualizarReclamo.
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  let query = supabase.from("reclamos_inquilino").update({ gasto_id: gastoId }).eq("id", reclamoId);
  if (empresaFiltro !== undefined) {
    query = empresaFiltro === null ? query.is("empresa_id", null) : query.eq("empresa_id", empresaFiltro);
  }

  const { data, error } = await query.select("id");
  if (error) return { ok: false, error: error.message };
  if (empresaFiltro !== undefined && (!data || data.length === 0)) {
    return { ok: false, error: "El reclamo no pertenece a la empresa activa." };
  }
  revalidatePath(RUTA);
  return { ok: true };
}

export interface DatosGastoDesdeReclamo {
  propiedadId: number;
  fecha: string;
  categoria: string;
  descripcion: string;
  monto: number;
  proveedor: string;
  pagadoPor: "Inmobiliaria" | "Propietario" | "Inquilino" | "Otro";
  tipoGasto: string;
  cotizacionUsd: number | null;
}

/**
 * Crea el gasto real que resuelve un reclamo (precarga propiedad, ver
 * DESIGN_LOG.md) y lo vincula en el mismo paso. Si el insert del gasto
 * sale bien pero el vínculo falla, el gasto queda igual creado — mismo
 * criterio de "sin rollback multi-paso" que ya usa crearGasto() para el
 * reparto por grupo (no hay función RPC transaccional para esto).
 */
export async function crearGastoDesdeReclamo(
  reclamoId: number,
  datos: DatosGastoDesdeReclamo
): Promise<{ ok: boolean; error?: string; gastoId?: number }> {
  const perfil = await requirePermisoAction("portal_inquilino");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const { data: gasto, error: errGasto } = await supabase
    .from("gastos_propiedades")
    .insert({
      empresa_id: perfil.empresaId,
      propiedad_id: datos.propiedadId,
      fecha: datos.fecha,
      categoria: datos.categoria,
      descripcion: datos.descripcion,
      monto: datos.monto,
      proveedor: datos.proveedor || null,
      comprobante: null,
      pagado_por: datos.pagadoPor,
      observaciones: null,
      tipo_gasto: datos.tipoGasto,
      cotizacion_usd: datos.cotizacionUsd,
      cobrado: false,
    })
    .select("id")
    .single();

  if (errGasto || !gasto) return { ok: false, error: errGasto?.message ?? "No se pudo crear el gasto." };

  // Mismo criterio que vincularGastoAReclamo: el gasto recién creado
  // queda en la empresa activa de superadmin (empresa_id: perfil.empresaId
  // arriba), pero sin este filtro el vínculo al reclamo podría escribir
  // sobre un reclamo de OTRA empresa si `reclamoId` no fuera de la activa.
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  let queryVinculo = supabase.from("reclamos_inquilino").update({ gasto_id: gasto.id }).eq("id", reclamoId);
  if (empresaFiltro !== undefined) {
    queryVinculo =
      empresaFiltro === null ? queryVinculo.is("empresa_id", null) : queryVinculo.eq("empresa_id", empresaFiltro);
  }
  const { data: vinculado, error: errVinculo } = await queryVinculo.select("id");
  if (errVinculo) {
    return { ok: false, error: `El gasto #${gasto.id} se creó, pero no se pudo vincular al reclamo: ${errVinculo.message}` };
  }
  if (empresaFiltro !== undefined && (!vinculado || vinculado.length === 0)) {
    return {
      ok: false,
      error: `El gasto #${gasto.id} se creó, pero el reclamo no pertenece a la empresa activa: no se pudo vincular.`,
    };
  }

  revalidatePath(RUTA);
  revalidatePath("/gastos");
  await registrarCotizacionUsada(perfil.empresaId, datos.cotizacionUsd);
  return { ok: true, gastoId: gasto.id };
}
