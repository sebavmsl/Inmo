import { createClient } from "@/lib/supabase/server";
import type { FilaPlanilla } from "@/lib/planilla/types";
import { clasificarUrgencia } from "@/lib/contratos/urgencia";

/** 'YYYY-MM' del mes actual, para planilla_verificaciones y para clasificar urgencia. */
export function periodoActual(): string {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * @param empresaFiltro Filtro explícito por empresa, solo relevante para
 *   superadmin (los demás roles ya quedan acotados a su propia empresa por
 *   RLS, así que pasan `undefined` = sin filtro adicional acá). superadmin
 *   no tiene `empresa_id` propio, así que por defecto (ver page.tsx) se le
 *   pasa `null` acá para mostrarle los contratos "huérfanos" (sin empresa
 *   asignada) en vez de mezclar todas las inmobiliarias en una sola tabla;
 *   eligiendo una empresa del desplegable se pasa su id numérico.
 */
export async function getCobranzasDelMes(
  propietarioFiltro?: string,
  empresaFiltro?: number | null
): Promise<FilaPlanilla[]> {
  const supabase = await createClient();
  const periodo = periodoActual();

  // 1. Propiedades (con filtro de propietario si corresponde — mismo
  //    patrón de 3 queries que ya usamos en el Dashboard, ver ese archivo
  //    para la explicación de por qué no usamos embeds de PostgREST).
  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario, calle, numero");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  if (empresaFiltro !== undefined) {
    propiedadesQuery =
      empresaFiltro === null ? propiedadesQuery.is("empresa_id", null) : propiedadesQuery.eq("empresa_id", empresaFiltro);
  }
  const { data: propiedades, error: errProp } = await propiedadesQuery;
  if (errProp) throw new Error(`[Planilla] Error cargando propiedades: ${errProp.message}`);

  const aliasPermitidos = propietarioFiltro ? new Set((propiedades ?? []).map((p) => p.alias_propiedad)) : null;
  if (aliasPermitidos && aliasPermitidos.size === 0) return [];
  const propiedadPorAlias = new Map((propiedades ?? []).map((p) => [p.alias_propiedad, p]));

  // 2. Contratos activos + finalizados-por-vencimiento-no-archivados
  let contratosQuery = supabase
    .from("contratos")
    .select(
      "codigo, alias_propiedad, dni_inquilino, fin_contrato, prox_actualizacion, indice, alquiler_calculado, alquiler, monto_inicial, cochera, saldo_actual, estado, finalizado_por, archivado"
    )
    .or("estado.eq.Activo,and(finalizado_por.eq.auto_vencimiento,archivado.eq.false)");

  if (aliasPermitidos) contratosQuery = contratosQuery.in("alias_propiedad", Array.from(aliasPermitidos));
  if (empresaFiltro !== undefined) {
    contratosQuery =
      empresaFiltro === null ? contratosQuery.is("empresa_id", null) : contratosQuery.eq("empresa_id", empresaFiltro);
  }

  const { data: contratos, error: errCont } = await contratosQuery;
  if (errCont) throw new Error(`[Planilla] Error cargando contratos: ${errCont.message}`);
  if (!contratos || contratos.length === 0) return [];

  // 3. Inquilinos
  const dnis = Array.from(new Set(contratos.map((c) => c.dni_inquilino).filter(Boolean)));
  const { data: inquilinos, error: errInq } = await supabase
    .from("inquilinos")
    .select("dni, apellidos, nombres, telefono")
    .in("dni", dnis);
  if (errInq) throw new Error(`[Planilla] Error cargando inquilinos: ${errInq.message}`);
  const inquilinoPorDni = new Map((inquilinos ?? []).map((i) => [i.dni, i]));

  // 4. Verificaciones de este período (checkbox + expensas ad-hoc)
  const codigos = contratos.map((c) => c.codigo);
  const { data: verificaciones, error: errVer } = await supabase
    .from("planilla_verificaciones")
    .select("codigo_contrato, verificado, expensas_adhoc")
    .eq("periodo", periodo)
    .in("codigo_contrato", codigos);
  if (errVer) throw new Error(`[Planilla] Error cargando verificaciones: ${errVer.message}`);
  const verifPorCodigo = new Map((verificaciones ?? []).map((v) => [v.codigo_contrato, v]));

  return contratos.map((c): FilaPlanilla => {
    const inquilino = inquilinoPorDni.get(c.dni_inquilino);
    const verif = verifPorCodigo.get(c.codigo);
    const alquilerMostrar = c.alquiler_calculado ?? c.alquiler ?? c.monto_inicial ?? 0;

    return {
      codigo: c.codigo,
      aliasPropiedad: c.alias_propiedad,
      inquilino: `${inquilino?.apellidos ?? ""}, ${inquilino?.nombres ?? ""}`,
      telefono: inquilino?.telefono ?? null,
      finContrato: c.fin_contrato,
      proxActualizacion: c.prox_actualizacion,
      indice: c.indice,
      alquilerMostrar,
      cochera: c.cochera ?? null,
      saldoActual: c.saldo_actual ?? 0,
      pagado: (c.saldo_actual ?? 0) <= 0, // ver DESIGN_LOG.md "¿Pagado? — REDEFINIDO"
      urgencia: c.estado === "Activo" ? clasificarUrgencia(c.fin_contrato, c.prox_actualizacion) : "normal",
      archivado: c.archivado ?? false,
      estadoVencido: c.finalizado_por === "auto_vencimiento" && !c.archivado,
      verificado: verif?.verificado ?? false,
      expensasAdhoc: verif?.expensas_adhoc ?? null,
    };
  });
}
