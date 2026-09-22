import type { ColumnaImport, TablaImportable, TipoColumna } from "@/lib/csv-migracion/tipos";

/**
 * Encabezados y columnas destino de cada tabla importable. Se mantienen
 * los MISMOS encabezados que ya usaba v1 (ver app.py, ESQUEMAS_VALIDOS y
 * MAPEO_CONTRATOS) — así cualquier CSV que el usuario ya tenga preparado
 * de antes sigue sirviendo tal cual, sin tener que rearmarlo.
 *
 * A diferencia de v1 (que para Propiedades/Inquilinos exigía que las
 * columnas del CSV coincidieran EXACTO con una lista fija, o rechazaba
 * el archivo entero), acá cada columna se busca por nombre y es
 * opcional salvo que se marque `requerido` — mismo criterio "robusto"
 * que Contratos/Gastos ya usaban en v1, ahora parejo en las 4 tablas
 * (confirmado con el usuario, sesión actual).
 */

export const PROPIEDADES_COLUMNAS: ColumnaImport[] = [
  { encabezado: "alias_propiedad", campo: "alias_propiedad", tipo: "texto", requerido: true },
  { encabezado: "calle", campo: "calle", tipo: "texto" },
  { encabezado: "numero", campo: "numero", tipo: "texto" },
  { encabezado: "departamento", campo: "departamento", tipo: "texto" },
  { encabezado: "propietario", campo: "propietario", tipo: "texto" },
  { encabezado: "ciudad", campo: "ciudad", tipo: "texto" },
  { encabezado: "provincia", campo: "provincia", tipo: "texto" },
  { encabezado: "tipo", campo: "tipo", tipo: "texto" },
  { encabezado: "nis", campo: "nis", tipo: "texto" },
  { encabezado: "cuenta_gas", campo: "cuenta_gas", tipo: "texto" },
  { encabezado: "finca", campo: "finca", tipo: "texto" },
  { encabezado: "cuenta_ooss", campo: "cuenta_ooss", tipo: "texto" },
  { encabezado: "nro_padron", campo: "nro_padron", tipo: "texto" },
];

export const INQUILINOS_COLUMNAS: ColumnaImport[] = [
  { encabezado: "apellidos", campo: "apellidos", tipo: "texto", requerido: true },
  { encabezado: "nombres", campo: "nombres", tipo: "texto", requerido: true },
  { encabezado: "dni", campo: "dni", tipo: "texto", requerido: true },
  { encabezado: "telefono", campo: "telefono", tipo: "texto" },
  { encabezado: "email", campo: "email", tipo: "texto" },
];

/**
 * `propiedad_id` en el CSV de v1 en realidad viste el ALIAS de la
 * propiedad, no el id numérico (así lo escribía v1, línea 6899-6900) —
 * se resuelve a `propiedad_id` real recién en validar.ts, después de
 * buscar la propiedad por alias. Se mantiene el mismo nombre de
 * encabezado por compatibilidad con CSVs ya preparados.
 */
export const GASTOS_COLUMNAS: ColumnaImport[] = [
  { encabezado: "propiedad_id", campo: "propiedad_id", tipo: "texto", requerido: true },
  { encabezado: "fecha", campo: "fecha", tipo: "fecha", requerido: true },
  { encabezado: "categoria", campo: "categoria", tipo: "texto", porDefecto: "Otros" },
  { encabezado: "descripcion", campo: "descripcion", tipo: "texto" },
  { encabezado: "monto", campo: "monto", tipo: "decimal", requerido: true },
  { encabezado: "proveedor", campo: "proveedor", tipo: "texto" },
  { encabezado: "comprobante", campo: "comprobante", tipo: "texto" },
  { encabezado: "pagado_por", campo: "pagado_por", tipo: "texto", porDefecto: "Inmobiliaria" },
  { encabezado: "observaciones", campo: "observaciones", tipo: "texto" },
  { encabezado: "tipo_gasto", campo: "tipo_gasto", tipo: "texto", porDefecto: "Extraordinario" },
  { encabezado: "cobrado", campo: "cobrado", tipo: "booleano", porDefecto: false },
  { encabezado: "periodo_cobrado", campo: "periodo_cobrado", tipo: "texto" },
];

/**
 * Puerto de MAPEO_CONTRATOS (app.py línea 6601) con la única corrección
 * ya documentada en docs/DESIGN_LOG.md (Módulo 10): "HONORARIOS PAGADOS"
 * y "GARANTÍA PAGADA" apuntan a las columnas NUEVAS
 * `honorarios_pagados_base`/`garantia_pagada_base` — las viejas
 * (`honorarios_pagados`/`garantia_pagada`) siguen siendo las que usa v1,
 * no se tocan.
 *
 * Mejora chica de esta sesión: v1 trunca esos dos montos a entero
 * (`int(float(...))`, línea 6837) — un resabio que no tiene sentido para
 * un monto en pesos. Como ahora escriben en columnas `numeric` nuevas
 * creadas para este propósito (sin nada de v1 leyéndolas), se guardan
 * como decimal, sin truncar.
 */
export const CONTRATOS_COLUMNAS: ColumnaImport[] = [
  { encabezado: "ALIAS PROPIEDAD", campo: "alias_propiedad", tipo: "texto", requerido: true },
  { encabezado: "DNI INQUILINO", campo: "dni_inquilino", tipo: "texto" },
  { encabezado: "ESTADO", campo: "estado", tipo: "texto", porDefecto: "Activo" },
  { encabezado: "INICIO CONTRATO", campo: "inicio_contrato", tipo: "fecha" },
  { encabezado: "FIN CONTRATO", campo: "fin_contrato", tipo: "fecha" },
  { encabezado: "DURACIÓN (MESES)", campo: "calc_duracion", tipo: "entero" },
  { encabezado: "ACTUALIZACIÓN", campo: "act_contrato", tipo: "entero" },
  { encabezado: "ÍNDICE", campo: "indice", tipo: "texto", porDefecto: "Otro" },
  { encabezado: "MONTO INICIAL", campo: "monto_inicial", tipo: "decimal" },
  { encabezado: "ALQUILER BASE", campo: "alquiler", tipo: "decimal" },
  { encabezado: "PRÓX ACTUALIZACIÓN", campo: "prox_actualizacion", tipo: "fecha" },
  { encabezado: "MES CONTRATO", campo: "mes_contrato", tipo: "entero" },
  { encabezado: "MES ACTUALIZACIÓN", campo: "mes_actualizacion_contrato", tipo: "entero" },
  { encabezado: "HONORARIOS", campo: "honorarios", tipo: "decimal" },
  { encabezado: "MONTO HONORARIOS", campo: "monto_honorarios", tipo: "decimal" },
  { encabezado: "CUOTAS HONORARIOS", campo: "cuota_honorarios", tipo: "entero" },
  { encabezado: "HONORARIOS PAGADOS", campo: "honorarios_pagados_base", tipo: "decimal" }, // corregido — ver doc-comment
  { encabezado: "TIPO GARANTÍA", campo: "tipo_de_garantie", tipo: "texto" },
  { encabezado: "VALOR GARANTÍA", campo: "monto_garantia", tipo: "decimal" },
  { encabezado: "GARANTÍA", campo: "garantia", tipo: "texto" },
  { encabezado: "GARANTÍA PAGADA", campo: "garantia_pagada_base", tipo: "decimal" }, // corregido — ver doc-comment
  { encabezado: "IMP INMO", campo: "imp_inmobiliario", tipo: "decimal" },
  { encabezado: "EXPENSAS BASE", campo: "expensas", tipo: "decimal" },
  { encabezado: "LUZ BASE", campo: "edesal", tipo: "decimal" },
  { encabezado: "GAS BASE", campo: "gas", tipo: "decimal" },
  { encabezado: "MUNI BASE", campo: "municipalidad", tipo: "decimal" },
  { encabezado: "AGUA BASE", campo: "ooss", tipo: "decimal" },
  { encabezado: "COCHERA BASE", campo: "cochera", tipo: "decimal" },
];

export const COLUMNAS_POR_TABLA: Record<TablaImportable, ColumnaImport[]> = {
  propiedades: PROPIEDADES_COLUMNAS,
  inquilinos: INQUILINOS_COLUMNAS,
  gastos_propiedades: GASTOS_COLUMNAS,
  contratos: CONTRATOS_COLUMNAS,
};

const VALORES_INDICE = ["ICL", "IPC", "UVA", "Otro"];
const VALORES_ESTADO_CONTRATO = ["Activo", "Finalizado", "Cancelado"];

/** dd/mm/aaaa, dd-mm-aaaa o aaaa-mm-dd (ya en formato ISO) → "aaaa-mm-dd". null si no se puede interpretar. */
export function parsearFechaFlexible(crudo: string): string | null {
  const valor = crudo.trim();
  if (!valor) return null;

  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor);
  if (iso) return valor;

  const conBarras = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec(valor);
  if (conBarras) {
    const [, d, m, a] = conBarras;
    const dia = (d ?? "").padStart(2, "0");
    const mes = (m ?? "").padStart(2, "0");
    if (Number(mes) < 1 || Number(mes) > 12 || Number(dia) < 1 || Number(dia) > 31) return null;
    return `${a}-${mes}-${dia}`;
  }

  return null;
}

export interface ResultadoParseoValor {
  valor: unknown;
  error: string | null;
}

/** Coerciona una celda cruda de CSV según el tipo declarado en el ColumnaImport correspondiente. */
export function parsearValor(columna: ColumnaImport, crudo: string | undefined): ResultadoParseoValor {
  const texto = (crudo ?? "").trim();

  if (!texto || texto.toLowerCase() === "nan" || texto.toLowerCase() === "none") {
    if (columna.requerido) return { valor: null, error: `falta "${columna.encabezado}"` };
    return { valor: columna.porDefecto ?? null, error: null };
  }

  switch (columna.tipo as TipoColumna) {
    case "texto": {
      if (columna.campo === "indice" && !VALORES_INDICE.some((v) => v.toLowerCase() === texto.toLowerCase())) {
        return { valor: "Otro", error: null };
      }
      if (columna.campo === "estado" && !VALORES_ESTADO_CONTRATO.some((v) => v.toLowerCase() === texto.toLowerCase())) {
        return { valor: null, error: `"${columna.encabezado}" tiene un valor inválido ("${texto}") — debe ser Activo, Finalizado o Cancelado` };
      }
      return { valor: texto, error: null };
    }

    case "entero": {
      const n = Math.trunc(Number(texto.replace(",", ".")));
      if (!Number.isFinite(n)) return { valor: null, error: `"${columna.encabezado}" no es un número entero válido ("${texto}")` };
      return { valor: n, error: null };
    }

    case "decimal": {
      const n = Number(texto.replace(",", "."));
      if (!Number.isFinite(n)) return { valor: null, error: `"${columna.encabezado}" no es un número válido ("${texto}")` };
      return { valor: Math.round(n * 100) / 100, error: null };
    }

    case "fecha": {
      const fecha = parsearFechaFlexible(texto);
      if (!fecha) return { valor: null, error: `"${columna.encabezado}" no es una fecha válida ("${texto}")` };
      return { valor: fecha, error: null };
    }

    case "booleano": {
      const esTrue = ["true", "1", "si", "sí"].includes(texto.toLowerCase());
      return { valor: esTrue, error: null };
    }

    default:
      return { valor: texto, error: null };
  }
}
