import { createClient } from "@/lib/supabase/server";

export type EstadoComprobante = "pendiente" | "aprobado" | "rechazado";
export type EstadoReclamo = "abierto" | "en_progreso" | "resuelto";

export interface FilaComprobante {
  id: number;
  fechaSubida: string;
  codigoContrato: string;
  propiedad: string;
  inquilino: string;
  montoDeclarado: number | null;
  estado: EstadoComprobante;
  revisadoPor: string | null;
  fechaRevision: string | null;
  /** URL firmada de corta duración (10 min) para ver/descargar el archivo subido — null si Storage falló al generarla. */
  urlArchivo: string | null;
}

export interface FilaReclamo {
  id: number;
  fecha: string;
  codigoContrato: string;
  propiedad: string;
  propiedadId: number | null;
  inquilino: string;
  descripcion: string;
  estado: EstadoReclamo;
  respuestaStaff: string | null;
  gastoId: number | null;
  gastoDescripcion: string | null;
  gastoMonto: number | null;
}

export interface GastoReciente {
  id: number;
  fecha: string;
  descripcion: string;
  monto: number;
}

/** Contexto de contratos+inquilinos, para no repetir el mismo join en getComprobantes/getReclamos. */
async function mapaContratosInquilinos(codigosContrato: string[]) {
  const supabase = await createClient();
  const codigos = Array.from(new Set(codigosContrato));
  if (codigos.length === 0) return { porCodigo: new Map(), porDni: new Map() };

  const { data: contratos } = await supabase
    .from("contratos")
    .select("codigo, alias_propiedad, dni_inquilino")
    .in("codigo", codigos);

  const dnis = Array.from(new Set((contratos ?? []).map((c) => c.dni_inquilino)));
  const { data: inquilinos } =
    dnis.length > 0 ? await supabase.from("inquilinos").select("dni, nombres, apellidos").in("dni", dnis) : { data: [] };

  const porDni = new Map((inquilinos ?? []).map((i) => [i.dni, `${i.nombres} ${i.apellidos}`.trim()]));
  const porCodigo = new Map((contratos ?? []).map((c) => [c.codigo, c]));

  return { porCodigo, porDni };
}

/**
 * Bandeja de comprobantes subidos por inquilinos (Módulo 9, ver
 * docs/DESIGN_LOG.md) — pendientes de revisión por el staff. NO carga un
 * pago real: aprobar acá solo cambia el estado, el staff sigue teniendo
 * que registrar el cobro por Pagos si corresponde.
 */
export async function getComprobantes(estadoFiltro?: EstadoComprobante): Promise<FilaComprobante[]> {
  const supabase = await createClient();

  let query = supabase
    .from("comprobantes_inquilino")
    .select("id, codigo_contrato, storage_path, monto_declarado, fecha_subida, estado, revisado_por, fecha_revision")
    .order("fecha_subida", { ascending: false });
  if (estadoFiltro) query = query.eq("estado", estadoFiltro);

  const { data: comprobantes, error } = await query;
  if (error) throw new Error(`[Portal Inquilino] Error cargando comprobantes: ${error.message}`);
  if (!comprobantes || comprobantes.length === 0) return [];

  const { porCodigo, porDni } = await mapaContratosInquilinos(comprobantes.map((c) => c.codigo_contrato));

  const filas = await Promise.all(
    comprobantes.map(async (c): Promise<FilaComprobante> => {
      const contrato = porCodigo.get(c.codigo_contrato);
      const { data: firmada } = await supabase.storage.from("comprobantes-inquilino").createSignedUrl(c.storage_path, 600);

      return {
        id: c.id,
        fechaSubida: c.fecha_subida,
        codigoContrato: c.codigo_contrato,
        propiedad: contrato?.alias_propiedad ?? c.codigo_contrato,
        inquilino: contrato ? porDni.get(contrato.dni_inquilino) ?? "" : "",
        montoDeclarado: c.monto_declarado,
        estado: c.estado,
        revisadoPor: c.revisado_por,
        fechaRevision: c.fecha_revision,
        urlArchivo: firmada?.signedUrl ?? null,
      };
    })
  );

  return filas;
}

/**
 * Bandeja de reclamos de inquilinos, con el gasto vinculado (si lo hay)
 * para trazabilidad en los dos sentidos (ver DESIGN_LOG.md).
 */
export async function getReclamos(estadoFiltro?: EstadoReclamo): Promise<FilaReclamo[]> {
  const supabase = await createClient();

  let query = supabase
    .from("reclamos_inquilino")
    .select("id, codigo_contrato, descripcion, estado, fecha, respuesta_staff, gasto_id")
    .order("fecha", { ascending: false });
  if (estadoFiltro) query = query.eq("estado", estadoFiltro);

  const { data: reclamos, error } = await query;
  if (error) throw new Error(`[Portal Inquilino] Error cargando reclamos: ${error.message}`);
  if (!reclamos || reclamos.length === 0) return [];

  const { porCodigo, porDni } = await mapaContratosInquilinos(reclamos.map((r) => r.codigo_contrato));

  const aliasesInvolucrados = Array.from(new Set(Array.from(porCodigo.values()).map((c) => c.alias_propiedad)));
  const { data: propiedades } =
    aliasesInvolucrados.length > 0
      ? await supabase.from("propiedades").select("id, alias_propiedad").in("alias_propiedad", aliasesInvolucrados)
      : { data: [] };
  const propiedadIdPorAlias = new Map((propiedades ?? []).map((p) => [p.alias_propiedad, p.id]));

  const gastoIds = reclamos.map((r) => r.gasto_id).filter((id): id is number => id !== null);
  const { data: gastos } =
    gastoIds.length > 0
      ? await supabase.from("gastos_propiedades").select("id, descripcion, monto").in("id", gastoIds)
      : { data: [] };
  const gastoPorId = new Map((gastos ?? []).map((g) => [g.id, g]));

  return reclamos.map((r): FilaReclamo => {
    const contrato = porCodigo.get(r.codigo_contrato);
    const gasto = r.gasto_id ? gastoPorId.get(r.gasto_id) : undefined;

    return {
      id: r.id,
      fecha: r.fecha,
      codigoContrato: r.codigo_contrato,
      propiedad: contrato?.alias_propiedad ?? r.codigo_contrato,
      propiedadId: contrato ? propiedadIdPorAlias.get(contrato.alias_propiedad) ?? null : null,
      inquilino: contrato ? porDni.get(contrato.dni_inquilino) ?? "" : "",
      descripcion: r.descripcion,
      estado: r.estado,
      respuestaStaff: r.respuesta_staff,
      gastoId: r.gasto_id,
      gastoDescripcion: gasto?.descripcion ?? null,
      gastoMonto: gasto?.monto ?? null,
    };
  });
}

/** Últimos gastos de una propiedad, para el selector "vincular a un gasto ya cargado" del reclamo. */
export async function getGastosRecientesPropiedad(propiedadId: number): Promise<GastoReciente[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("gastos_propiedades")
    .select("id, fecha, descripcion, monto")
    .eq("propiedad_id", propiedadId)
    .order("fecha", { ascending: false })
    .limit(15);
  if (error) throw new Error(`[Portal Inquilino] Error cargando gastos recientes: ${error.message}`);
  return data ?? [];
}
