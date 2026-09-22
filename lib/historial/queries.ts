import { createClient } from "@/lib/supabase/server";
import { nombreMesAnio } from "@/lib/format";
import { sumarCategoria, montosDesdeFilaPago } from "@/lib/conceptos/categorias";

export interface FilaHistorial {
  nroComprobante: string | null;
  fecha: string;
  periodo: string; // "Mes N de M", relativo al contrato
  mesAnio: string; // "Septiembre 2026" — calculado a partir de periodo + inicio_contrato (ver calcularMesAnio)
  codigoContrato: string;
  propiedad: string; // alias_propiedad
  domicilio: string; // calle + número (+ ", Dto: X"), vía join a propiedades — antes faltaba
  inquilino: string;
  tipoPago: string;
  montoAlquiler: number;
  montoExpensas: number;
  montoEdesal: number;
  montoGas: number;
  montoMunicipalidad: number;
  montoOoss: number;
  montoImpInmobiliario: number;
  /**
   * Suma SOLO de la categoría "servicio" (Luz + Gas + OO.SS.) — ver
   * lib/conceptos/categorias.ts. CORRECCIÓN de esta sesión: antes esta
   * columna también sumaba Municipalidad e Imp. Inmobiliario, que ahora
   * son sus propias categorías ("tasa" e "impuesto") — ya se muestran
   * como columnas propias, así que sumarlas de nuevo acá era además un
   * doble conteo visual. El total categorizado sigue disponible con
   * `sumarCategoria()` para cualquier categoría, incluida "tasa"/"impuesto"
   * (hoy 1 a 1 con montoMunicipalidad/montoImpInmobiliario).
   */
  montoServicios: number;
  montoCochera: number;
  montoHonorarios: number;
  montoGarantia: number;
  montoConceptoExtra: number;
  conceptoExtraDesc: string | null;
  montoAbonado: number;
  saldoPendiente: number; // cuenta corriente, ver DESIGN_LOG.md
  retencionAgencia: number; // FIX Módulo 6 (ver DESIGN_LOG.md): antes hardcodeado en $0
  metodoPago: string | null;
  cotizacionUsd: number | null;
  alquilerUsd: number;
  cocheraUsd: number;
  impInmobiliarioUsd: number;
  retencionAgenciaUsd: number; // FIX de esta sesión: v1 también la hardcodea en 0 (línea 1638) — mismo bug que la versión en $, nunca corregido ahí
  registradoPor: string | null; // para el filtro "por usuario" del Reporte de Cobros
}

/**
 * "Mes N de M" + fecha de inicio del contrato → "Septiembre 2026".
 * Puerto de `_calcular_mes_anio` (app.py líneas 4753-4772).
 */
function calcularMesAnio(periodo: string, inicioContrato: string | null): string {
  const match = /^Mes\s+(\d+)\s+de\s+\d+/.exec(periodo);
  if (!match || !inicioContrato) return "";
  const numMesContrato = Number(match[1]);
  const inicio = new Date(inicioContrato);
  if (Number.isNaN(inicio.getTime())) return "";
  const fecha = new Date(inicio.getFullYear(), inicio.getMonth() + (numMesContrato - 1), inicio.getDate());
  return nombreMesAnio(fecha);
}

function aUsd(valorArs: number, cotizacion: number | null): number {
  return cotizacion && cotizacion > 0 ? valorArs / cotizacion : 0;
}

/**
 * Puerto de `_cached_historial_pagos()` (app.py líneas 1587-1645), con el
 * fix de "Retención Agencia" ya aplicado (ver DESIGN_LOG.md, Módulo 6:
 * se lee `pagos_historial.monto_gasto_admin`, que Módulo 4 ya calcula y
 * guarda en cada pago — sin join ni recálculo).
 *
 * Ampliación de esta sesión respecto a la primera versión de este
 * archivo: se agregan el resto de columnas de v1 que faltaban
 * (desglose de servicios, honorarios/garantía/concepto extra, USD por
 * concepto, domicilio vía join a propiedades, mes/año calculado) para
 * que la tabla y el Reporte de Cobros tengan paridad completa con v1.
 */
export async function getHistorialPagos(propietarioFiltro?: string): Promise<FilaHistorial[]> {
  const supabase = await createClient();

  let propiedadesQuery = supabase.from("propiedades").select("alias_propiedad, propietario, calle, numero, departamento");
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  const { data: propiedades, error: errProp } = await propiedadesQuery;
  if (errProp) throw new Error(`[Historial] Error cargando propiedades: ${errProp.message}`);

  const aliasPermitidos = propietarioFiltro ? new Set((propiedades ?? []).map((p) => p.alias_propiedad)) : null;
  if (aliasPermitidos && aliasPermitidos.size === 0) return [];

  // Domicilio por alias — igual criterio que v1 (calle + número + ", Dto: X"
  // si corresponde). `propiedades` ya trae el universo correcto para este
  // pedido (todas, o solo las del propietario filtrado).
  const domicilioPorAlias = new Map(
    (propiedades ?? []).map((p) => [
      p.alias_propiedad,
      `${p.calle} ${p.numero}${p.departamento ? `, Dto: ${p.departamento}` : ""}`.trim(),
    ])
  );

  let pagosQuery = supabase
    .from("pagos_historial")
    .select(
      `nro_comprobante, fecha, periodo, codigo_contrato, propiedad, inquilino, tipo_pago,
       monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_ooss,
       monto_imp_inmobiliario, monto_cochera, monto_honorarios, monto_garantia,
       monto_concepto_extra, concepto_extra_desc, monto_abonado, saldo_pendiente,
       monto_gasto_admin, metodo_pago, cotizacion_usd, registrado_por`
    )
    .order("fecha", { ascending: false });

  if (aliasPermitidos) pagosQuery = pagosQuery.in("propiedad", Array.from(aliasPermitidos));

  const { data: pagos, error } = await pagosQuery;
  if (error) throw new Error(`[Historial] Error cargando pagos: ${error.message}`);
  if (!pagos || pagos.length === 0) return [];

  // inicio_contrato de cada contrato involucrado, para calcular MES/AÑO.
  const codigosContrato = Array.from(new Set(pagos.map((p) => p.codigo_contrato)));
  const { data: contratos } = await supabase.from("contratos").select("codigo, inicio_contrato").in("codigo", codigosContrato);
  const inicioPorCodigo = new Map((contratos ?? []).map((c) => [c.codigo, c.inicio_contrato]));

  return pagos.map((p): FilaHistorial => {
    const montoServicios = sumarCategoria(montosDesdeFilaPago(p), "servicio");
    const retencionAgencia = p.monto_gasto_admin ?? 0;
    const cotizacionUsd = p.cotizacion_usd;

    return {
      nroComprobante: p.nro_comprobante,
      fecha: p.fecha,
      periodo: p.periodo,
      mesAnio: calcularMesAnio(p.periodo, inicioPorCodigo.get(p.codigo_contrato) ?? null),
      codigoContrato: p.codigo_contrato,
      propiedad: p.propiedad,
      domicilio: domicilioPorAlias.get(p.propiedad) ?? p.propiedad,
      inquilino: p.inquilino,
      tipoPago: p.tipo_pago,
      montoAlquiler: p.monto_alquiler ?? 0,
      montoExpensas: p.monto_expensas ?? 0,
      montoEdesal: p.monto_edesal ?? 0,
      montoGas: p.monto_gas ?? 0,
      montoMunicipalidad: p.monto_municipalidad ?? 0,
      montoOoss: p.monto_ooss ?? 0,
      montoImpInmobiliario: p.monto_imp_inmobiliario ?? 0,
      montoServicios,
      montoCochera: p.monto_cochera ?? 0,
      montoHonorarios: p.monto_honorarios ?? 0,
      montoGarantia: p.monto_garantia ?? 0,
      montoConceptoExtra: p.monto_concepto_extra ?? 0,
      conceptoExtraDesc: p.concepto_extra_desc,
      montoAbonado: p.monto_abonado ?? 0,
      saldoPendiente: p.saldo_pendiente ?? 0,
      retencionAgencia,
      metodoPago: p.metodo_pago,
      cotizacionUsd,
      alquilerUsd: aUsd(p.monto_alquiler ?? 0, cotizacionUsd),
      cocheraUsd: aUsd(p.monto_cochera ?? 0, cotizacionUsd),
      impInmobiliarioUsd: aUsd(p.monto_imp_inmobiliario ?? 0, cotizacionUsd),
      retencionAgenciaUsd: aUsd(retencionAgencia, cotizacionUsd),
      registradoPor: p.registrado_por,
    };
  });
}
