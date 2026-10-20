/**
 * Armado del alta de un contrato (Entrega 2 — V2.018): resumen, meses ya
 * transcurridos y registro final para `crear_contrato_v2`.
 *
 * Funciones puras (sin base ni red): reciben los montos del alquiler por
 * ciclo de actualización ya consultados (ver lib/carga/mesesTranscurridos.ts).
 */
import {
  aISO,
  aTextoAR,
  calcularDuracion,
  calcularMesActual,
  calcularProxActualizacion,
  cicloDelMes,
  cuotaDelMes,
  estadoGarantiaPython,
  leerFechaISO,
  nombreMesCalendario,
  redondear2,
  textoServiciosPython,
  tieneDeposito,
  tienePagare,
  vencimientoDelMes,
  type FechaPartes,
} from "@/lib/carga/calculoContrato";
import type { DatosAltaContrato, MesCalculado, MesConfirmado, PrevisualizacionAlta } from "@/lib/carga/tipos";

export const INDICES_AUTOMATICOS = ["ICL", "IPC", "UVA"];

export function actualizaConIndice(datos: Pick<DatosAltaContrato, "indice" | "frecuenciaMeses">): boolean {
  return INDICES_AUTOMATICOS.includes(datos.indice) && datos.frecuenciaMeses > 0;
}

function noNegativo(n: number): boolean {
  return Number.isFinite(n) && n >= 0;
}

/** Devuelve el primer error de validación, o null si está todo bien. */
export function validarAlta(d: DatosAltaContrato): string | null {
  if (!d.aliasPropiedad) return "Elegí la propiedad.";
  if (!d.dniInquilino) return "Elegí el inquilino.";
  const inicio = leerFechaISO(d.fechaInicio);
  const fin = leerFechaISO(d.finContrato);
  if (!inicio) return "La fecha de inicio no es válida.";
  if (!fin) return "La fecha de fin no es válida.";
  if (aISO(fin) <= aISO(inicio)) return "La fecha de fin tiene que ser posterior a la de inicio.";
  if (calcularDuracion(inicio, fin) < 1) return "El contrato tiene que durar al menos un mes.";
  if (!Number.isInteger(d.diaVencimiento) || d.diaVencimiento < 1 || d.diaVencimiento > 31)
    return "El día de vencimiento tiene que estar entre 1 y 31.";
  if (!(d.montoInicial > 0)) return "El monto inicial tiene que ser mayor a 0.";
  if (!noNegativo(d.honorariosPct) || d.honorariosPct > 100) return "El % de comisión tiene que estar entre 0 y 100.";
  if (!noNegativo(d.montoHonorarios)) return "El total de honorarios no puede ser negativo.";
  if (!Number.isInteger(d.cuotaHonorarios) || d.cuotaHonorarios < 1) return "Las cuotas de honorarios tienen que ser al menos 1.";
  if (!noNegativo(d.montoGarantia)) return "El depósito no puede ser negativo.";
  if (!Number.isInteger(d.cuotasDeposito) || d.cuotasDeposito < 1) return "Las cuotas del depósito tienen que ser al menos 1.";
  if (!noNegativo(d.montoPagare)) return "El pagaré no puede ser negativo.";
  if (!noNegativo(d.cochera)) return "La cochera no puede ser negativa.";
  if (!noNegativo(d.cargoGeneralServicios)) return "El cargo general de servicios no puede ser negativo.";
  for (const v of Object.values(d.servicios)) if (!noNegativo(v)) return "Los montos de servicios no pueden ser negativos.";
  if (d.alquilerVigente !== null && !(d.alquilerVigente > 0)) return "El alquiler vigente tiene que ser mayor a 0.";
  return null;
}

export interface ResumenAlta {
  inicio: FechaPartes;
  fin: FechaPartes;
  duracion: number;
  mesActual: number;
  prox: FechaPartes;
  necesitaRenovacion: boolean;
  /** Meses a registrar: del 1 al anterior al actual, sin pasar la duración. */
  cantidadMesesPasados: number;
  /** Ciclos de actualización cuyo monto hay que consultar (incluye el del mes actual). */
  ciclos: number[];
}

export function resumenAlta(d: DatosAltaContrato, hoy: FechaPartes): ResumenAlta {
  const inicio = leerFechaISO(d.fechaInicio)!;
  const fin = leerFechaISO(d.finContrato)!;
  const duracion = calcularDuracion(inicio, fin);
  const mesActual = calcularMesActual(inicio, hoy);
  const prox = calcularProxActualizacion(inicio, fin, d.frecuenciaMeses, hoy);
  const necesitaRenovacion = d.frecuenciaMeses > 0 && aISO(prox) > aISO(fin);
  const cantidadMesesPasados = Math.max(0, Math.min(mesActual - 1, duracion));
  const ciclos = new Set<number>();
  if (actualizaConIndice(d)) {
    const ultimo = Math.min(mesActual, Math.max(duracion, 1));
    for (let n = 1; n <= ultimo; n++) {
      const c = cicloDelMes(n, d.frecuenciaMeses);
      if (c > 0) ciclos.add(c);
    }
  }
  return { inicio, fin, duracion, mesActual, prox, necesitaRenovacion, cantidadMesesPasados, ciclos: [...ciclos].sort((a, b) => a - b) };
}

/** Cochera de un mes: con tilde, acompaña al alquiler en la misma proporción. */
function cocheraDelMes(d: DatosAltaContrato, alquiler: number): number {
  if (!d.cocheraActualizaConIndice || !INDICES_AUTOMATICOS.includes(d.indice) || !(d.montoInicial > 0)) return d.cochera;
  return Math.round((d.cochera * alquiler) / d.montoInicial);
}

/**
 * Arma la previsualización: un renglón por mes transcurrido, más el
 * alquiler y la cochera vigentes. `montosPorCiclo` trae el alquiler de
 * cada ciclo de actualización (null si no se pudo consultar el índice).
 */
export function armarPrevisualizacion(
  d: DatosAltaContrato,
  r: ResumenAlta,
  montosPorCiclo: Map<number, number | null>
): PrevisualizacionAlta {
  const avisos: string[] = [];
  const auto = actualizaConIndice(d);

  // Monto de cada ciclo; si un ciclo no se pudo consultar, sigue el último conocido.
  const alquilerDeCiclo = new Map<number, { monto: number; ok: boolean }>();
  alquilerDeCiclo.set(0, { monto: d.montoInicial, ok: true });
  const maxCiclo = r.ciclos.length ? r.ciclos[r.ciclos.length - 1]! : 0;
  const ciclosFallidos: number[] = [];
  for (let c = 1; c <= maxCiclo; c++) {
    const anterior = alquilerDeCiclo.get(c - 1)!;
    const valor = montosPorCiclo.get(c);
    if (valor && valor > 0) alquilerDeCiclo.set(c, { monto: valor, ok: true });
    else {
      alquilerDeCiclo.set(c, { monto: anterior.monto, ok: false });
      ciclosFallidos.push(c);
    }
  }
  if (ciclosFallidos.length) {
    avisos.push(
      `No se pudo consultar el ${d.indice} para ${ciclosFallidos.length === 1 ? "una actualización" : `${ciclosFallidos.length} actualizaciones`}: esos meses usan el último monto conocido (marcados con ⚠️). Corregilos con el ajuste.`
    );
  }
  if (d.indice === "Otro" && d.frecuenciaMeses > 0 && r.mesActual > d.frecuenciaMeses) {
    avisos.push("El índice \"Otro\" no se calcula solo: todos los meses usan el monto inicial. Corregí cada mes con el ajuste y cargá el alquiler vigente.");
  }

  const montoDelMes = (n: number) => (auto ? alquilerDeCiclo.get(cicloDelMes(n, d.frecuenciaMeses)) : undefined) ?? { monto: d.montoInicial, ok: true };

  const deInquilino = (monto: number, cargo: string) => (cargo === "Inquilino" ? monto : 0);
  const s = d.servicios;
  const c = d.cargos;
  const deposito = tieneDeposito(d.tipoGarantia) ? d.montoGarantia : 0;

  const meses: MesCalculado[] = [];
  for (let n = 1; n <= r.cantidadMesesPasados; n++) {
    const { monto: alquiler, ok } = montoDelMes(n);
    const mes: MesCalculado = {
      nro: n,
      periodo: `Mes ${n} de ${r.duracion}`,
      mesCalendario: nombreMesCalendario(r.inicio, n),
      vencimiento: aISO(vencimientoDelMes(r.inicio, n, d.diaVencimiento)),
      alquiler,
      cochera: cocheraDelMes(d, alquiler),
      expensas: deInquilino(s.expensas, c.expensas),
      edesal: deInquilino(s.edesal, c.electricidad),
      gas: deInquilino(s.gas, c.gas),
      municipalidad: deInquilino(s.municipalidad, c.municipalidad),
      ooss: deInquilino(s.ooss, c.ooss),
      impInmobiliario: deInquilino(s.impInmobiliario, c.impInmobiliario),
      cargoGeneral: d.cargoGeneralServicios,
      honorarios: cuotaDelMes(d.montoHonorarios, d.cuotaHonorarios, n),
      garantia: cuotaDelMes(deposito, d.cuotasDeposito, n),
      subtotal: 0,
      indiceOk: ok,
    };
    mes.subtotal = redondear2(
      mes.alquiler + mes.cochera + mes.expensas + mes.edesal + mes.gas + mes.municipalidad + mes.ooss +
        mes.impInmobiliario + mes.cargoGeneral + mes.honorarios + mes.garantia
    );
    meses.push(mes);
  }

  const vigente = montoDelMes(Math.min(r.mesActual, Math.max(r.duracion, 1)));
  if (auto && !vigente.ok && !ciclosFallidos.length) {
    avisos.push("No se pudo consultar el índice del ciclo actual: el alquiler vigente es el último monto conocido.");
  }

  return {
    duracion: r.duracion,
    mesActual: r.mesActual,
    proxActualizacion: aISO(r.prox),
    necesitaRenovacion: r.necesitaRenovacion,
    alquilerVigenteCalculado: vigente.monto,
    cocheraVigente: cocheraDelMes(d, vigente.monto),
    meses,
    avisos,
  };
}

/** Estado inicial de cada mes en la pantalla (decisiones de Carga: Pagado por defecto). */
export function mesConfirmadoPorDefecto(m: MesCalculado, hoyISO: string): MesConfirmado {
  return {
    ...m,
    estado: "Pagado",
    ajuste: 0,
    comision: false,
    pagaAhora: false,
    montoPagado: m.subtotal,
    fechaPago: hoyISO,
    metodoPago: "Transferencia Bancaria",
  };
}

export function totalDelMes(m: MesConfirmado): number {
  return redondear2(m.subtotal + (Number.isFinite(m.ajuste) ? m.ajuste : 0));
}

export function abonadoDelMes(m: MesConfirmado): number {
  if (m.estado === "Pagado") return Math.max(0, totalDelMes(m));
  if (m.pagaAhora) return Math.max(0, redondear2(m.montoPagado));
  return 0;
}

/** Saldo que queda en la cuenta corriente después de todos los meses. */
export function saldoFinal(meses: MesConfirmado[]): number {
  return redondear2(meses.reduce((acc, m) => acc + totalDelMes(m) - abonadoDelMes(m), 0));
}

function fechaHoraRegistro(m: MesConfirmado, ahora: { iso: string; hora: string }): string {
  const venc = leerFechaISO(m.vencimiento)!;
  if (m.estado === "Adeudado" && m.pagaAhora) {
    const f = leerFechaISO(m.fechaPago) ?? leerFechaISO(ahora.iso)!;
    return `${aTextoAR(f)} ${aISO(f) === ahora.iso ? ahora.hora : "12:00"}`;
  }
  return `${aTextoAR(venc)} 00:00`;
}

export function validarMeses(meses: MesConfirmado[], cantidadEsperada: number, hoyISO: string): string | null {
  if (meses.length !== cantidadEsperada) return "La lista de meses no coincide con las fechas del contrato. Volvé a calcular los meses.";
  const nros = new Set(meses.map((m) => m.nro));
  for (let n = 1; n <= cantidadEsperada; n++) if (!nros.has(n)) return "Falta un mes en la lista. Volvé a calcular los meses.";
  for (const m of meses) {
    if (!Number.isFinite(m.ajuste)) return `El ajuste del ${m.periodo} no es un número.`;
    if (m.estado === "Adeudado" && m.pagaAhora) {
      if (!(m.montoPagado > 0)) return `Cargá el monto que paga ahora del ${m.periodo}.`;
      const f = leerFechaISO(m.fechaPago);
      if (!f) return `La fecha de pago del ${m.periodo} no es válida.`;
      if (aISO(f) > hoyISO) return `La fecha de pago del ${m.periodo} no puede ser futura.`;
    }
  }
  return null;
}

/**
 * Registro que recibe `crear_contrato_v2`: columnas del contrato con sus
 * nombres reales, y la lista de meses.
 */
export function armarRegistroAlta(
  d: DatosAltaContrato,
  prev: PrevisualizacionAlta,
  meses: MesConfirmado[],
  extra: { empresaId: number; username: string; ahora: { iso: string; hora: string } }
): { contrato: Record<string, unknown>; meses: Record<string, unknown>[] } {
  const alquilerVigente = d.alquilerVigente ?? prev.alquilerVigenteCalculado;
  const cocheraVigente = cocheraDelMes(d, alquilerVigente);
  const s = d.servicios;
  const c = d.cargos;
  const deInquilino = (monto: number, cargo: string) => (cargo === "Inquilino" ? monto : 0);
  const serviciosTotal = redondear2(
    deInquilino(s.impInmobiliario, c.impInmobiliario) + deInquilino(s.expensas, c.expensas) +
      deInquilino(s.edesal, c.electricidad) + deInquilino(s.gas, c.gas) +
      deInquilino(s.municipalidad, c.municipalidad) + deInquilino(s.ooss, c.ooss) +
      cocheraVigente + d.cargoGeneralServicios
  );
  const deposito = tieneDeposito(d.tipoGarantia) ? d.montoGarantia : 0;
  const honorariosPagados = redondear2(meses.reduce((a, m) => a + m.honorarios, 0));
  const garantiaPagada = redondear2(meses.reduce((a, m) => a + m.garantia, 0));

  const contrato: Record<string, unknown> = {
    empresa_id: extra.empresaId,
    registrado_por: extra.username,
    alias_propiedad: d.aliasPropiedad,
    dni_inquilino: d.dniInquilino,
    estado: d.estado,
    inicio_contrato: d.fechaInicio,
    fin_contrato: d.finContrato,
    calc_duracion: prev.duracion,
    act_contrato: d.frecuenciaMeses,
    indice: d.indice,
    monto_inicial: d.montoInicial,
    alquiler: alquilerVigente,
    prox_actualizacion: prev.proxActualizacion,
    mes_contrato: prev.mesActual,
    mes_actualizacion_contrato: d.frecuenciaMeses > 0 ? d.frecuenciaMeses : 1,
    servicios: textoServiciosPython({ alquilerVigente, cargos: c }),
    honorarios: d.honorariosPct,
    monto_honorarios: d.montoHonorarios,
    cuota_honorarios: d.cuotaHonorarios,
    honorarios_pagados: honorariosPagados,
    cuotas_honorarios_pagadas: meses.filter((m) => m.honorarios > 0).length,
    tipo_de_garantie: d.tipoGarantia,
    monto_garantia: deposito,
    garantia: estadoGarantiaPython(d.tipoGarantia, deposito, garantiaPagada),
    garantia_pagada: garantiaPagada,
    cuotas_deposito: d.cuotasDeposito,
    cuotas_deposito_pagadas: meses.filter((m) => m.garantia > 0).length,
    imp_inmobiliario: s.impInmobiliario,
    expensas: s.expensas,
    edesal: s.edesal,
    gas: s.gas,
    municipalidad: s.municipalidad,
    ooss: s.ooss,
    servicios_total: serviciosTotal,
    cochera: cocheraVigente,
    alquiler_cobrado: alquilerVigente,
    total_pagado: redondear2(alquilerVigente + serviciosTotal),
    cargo_electricidad: c.electricidad,
    cargo_gas: c.gas,
    cargo_municipalidad: c.municipalidad,
    cargo_ooss: c.ooss,
    cargo_expensas: c.expensas,
    cargo_imp_inmobiliario: c.impInmobiliario,
    dia_vencimiento: d.diaVencimiento,
    cochera_monto_inicial: d.cochera,
    cochera_actualiza_con_indice: d.cocheraActualizaConIndice && INDICES_AUTOMATICOS.includes(d.indice),
    cargo_general_servicios: d.cargoGeneralServicios,
    monto_pagare: tienePagare(d.tipoGarantia) ? d.montoPagare : 0,
  };

  const registros = [...meses]
    .sort((a, b) => a.nro - b.nro)
    .map((m) => {
      const abonado = abonadoDelMes(m);
      const comentario =
        m.estado === "Pagado"
          ? "Carga inicial: pagado antes del alta"
          : m.pagaAhora
            ? "Carga inicial: adeudado, pagado al cargar el contrato"
            : "Carga inicial: adeudado";
      return {
        nro: m.nro,
        periodo: m.periodo,
        fecha: fechaHoraRegistro(m, extra.ahora),
        alquiler: m.alquiler,
        expensas: m.expensas,
        edesal: m.edesal,
        gas: m.gas,
        municipalidad: m.municipalidad,
        cochera: m.cochera,
        ooss: m.ooss,
        imp_inmobiliario: m.impInmobiliario,
        honorarios: m.honorarios,
        garantia: m.garantia,
        cargo_general: m.cargoGeneral,
        ajuste: redondear2(m.ajuste),
        abonado,
        comision: m.comision && abonado > 0,
        metodo_pago: m.estado === "Adeudado" && m.pagaAhora ? m.metodoPago : "Carga inicial",
        comentario,
      };
    });

  return { contrato, meses: registros };
}
