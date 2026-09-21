import type { TipoPago } from "@/lib/types/database.types";

/**
 * Fórmula única de cuenta corriente para los 3 tipos de pago — ver
 * docs/DESIGN_LOG.md, sección "Saldo de contratos — MODELO FINAL".
 *
 *   saldo_nuevo = saldo_actual_antes + cargos_de_este_movimiento − pagado_de_este_movimiento
 *
 * Sin max(0, ...): un sobrepago queda como saldo negativo (a favor del
 * inquilino) — a diferencia de v1, que lo perdía sin dejar rastro.
 */
export interface ConceptosPago {
  alquiler: number;
  expensas: number;
  edesal: number;
  gas: number;
  municipalidad: number;
  cochera: number;
  ooss: number;
  impInmobiliario: number;
  honorarios: number; // fee de gestión en cuotas — no es la comisión
  garantia: number;
  conceptoExtra: number;
}

export function sumaConceptos(c: ConceptosPago): number {
  return (
    c.alquiler +
    c.expensas +
    c.edesal +
    c.gas +
    c.municipalidad +
    c.cochera +
    c.ooss +
    c.impInmobiliario +
    c.honorarios +
    c.garantia +
    c.conceptoExtra
  );
}

export interface ResultadoCalculoSaldo {
  cargos: number;
  saldoNuevo: number;
  gastoAdmin: number; // comisión real, calculada automáticamente (ver Módulo 6)
}

/**
 * Calcula el saldo nuevo y la comisión automática de administración.
 * `montoAbonado` es lo efectivamente cobrado en ESTE movimiento (para
 * Corrección, siempre 0 — la diferencia va en `cargos`, no acá).
 */
export function calcularSaldoNuevo(params: {
  tipoPago: TipoPago;
  saldoActualAntes: number;
  conceptos: ConceptosPago | null; // null para Complemento/Corrección (no hay cargos nuevos)
  diferenciaCorreccion: number | null; // solo para Corrección, puede ser negativo
  montoAbonado: number; // ignorado para Corrección — ver nota abajo
  honorariosPct: number; // contratos.honorarios (% de comisión — nombre real de la columna), para calcular monto_gasto_admin
}): ResultadoCalculoSaldo {
  const { tipoPago, saldoActualAntes, conceptos, diferenciaCorreccion, honorariosPct } = params;

  let cargos: number;
  let pagado: number;
  // Monto que efectivamente "entra" en la fórmula de comisión (ver abajo)
  // y en pagos_historial.monto_abonado — para Corrección es la propia
  // diferencia, NO el parámetro `montoAbonado` (evita que el caller tenga
  // que pasar el mismo valor en dos parámetros distintos sin que nada lo
  // obligue a mantenerlos sincronizados).
  let montoParaComision: number;

  switch (tipoPago) {
    case "Normal":
      cargos = conceptos ? sumaConceptos(conceptos) : 0;
      pagado = params.montoAbonado;
      montoParaComision = params.montoAbonado;
      break;
    case "Complemento":
      cargos = 0; // ya se cargó con el pago Normal de ese período
      pagado = params.montoAbonado;
      montoParaComision = params.montoAbonado;
      break;
    case "Corrección":
      cargos = diferenciaCorreccion ?? 0;
      pagado = 0; // la diferencia ya captura el efecto neto, no hay "monto abonado" separado
      montoParaComision = diferenciaCorreccion ?? 0;
      break;
  }

  const saldoNuevo = saldoActualAntes + cargos - pagado;

  // Comisión automática — puerto de app.py línea 4345, aplica a los 3
  // tipos de pago por igual (ver DESIGN_LOG.md: si una Corrección
  // devuelve plata, la comisión también se revierte proporcionalmente).
  const gastoAdmin = Math.round(((montoParaComision * honorariosPct) / 100) * 100) / 100;

  return { cargos, saldoNuevo, gastoAdmin };
}
