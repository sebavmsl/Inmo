/**
 * Forma de cada fila que devuelve la query de contratos activos usada por
 * el Dashboard — puerto directo de `_cached_contratos_activos()` en
 * app.py (líneas 1474-1487).
 */
export interface ContratoActivoDashboardRow {
  codigo: string;
  alias_propiedad: string;
  inquilino: string; // "Apellidos, Nombres" ya concatenado en la query
  estado: string;
  fin_contrato: string | null; // "YYYY-MM-DD" o "DD/MM/YYYY"
  prox_actualizacion: string | null; // "YYYY-MM-DD" o "DD/MM/YYYY"
  alquiler: number | null;
  mes_contrato: number | null;
  /**
   * Frecuencia de actualización. En v1 conviven dos formatos históricos:
   * un número (meses) o una etiqueta de texto ("Mensual", "Trimestral",
   * etc.) — ver FRECUENCIA_A_MESES en metrics.ts.
   */
  act_contrato: number | string | null;
}
