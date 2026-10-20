"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { bloqueadoPorActualizacionPendiente } from "@/lib/carga/validaciones";
import { verificarConflicto } from "@/lib/concurrencia/queries";
import {
  listarContratosEditables,
  listarOpcionesAlta,
  obtenerDatosRenovacion,
  type ContratoEditable,
} from "@/lib/carga/queries";
import { armarPrevisualizacion, armarRegistroAlta, resumenAlta, validarAlta, validarMeses } from "@/lib/carga/armadoAlta";
import { hoyArgentina, previsualizarAltaContrato } from "@/lib/carga/mesesTranscurridos";
import { claveHoy, fechaHoraPythonAhora } from "@/lib/fechas";
import type { DatosAltaContrato, MesConfirmado, OpcionesAlta, PrevisualizacionAlta } from "@/lib/carga/tipos";
import type { CargosContrato, ServiciosContrato } from "@/lib/carga/tipos";
import {
  aISO,
  calcularDuracion,
  calcularProxActualizacion,
  leerFechaISO,
  textoServiciosPython,
  tieneDeposito,
  tienePagare,
} from "@/lib/carga/calculoContrato";
import type { IndiceActualizacion } from "@/lib/types/database.types";

export async function listarContratos(): Promise<ContratoEditable[]> {
  const perfil = await requirePermisoAction("carga");
  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;
  const empresaFiltro = perfil.rol === "superadmin" ? perfil.empresaId : undefined;
  return listarContratosEditables(propietarioFiltro, empresaFiltro);
}

/** Listas de propiedades e inquilinos de la empresa, para el alta. */
export async function opcionesAlta(): Promise<OpcionesAlta> {
  const perfil = await requirePermisoAction("carga");
  if (!perfil.empresaId) return { propiedades: [], inquilinos: [] };
  return listarOpcionesAlta(perfil.empresaId);
}

/** Datos precargados para renovar un contrato (botón "Renovar"). */
export async function datosRenovacion(codigo: string): Promise<{ ok: boolean; datos?: DatosAltaContrato; error?: string }> {
  const perfil = await requirePermisoAction("carga");
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };
  const datos = await obtenerDatosRenovacion(codigo, perfil.empresaId);
  if (!datos) return { ok: false, error: "No se encontró el contrato a renovar." };
  return { ok: true, datos };
}

/**
 * Paso 1 del alta: valida y calcula duración, mes actual, próxima
 * actualización, alquiler vigente y los meses ya transcurridos (con el
 * índice de cada ciclo). No guarda nada.
 */
export async function previsualizarAlta(
  datos: DatosAltaContrato
): Promise<{ ok: boolean; previsualizacion?: PrevisualizacionAlta; error?: string }> {
  await requirePermisoAction("carga");
  const error = validarAlta(datos);
  if (error) return { ok: false, error };
  try {
    return { ok: true, previsualizacion: await previsualizarAltaContrato(datos) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Error calculando los meses del contrato." };
  }
}

/**
 * Paso 2 del alta: guarda todo en una sola transacción con
 * `crear_contrato_v2` (migración 0023): cierra el contrato activo
 * anterior de la propiedad (Finalizado o Cancelado, con motivo
 * "renovacion"), crea el contrato con el código de la secuencia (igual que
 * Python) y registra los meses transcurridos en pagos_historial.
 *
 * Se vuelve a calcular la previsualización acá (duración, mes actual,
 * próxima actualización y cantidad de meses) para no confiar en fechas
 * calculadas en el navegador; los montos de cada mes son los que el
 * usuario confirmó en pantalla.
 */
export async function crearContrato(
  datos: DatosAltaContrato,
  meses: MesConfirmado[],
  alquilerVigenteConfirmado: number
): Promise<{ ok: boolean; codigo?: string; cerrados?: { codigo: string; estado: string }[]; error?: string }> {
  const perfil = await requirePermisoAction("carga");
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const errorDatos = validarAlta(datos);
  if (errorDatos) return { ok: false, error: errorDatos };

  const r = resumenAlta(datos, hoyArgentina());
  const errorMeses = validarMeses(meses, r.cantidadMesesPasados, claveHoy());
  if (errorMeses) return { ok: false, error: errorMeses };
  if (!(alquilerVigenteConfirmado > 0)) return { ok: false, error: "El alquiler vigente tiene que ser mayor a 0." };

  // Previsualización sin consultar índices: alcanza para las fechas; el
  // alquiler vigente es el que el usuario confirmó.
  const prev = armarPrevisualizacion(datos, r, new Map());
  const registro = armarRegistroAlta({ ...datos, alquilerVigente: alquilerVigenteConfirmado }, prev, meses, {
    empresaId: perfil.empresaId,
    username: perfil.username,
    ahora: { iso: claveHoy(), hora: fechaHoraPythonAhora().slice(11) },
  });

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("crear_contrato_v2", {
    p_contrato: registro.contrato,
    p_meses: registro.meses,
  });
  if (error) {
    const sinFuncion = /crear_contrato_v2/.test(error.message) && /(not find|does not exist|no existe)/i.test(error.message);
    return {
      ok: false,
      error: sinFuncion
        ? "Falta aplicar la migración 0023 en Supabase (función crear_contrato_v2)."
        : `Error al crear el contrato: ${error.message}`,
    };
  }
  const res = (data ?? {}) as { ok?: boolean; codigo?: number; cerrados?: { codigo: number; estado: string }[]; error?: string };
  if (!res.ok) return { ok: false, error: res.error ?? "No se pudo crear el contrato." };

  revalidatePath("/carga");
  revalidatePath("/planilla");
  revalidatePath("/pagos");
  return {
    ok: true,
    codigo: String(res.codigo ?? ""),
    cerrados: (res.cerrados ?? []).map((c) => ({ codigo: String(c.codigo), estado: c.estado })),
  };
}

export interface DatosEditarContrato {
  estado: string;
  dniInquilino: string;
  fechaInicio: string;
  finContrato: string | null;
  diaVencimiento: number;
  /** Dato original del alta: se puede corregir, con aviso en pantalla. */
  montoInicial: number;
  indice: IndiceActualizacion;
  frecuenciaMeses: number;
  honorariosPct: number;
  montoHonorarios: number | null;
  cuotaHonorarios: number;
  tipoGarantia: string;
  montoGarantia: number | null;
  cuotasDeposito: number;
  montoPagare: number;
  servicios: ServiciosContrato;
  cargos: CargosContrato;
  cargoGeneralServicios: number;
  cochera: number | null; // cochera del mes (vigente)
  cocheraMontoInicial: number;
  cocheraActualizaConIndice: boolean;
}

/**
 * Edición de un contrato existente — corrige datos mal cargados. No es
 * una renovación (para eso está "Renovar", que crea un contrato nuevo).
 *
 * No toca `alquiler` (vigente, lo mantienen Pagos y la actualización de
 * índices de Planilla) ni el saldo. Si cambian las fechas o la
 * frecuencia, recalcula duración y próxima actualización con la fórmula
 * de Python. Reescribe `servicios` con el formato de Python porque Python
 * lee de ahí el alquiler vigente y a cargo de quién va el impuesto
 * inmobiliario.
 *
 * Dos capas de protección antes de guardar: optimistic locking (Módulo
 * transversal "Ediciones simultáneas") y el bloqueo por actualización
 * de índice pendiente (ver lib/carga/validaciones.ts).
 */
export async function editarContrato(
  codigo: string,
  datos: DatosEditarContrato,
  updatedAtEsperado: string
): Promise<{ ok: boolean; error?: string; conflicto?: boolean; bloqueado?: boolean }> {
  const perfil = await requirePermisoAction("carga");
  const supabase = await createClient();
  if (!perfil.empresaId) return { ok: false, error: "Usuario sin empresa asociada." };

  const conflicto = await verificarConflicto("contratos", codigo, updatedAtEsperado);
  if (conflicto.hayConflicto) {
    return { ok: false, conflicto: true, error: "Alguien más guardó cambios sobre este contrato mientras lo editabas. Actualizá y volvé a intentar." };
  }

  const { data: actual } = await supabase
    .from("contratos")
    .select("fin_contrato, prox_actualizacion, inicio_contrato, act_contrato, alquiler, monto_inicial, calc_duracion")
    .eq("codigo", codigo)
    .eq("empresa_id", perfil.empresaId)
    .maybeSingle();
  if (!actual) return { ok: false, error: "No se encontró el contrato." };

  const { bloqueado, motivo } = bloqueadoPorActualizacionPendiente({
    estado: datos.estado,
    finContrato: actual.fin_contrato ?? null,
    proxActualizacion: actual.prox_actualizacion ?? null,
  });
  if (bloqueado) return { ok: false, bloqueado: true, error: motivo ?? "Edición bloqueada." };

  const inicio = leerFechaISO(datos.fechaInicio);
  const fin = leerFechaISO(datos.finContrato);
  if (!inicio || !fin) return { ok: false, error: "Las fechas de inicio y fin tienen que ser válidas." };
  if (aISO(fin) <= aISO(inicio)) return { ok: false, error: "La fecha de fin tiene que ser posterior a la de inicio." };
  if (!Number.isInteger(datos.diaVencimiento) || datos.diaVencimiento < 1 || datos.diaVencimiento > 31)
    return { ok: false, error: "El día de vencimiento tiene que estar entre 1 y 31." };
  if (!(datos.montoInicial > 0)) return { ok: false, error: "El monto inicial tiene que ser mayor a 0." };

  // Duración y próxima actualización: se recalculan solo si cambió algo que las afecta.
  const cambiaronFechas =
    datos.fechaInicio !== actual.inicio_contrato ||
    datos.finContrato !== actual.fin_contrato ||
    datos.frecuenciaMeses !== actual.act_contrato;
  const recalculo = cambiaronFechas
    ? {
        calc_duracion: calcularDuracion(inicio, fin),
        prox_actualizacion: aISO(calcularProxActualizacion(inicio, fin, datos.frecuenciaMeses, hoyArgentina())),
        mes_actualizacion_contrato: datos.frecuenciaMeses > 0 ? datos.frecuenciaMeses : 1,
      }
    : {};

  const alquilerVigente = actual.alquiler && actual.alquiler > 0 ? actual.alquiler : datos.montoInicial;
  const deposito = tieneDeposito(datos.tipoGarantia) ? (datos.montoGarantia ?? 0) : 0;

  const { error } = await supabase
    .from("contratos")
    .update({
      estado: datos.estado,
      dni_inquilino: datos.dniInquilino,
      inicio_contrato: datos.fechaInicio,
      fin_contrato: datos.finContrato,
      ...recalculo,
      dia_vencimiento: datos.diaVencimiento,
      monto_inicial: datos.montoInicial,
      indice: datos.indice,
      act_contrato: datos.frecuenciaMeses,
      honorarios: datos.honorariosPct,
      monto_honorarios: datos.montoHonorarios,
      cuota_honorarios: datos.cuotaHonorarios,
      tipo_de_garantie: datos.tipoGarantia,
      monto_garantia: deposito,
      cuotas_deposito: datos.cuotasDeposito,
      monto_pagare: tienePagare(datos.tipoGarantia) ? datos.montoPagare : 0,
      expensas: datos.servicios.expensas,
      edesal: datos.servicios.edesal,
      gas: datos.servicios.gas,
      municipalidad: datos.servicios.municipalidad,
      ooss: datos.servicios.ooss,
      imp_inmobiliario: datos.servicios.impInmobiliario,
      cargo_electricidad: datos.cargos.electricidad,
      cargo_gas: datos.cargos.gas,
      cargo_municipalidad: datos.cargos.municipalidad,
      cargo_ooss: datos.cargos.ooss,
      cargo_expensas: datos.cargos.expensas,
      cargo_imp_inmobiliario: datos.cargos.impInmobiliario,
      cargo_general_servicios: datos.cargoGeneralServicios,
      cochera: datos.cochera,
      cochera_monto_inicial: datos.cocheraMontoInicial,
      cochera_actualiza_con_indice: datos.cocheraActualizaConIndice && ["ICL", "IPC", "UVA"].includes(datos.indice),
      servicios: textoServiciosPython({ alquilerVigente, cargos: datos.cargos }),
    })
    .eq("codigo", codigo)
    .eq("empresa_id", perfil.empresaId);

  if (error) {
    const sinColumnas = /dia_vencimiento|cochera_monto_inicial|cargo_general_servicios|monto_pagare/.test(error.message);
    return { ok: false, error: sinColumnas ? "Falta aplicar la migración 0023 en Supabase." : error.message };
  }
  revalidatePath("/carga");
  revalidatePath("/planilla");
  return { ok: true };
}
