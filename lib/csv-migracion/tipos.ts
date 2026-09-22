/**
 * Migración masiva por CSV (Módulo 10, ver docs/DESIGN_LOG.md) — puerto
 * de "🚀 Importar / Exportar Datos (CSV)" de app.py, subpestaña exclusiva
 * de superadmin dentro de Panel de Gestión.
 *
 * Alcance confirmado con el usuario (sesión actual):
 *   - Se puede IMPORTAR: propiedades, inquilinos, contratos, gastos_propiedades.
 *   - Se puede EXPORTAR (además de las 4 de arriba): pagos_historial, permisos_usuario.
 *     En v1 esas 2 últimas aparecían también como "importables", pero la
 *     importación estaba rota — nunca se les definió el esquema de columnas
 *     esperado (ESQUEMAS_VALIDOS no las incluye, línea 868 de app.py), así
 *     que cualquier CSV rebotaba con "no coincide el esquema". Acá se
 *     resuelve dejándolas directamente como solo-exportables, sin fingir
 *     una importación que en la práctica nunca funcionó.
 */

export const TABLAS_IMPORTABLES = ["propiedades", "inquilinos", "contratos", "gastos_propiedades"] as const;
export type TablaImportable = (typeof TABLAS_IMPORTABLES)[number];

export const TABLAS_EXPORTABLES = [...TABLAS_IMPORTABLES, "pagos_historial", "permisos_usuario"] as const;
export type TablaExportable = (typeof TABLAS_EXPORTABLES)[number];

export const LABEL_TABLA: Record<TablaExportable, string> = {
  propiedades: "Propiedades",
  inquilinos: "Inquilinos",
  contratos: "Contratos",
  gastos_propiedades: "Gastos de Propiedades",
  pagos_historial: "Historial de Pagos",
  permisos_usuario: "Permisos de Usuario",
};

export type TipoColumna = "texto" | "entero" | "decimal" | "fecha" | "booleano";

export interface ColumnaImport {
  /** Encabezado esperado en el CSV — se mantiene el mismo texto que ya usaba v1 (mismas plantillas sirven). */
  encabezado: string;
  /** Columna real en la tabla destino. */
  campo: string;
  tipo: TipoColumna;
  requerido?: boolean;
  /** Valor por defecto si la celda viene vacía y no es requerida. */
  porDefecto?: string | number | boolean;
}

export interface FilaValidada {
  filaCsv: number; // número de fila real del CSV (1 = encabezado, así que datos arrancan en 2), para mensajes al usuario
  valores: Record<string, unknown>;
  /** Texto corto para mostrar en la previsualización (ej. alias de la propiedad, o "Contrato: X — Y"). */
  resumen: string;
}

export interface ResultadoValidacion {
  filasValidas: FilaValidada[];
  errores: string[]; // filas descartadas — no se pueden importar
  avisos: string[]; // se importan igual, pero con algo para revisar (ej. "inquilino no encontrado, se importa sin inquilino")
}
