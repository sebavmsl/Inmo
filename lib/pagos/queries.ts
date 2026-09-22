import { createClient } from "@/lib/supabase/server";
import { calcularValorActualizado } from "@/lib/indices/calculo";
import type { IndiceActualizacion } from "@/lib/types/database.types";

export interface ContratoParaPago {
  codigo: string;
  aliasPropiedad: string;
  dniInquilino: string;
  nombreInquilino: string;
  telefonoInquilino: string | null;
  indice: IndiceActualizacion;
  honorariosPct: number;
  saldoActual: number;
  alquilerSugerido: number;
  // Últimos valores conocidos, para precargar los inputs
  ultimosConceptos: {
    expensas: number;
    edesal: number;
    gas: number;
    municipalidad: number;
    cochera: number;
    ooss: number;
    impInmobiliario: number;
  };
  honorarios: { totalPactado: number; cuotasPactadas: number; cuotasPagadas: number; sugeridaPorCuota: number };
  garantia: { totalPactado: number; cuotasPactadas: number; cuotasPagadas: number; sugeridaPorCuota: number };
}

/**
 * Puerto de la selección de contrato en Módulo 4: recalcula el índice
 * EN VIVO (decisión explícita del usuario, igual que v1) — distinto del
 * motor bulk de Módulo 3, que solo mira "prox_actualizacion este mes".
 * Acá la elegibilidad es "meses desde la última actualización aplicada"
 * (ver DESIGN_LOG.md).
 */
export async function getContratoParaPago(codigo: string, empresaFiltro?: number | null): Promise<ContratoParaPago | null> {
  const supabase = await createClient();

  let query = supabase
    .from("contratos")
    .select(
      "codigo, alias_propiedad, dni_inquilino, indice, honorarios, saldo_actual, monto_inicial, inicio_contrato, act_contrato, alquiler, alquiler_calculado, alquiler_calculado_fecha, honorarios_pagados_base, cuotas_honorarios_pagadas_base, garantia_pagada_base, cuotas_deposito_pagadas_base, monto_honorarios, cuota_honorarios, monto_garantia, cuotas_deposito"
    )
    .eq("codigo", codigo)
    .eq("estado", "Activo");
  // Defensa en profundidad para superadmin (bypassea RLS): sin esto,
  // podría ver/operar el contrato de OTRA empresa con solo cambiar el
  // ?contrato= de la URL, sin que tenga nada que ver con la empresa
  // elegida en el selector global.
  if (empresaFiltro !== undefined) {
    query = empresaFiltro === null ? query.is("empresa_id", null) : query.eq("empresa_id", empresaFiltro);
  }
  const { data: contrato, error } = await query.single();

  if (error || !contrato) return null;

  const { data: inquilino } = await supabase
    .from("inquilinos")
    .select("nombres, apellidos, telefono")
    .eq("dni", contrato.dni_inquilino)
    .single();

  // Recalcular índice en vivo si corresponde (ICL/IPC/UVA, no "Otro")
  let alquilerSugerido = contrato.alquiler_calculado ?? contrato.alquiler ?? contrato.monto_inicial ?? 0;
  if (["ICL", "IPC", "UVA"].includes(contrato.indice)) {
    // contratos.act_contrato ya guarda la frecuencia directamente en
    // meses (1, 2, 3, 4, 6, 12, 24 — confirmado contra app.py, línea
    // ~2559: "opciones_meses"). NO es un enum de texto como se asumió
    // originalmente ("frecuencia_actualizacion" no existe en la base real).
    const frecuenciaMeses = contrato.act_contrato ?? 6;
    try {
      const valor = await calcularValorActualizado(
        contrato.indice as IndiceActualizacion,
        contrato.monto_inicial,
        new Date(contrato.inicio_contrato),
        frecuenciaMeses
      );
      if (valor !== null) {
        alquilerSugerido = valor;
        await supabase
          .from("contratos")
          .update({ alquiler_calculado: valor, alquiler_calculado_fecha: new Date().toISOString().slice(0, 10) })
          .eq("codigo", codigo);
      }
    } catch {
      // Silencioso, igual que v1 — se usa el valor anterior si falla la fuente externa
    }
  }

  // Último pago conocido, para precargar conceptos (expensas, gas, etc.)
  const { data: ultimoPago } = await supabase
    .from("pagos_historial")
    .select("monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera, monto_ooss, monto_imp_inmobiliario")
    .eq("codigo_contrato", codigo)
    .order("id", { ascending: false })
    .limit(1)
    .maybeSingle();

  // Total pagado hasta ahora de honorarios/garantía = base + suma del ledger
  const { data: sumaPagos } = await supabase
    .from("pagos_historial")
    .select("monto_honorarios, monto_garantia")
    .eq("codigo_contrato", codigo);

  const sumHonorarios = (sumaPagos ?? []).reduce((acc, p) => acc + (p.monto_honorarios || 0), 0);
  const sumGarantia = (sumaPagos ?? []).reduce((acc, p) => acc + (p.monto_garantia || 0), 0);
  const cuotasHonorariosPagadas =
    (contrato.cuotas_honorarios_pagadas_base ?? 0) + (sumaPagos ?? []).filter((p) => p.monto_honorarios > 0).length;
  const cuotasGarantiaPagadas =
    (contrato.cuotas_deposito_pagadas_base ?? 0) + (sumaPagos ?? []).filter((p) => p.monto_garantia > 0).length;

  const honorariosTotal = (contrato.honorarios_pagados_base ?? 0) + sumHonorarios;
  const garantiaTotal = (contrato.garantia_pagada_base ?? 0) + sumGarantia;

  // Puerto exacto de la lógica de v1 (líneas 3636-3645, 3684-3685): si el
  // total pactado es NULL en la base, se usa monto_inicial como default —
  // NO significa "sin honorarios/garantía pactados". Un valor explícito
  // (incluido 0) siempre se respeta tal cual.
  const honorariosPactado = contrato.monto_honorarios ?? contrato.monto_inicial ?? 0;
  const honorariosCuotasPactadas = Math.max(1, contrato.cuota_honorarios || 0) || 1;
  const garantiaPactado = contrato.monto_garantia ?? contrato.monto_inicial ?? 0;
  const garantiaCuotasPactadas = Math.max(1, contrato.cuotas_deposito || 0) || 1;

  return {
    codigo: contrato.codigo,
    aliasPropiedad: contrato.alias_propiedad,
    dniInquilino: contrato.dni_inquilino,
    nombreInquilino: `${inquilino?.nombres ?? ""} ${inquilino?.apellidos ?? ""}`.trim(),
    telefonoInquilino: inquilino?.telefono ?? null,
    indice: contrato.indice,
    honorariosPct: contrato.honorarios ?? 7,
    saldoActual: contrato.saldo_actual ?? 0,
    alquilerSugerido,
    ultimosConceptos: {
      expensas: ultimoPago?.monto_expensas ?? 0,
      edesal: ultimoPago?.monto_edesal ?? 0,
      gas: ultimoPago?.monto_gas ?? 0,
      municipalidad: ultimoPago?.monto_municipalidad ?? 0,
      cochera: ultimoPago?.monto_cochera ?? 0,
      ooss: ultimoPago?.monto_ooss ?? 0,
      impInmobiliario: ultimoPago?.monto_imp_inmobiliario ?? 0,
    },
    honorarios: {
      totalPactado: honorariosPactado,
      cuotasPactadas: honorariosCuotasPactadas,
      cuotasPagadas: cuotasHonorariosPagadas,
      sugeridaPorCuota: sugerirCuota(honorariosPactado, honorariosCuotasPactadas, honorariosTotal),
    },
    garantia: {
      totalPactado: garantiaPactado,
      cuotasPactadas: garantiaCuotasPactadas,
      cuotasPagadas: cuotasGarantiaPagadas,
      sugeridaPorCuota: sugerirCuota(garantiaPactado, garantiaCuotasPactadas, garantiaTotal),
    },
  };
}

/** Cuota sugerida = total ÷ cuotas, capada por el saldo restante si es la última. */
function sugerirCuota(totalPactado: number, cuotasPactadas: number, yaAbonado: number): number {
  if (cuotasPactadas <= 0) return 0;
  const porCuota = totalPactado / cuotasPactadas;
  const restante = totalPactado - yaAbonado;
  return Math.max(0, Math.min(porCuota, restante));
}

/** Lista liviana de contratos activos, para el <select> de la pantalla de Pagos. */
export async function getContratosActivosParaSelector(
  empresaFiltro?: number | null
): Promise<{ codigo: string; aliasPropiedad: string; inquilino: string }[]> {
  const supabase = await createClient();
  let query = supabase.from("contratos").select("codigo, alias_propiedad, dni_inquilino").eq("estado", "Activo").order("alias_propiedad");
  if (empresaFiltro !== undefined) {
    query = empresaFiltro === null ? query.is("empresa_id", null) : query.eq("empresa_id", empresaFiltro);
  }
  const { data: contratos, error } = await query;
  if (error || !contratos) return [];

  const dnis = Array.from(new Set(contratos.map((c) => c.dni_inquilino)));
  const { data: inquilinos } = await supabase.from("inquilinos").select("dni, nombres, apellidos").in("dni", dnis);
  const porDni = new Map((inquilinos ?? []).map((i) => [i.dni, i]));

  return contratos.map((c) => {
    const i = porDni.get(c.dni_inquilino);
    return {
      codigo: c.codigo,
      aliasPropiedad: c.alias_propiedad,
      inquilino: `${i?.apellidos ?? ""}, ${i?.nombres ?? ""}`,
    };
  });
}
