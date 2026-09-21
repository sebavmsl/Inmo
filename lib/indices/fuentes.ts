import * as XLSX from "xlsx";

/**
 * Fuentes externas de índices — puerto de `_obtener_icl_bcra_xls()` y
 * `_obtener_ipc_indec()` (app.py líneas 1759-1894), ampliado con UVA
 * (ver docs/DESIGN_LOG.md, sección "Ampliación del motor de índices").
 *
 * Devuelve siempre un mapa {"YYYY-MM-DD": valor}. En v1 esto corría con
 * `@st.cache_data(ttl=3600)` (cache en memoria de 1 hora); acá no hace
 * falta ese cache porque el cron corre una vez al día y persiste el
 * resultado en `indices_historicos` — no se vuelve a pedir hasta el
 * día siguiente.
 *
 * NOTA para quien despliegue esto: no pude probar estas URLs en vivo
 * desde este entorno (sin acceso de red). La heurística de detección de
 * columnas del XLS del BCRA está portada 1:1 de la lógica de pandas,
 * pero vale la pena correr el cron una vez en modo manual/staging y
 * revisar los logs antes de confiar en el cron automático en producción.
 */

type SerieIndice = Record<string, number>;

/**
 * Caché en memoria, por año, SOLO para la duración de una ejecución
 * (se reinicia en cada cold start / invocación de la función serverless
 * — no es una caché persistente entre corridas). Evita pedirle el mismo
 * año a BCRA una vez por cada contrato elegible cuando el cron procesa
 * un lote — sin necesitar una tabla que tendría que cubrir años de
 * historia para no romper contratos viejos (ver docs/DESIGN_LOG.md,
 * corrección de esta sesión: "por qué leer de indices_historicos en el
 * paso 3 no funciona").
 */
const cacheIclPorAnio = new Map<number, Promise<SerieIndice>>();
const cacheUvaPromise: { valor: Promise<SerieIndice> | null } = { valor: null };

/** Puerto de `_obtener_icl_bcra_xls(año)` — línea 1759. */
export async function obtenerIclBcraXls(anio: number): Promise<SerieIndice> {
  if (!cacheIclPorAnio.has(anio)) {
    cacheIclPorAnio.set(anio, obtenerIclBcraXlsSinCache(anio));
  }
  return cacheIclPorAnio.get(anio)!;
}

async function obtenerIclBcraXlsSinCache(anio: number): Promise<SerieIndice> {
  const url = `https://www.bcra.gob.ar/pdfs/PublicacionesEstadisticas/icl${anio}.xls`;
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const buffer = await resp.arrayBuffer();
    const resultado = parsearXlsFechaValor(buffer);
    if (Object.keys(resultado).length > 0) return resultado;
    throw new Error("XLS descargado pero sin datos válidos");
  } catch (e) {
    console.warn(`[ICL] Fuente primaria BCRA falló para ${anio}:`, e);
  }

  // Fallback: API pública datos.gob.ar (misma serie que usa v1)
  try {
    const url = "https://apis.datos.gob.ar/series/api/series/?ids=174.1_ICL_0_0_32&limit=5000&format=json";
    const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const puntos: [string, number][] = (data.data ?? []).filter((p: unknown[]) => p[1] !== null);
    if (puntos.length > 0) {
      const resultado: SerieIndice = {};
      for (const [fecha, valor] of puntos) resultado[fecha] = valor;
      return resultado;
    }
  } catch (e2) {
    console.warn("[ICL] Fallback datos.gob.ar también falló:", e2);
  }

  return {};
}

/**
 * UVA — mismo mecanismo que ICL (XLS diario del BCRA), pero es UN SOLO
 * archivo con toda la serie histórica, no uno por año.
 * (ver docs/DESIGN_LOG.md, sección "Ampliación del motor de índices — UVA")
 */
export async function obtenerUvaBcraXls(): Promise<SerieIndice> {
  if (!cacheUvaPromise.valor) {
    cacheUvaPromise.valor = obtenerUvaBcraXlsSinCache();
  }
  return cacheUvaPromise.valor;
}

async function obtenerUvaBcraXlsSinCache(): Promise<SerieIndice> {
  const url = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/diar_uva.xls";
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const buffer = await resp.arrayBuffer();
    const resultado = parsearXlsFechaValor(buffer);
    if (Object.keys(resultado).length > 0) return resultado;
    throw new Error("XLS de UVA descargado pero sin datos válidos");
  } catch (e) {
    console.warn("[UVA] Fuente BCRA falló:", e);
    return {};
  }
}

/** Puerto de `_obtener_ipc_indec()` — línea 1841. */
export async function obtenerIpcIndec(): Promise<SerieIndice> {
  const url = "https://apis.datos.gob.ar/series/api/series/?ids=145.3_INGNACUAL_DICI_M_38&limit=1000&format=json";
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const puntos: [string, number][] = (data.data ?? []).filter((p: unknown[]) => p[1] !== null);
    if (puntos.length === 0) throw new Error("La API del INDEC no devolvió datos");

    // El IPC viene como variación mensual (ej: 0.0158 = 1.58%) — se
    // acumula en un índice base=1, igual que v1.
    const resultado: SerieIndice = {};
    let indiceAcum = 1.0;
    for (const [fecha, variacion] of puntos) {
      indiceAcum *= 1 + Number(variacion);
      resultado[fecha] = indiceAcum;
    }
    return resultado;
  } catch (e) {
    console.warn("[IPC] Fuente primaria datos.gob.ar falló:", e);
  }

  // Fallback: serie alternativa (misma que usa v1)
  try {
    const url =
      "https://apis.datos.gob.ar/series/api/series/?ids=145.3_INGNACUAL_DICI_M_38,103.1_I2N_2016_M_19&limit=1000&format=json";
    const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const puntos: [string, number][] = (data.data ?? []).filter((p: unknown[]) => p[1] !== null);
    if (puntos.length > 0) {
      const resultado: SerieIndice = {};
      let indiceAcum = 1.0;
      for (const [fecha, variacion] of puntos) {
        indiceAcum *= 1 + Number(variacion);
        resultado[fecha] = indiceAcum;
      }
      return resultado;
    }
  } catch (e2) {
    console.warn("[IPC] Fallback alternativo también falló:", e2);
  }

  return {};
}

/**
 * Puerto de la heurística de detección de columnas de
 * `_obtener_icl_bcra_xls()` (líneas 1782-1799): busca, entre las
 * primeras 15 columnas, una con más de 5 valores en formato YYYYMMDD
 * (8 dígitos) — esa es la columna de fecha, y el valor está en la
 * columna siguiente. Si no encuentra ninguna, cae al fallback de v1
 * (columnas 7 y 8 fijas).
 */
function parsearXlsFechaValor(buffer: ArrayBuffer): SerieIndice {
  const libro = XLSX.read(buffer, { type: "array" });
  const primeraHoja = libro.SheetNames[0];
  if (!primeraHoja) return {};
  const hoja = libro.Sheets[primeraHoja];
  if (!hoja) return {};
  const filas: unknown[][] = XLSX.utils.sheet_to_json(hoja, { header: 1, raw: true });

  const maxColumnas = Math.min(15, Math.max(...filas.map((f) => f.length)));
  let colFecha: number | null = null;

  for (let col = 0; col < maxColumnas; col++) {
    const fechasValidas = filas.filter((f) => /^\d{8}$/.test(String(f[col] ?? "").trim())).length;
    if (fechasValidas > 5) {
      colFecha = col;
      break;
    }
  }

  const [cf, cv] = colFecha !== null ? [colFecha, colFecha + 1] : [7, 8];

  const resultado: SerieIndice = {};
  for (const fila of filas) {
    const fechaRaw = String(fila[cf] ?? "").trim();
    const valorRaw = fila[cv];
    if (!/^\d{8}$/.test(fechaRaw)) continue;
    const valor = Number(valorRaw);
    if (Number.isNaN(valor)) continue;
    const anio = fechaRaw.slice(0, 4);
    const mes = fechaRaw.slice(4, 6);
    const dia = fechaRaw.slice(6, 8);
    resultado[`${anio}-${mes}-${dia}`] = valor;
  }
  return resultado;
}
