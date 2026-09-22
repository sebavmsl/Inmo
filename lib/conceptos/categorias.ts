/**
 * Categorización transversal de conceptos de pago — módulo nuevo de esta
 * sesión, sin equivalente en v1. Fuente única de verdad para qué
 * categoría le corresponde a cada columna `monto_*` de `pagos_historial`.
 *
 * Antes (hallazgo de esta sesión), cada módulo que necesitaba un total
 * "Servicios" lo recalculaba por su cuenta con su propia lista
 * hardcodeada de columnas (Historial de Pagos y Rendición a
 * Propietarios tenían la MISMA cuenta duplicada en dos archivos
 * distintos, con riesgo real de desincronizarse si mañana cambia el
 * criterio). Acá vive una sola vez.
 *
 * Alcance deliberado: esto clasifica los conceptos de UN PAGO
 * (`pagos_historial`), no las categorías libres que el usuario tipea al
 * cargar un gasto de propiedad (`gastos_propiedades.categoria`, Módulo
 * 2/7 — Reparación, Impuestos, etc.) — son dos ejes distintos, no se
 * mezclan.
 *
 * Fija (no configurable por empresa) — decisión de esta sesión: el
 * usuario no mostró preferencia por una pantalla de administración
 * nueva, y un mapeo fijo es más simple de mantener y mostrar de forma
 * consistente en todos lados. Si más adelante hace falta que cada
 * empresa lo pueda editar, este archivo es el único lugar a convertir
 * en una tabla de configuración.
 */

export type CategoriaConcepto =
  | "ingreso-base"
  | "expensas"
  | "servicio"
  | "tasa"
  | "impuesto"
  | "comisión"
  | "depósito"
  | "otro";

export const CATEGORIAS_CONCEPTO: CategoriaConcepto[] = [
  "ingreso-base",
  "expensas",
  "servicio",
  "tasa",
  "impuesto",
  "comisión",
  "depósito",
  "otro",
];

export const LABEL_CATEGORIA: Record<CategoriaConcepto, string> = {
  "ingreso-base": "Ingreso base",
  expensas: "Expensas",
  servicio: "Servicios",
  tasa: "Tasas",
  impuesto: "Impuestos",
  comisión: "Comisión",
  depósito: "Depósito",
  otro: "Otro",
};

export interface ConceptoPago {
  /** Nombre del campo en `pagos_historial`, SIN el prefijo `monto_`. */
  campo: string;
  label: string;
  categoria: CategoriaConcepto;
}

/**
 * Tabla confirmada con el usuario (conversación de esta sesión):
 * Alquiler/Cochera → ingreso-base · Expensas → expensas · Luz/Gas/OO.SS.
 * → servicio · Municipalidad → tasa · Imp. Inmobiliario → impuesto ·
 * Comisión agencia + Honorarios de gestión → comisión · Garantía →
 * depósito · Concepto extra → otro.
 */
export const CONCEPTOS_PAGO: ConceptoPago[] = [
  { campo: "alquiler", label: "Alquiler", categoria: "ingreso-base" },
  { campo: "cochera", label: "Cochera", categoria: "ingreso-base" },
  { campo: "expensas", label: "Expensas", categoria: "expensas" },
  { campo: "edesal", label: "Luz (EDESAL)", categoria: "servicio" },
  { campo: "gas", label: "Gas", categoria: "servicio" },
  { campo: "ooss", label: "OO.SS.", categoria: "servicio" },
  { campo: "municipalidad", label: "Municipalidad", categoria: "tasa" },
  { campo: "imp_inmobiliario", label: "Impuesto Inmobiliario", categoria: "impuesto" },
  { campo: "gasto_admin", label: "Comisión agencia", categoria: "comisión" },
  { campo: "honorarios", label: "Honorarios de gestión", categoria: "comisión" },
  { campo: "garantia", label: "Garantía", categoria: "depósito" },
  { campo: "concepto_extra", label: "Concepto extra", categoria: "otro" },
];

/**
 * Suma los conceptos de una categoría dentro de un objeto de montos
 * (claves = `campo` de CONCEPTOS_PAGO, ej. `{ edesal: 100, gas: 200 }`).
 * Falta un campo o viene null/undefined → cuenta como 0.
 */
export function sumarCategoria(montos: Partial<Record<string, number | null | undefined>>, categoria: CategoriaConcepto): number {
  return CONCEPTOS_PAGO.filter((c) => c.categoria === categoria).reduce((acc, c) => acc + (montos[c.campo] ?? 0), 0);
}

/** Totales de TODAS las categorías a la vez, para no llamar sumarCategoria() ocho veces seguidas. */
export function totalesPorCategoria(montos: Partial<Record<string, number | null | undefined>>): Record<CategoriaConcepto, number> {
  const totales = {} as Record<CategoriaConcepto, number>;
  for (const categoria of CATEGORIAS_CONCEPTO) totales[categoria] = sumarCategoria(montos, categoria);
  return totales;
}

/** Forma mínima de una fila de `pagos_historial` (columnas `monto_*` reales) que necesita montosDesdeFilaPago(). */
export interface MontosPagoHistorial {
  monto_alquiler?: number | null;
  monto_cochera?: number | null;
  monto_expensas?: number | null;
  monto_edesal?: number | null;
  monto_gas?: number | null;
  monto_ooss?: number | null;
  monto_municipalidad?: number | null;
  monto_imp_inmobiliario?: number | null;
  monto_gasto_admin?: number | null;
  monto_honorarios?: number | null;
  monto_garantia?: number | null;
  monto_concepto_extra?: number | null;
}

/**
 * Adapta una fila de `pagos_historial` (columnas `monto_*`, nombre real
 * de la base) al formato de claves cortas que esperan sumarCategoria()/
 * totalesPorCategoria() — para no repetir este mapeo en cada módulo que
 * lo necesita (Historial de Pagos, Rendición a Propietarios).
 */
export function montosDesdeFilaPago(fila: MontosPagoHistorial): Partial<Record<string, number | null | undefined>> {
  return {
    alquiler: fila.monto_alquiler,
    cochera: fila.monto_cochera,
    expensas: fila.monto_expensas,
    edesal: fila.monto_edesal,
    gas: fila.monto_gas,
    ooss: fila.monto_ooss,
    municipalidad: fila.monto_municipalidad,
    imp_inmobiliario: fila.monto_imp_inmobiliario,
    gasto_admin: fila.monto_gasto_admin,
    honorarios: fila.monto_honorarios,
    garantia: fila.monto_garantia,
    concepto_extra: fila.monto_concepto_extra,
  };
}
