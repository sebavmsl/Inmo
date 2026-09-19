import { createClient } from "@/lib/supabase/server";
import type { FilaPlanilla, UrgenciaFila } from "@/lib/planilla/types";

/** 'YYYY-MM' del mes actual, para planilla_verificaciones y para clasificar urgencia. */
export function periodoActual(): string {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Clasifica la urgencia de una fila, mismo criterio de colores que v1:
 * amarillo (actualizar este mes) / celeste (mes próximo) / rojo (RENOVAR:
 * la próxima actualización cae después del fin del contrato) / normal.
 * Réplica del criterio ya usado en lib/dashboard/metrics.ts, adaptado a
 * clasificación por fila en vez de alertas agregadas.
 */
function clasificarUrgencia(finContrato: string | null, proxActualizacion: string | null): UrgenciaFila {
  if (!proxActualizacion) return "normal";

  const hoy = new Date();
  const mesActual = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  const mesProximo = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 1);
  const prox = new Date(proxActualizacion);
  const proxMes = new Date(prox.getFullYear(), prox.getMonth(), 1);

  if (finContrato) {
    const fin = new Date(finContrato);
    if (prox > fin) return "renovar"; // la próxima actualización cae después de que termina el contrato
  }

  if (proxMes.getTime() === mesActual.getTime()) return "actualizar_este_mes";
  if (proxMes.getTime() === mesProximo.getTime()) return "actualizar_mes_proximo";
  return "normal";
}

export async function getCobranzasDelMes(propietarioFiltro?: string): Promise<FilaPlanilla[]> {
  const supabase = await createClient();
  const periodo = periodoActual();

  // 1. Propiedades (con filtro de propietario si corresponde — mismo
  //    patrón de 3 queries que ya usamos en el Dashboard, ver ese archivo
  //    para la explicación de por qué no usamos embeds de PostgREST).
  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario, calle, numero");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
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
