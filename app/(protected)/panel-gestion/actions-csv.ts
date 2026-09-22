"use server";

import { createClient } from "@/lib/supabase/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { validarFilas } from "@/lib/csv-migracion/validar";
import { COLUMNAS_POR_TABLA } from "@/lib/csv-migracion/columnas";
import {
  TABLAS_IMPORTABLES,
  type FilaValidada,
  type ResultadoValidacion,
  type TablaExportable,
  type TablaImportable,
} from "@/lib/csv-migracion/tipos";

/**
 * Migración masiva por CSV — puerto de "🚀 Importar / Exportar Datos
 * (CSV)" (app.py, Panel de Gestión, exclusivo de superadmin). Alcance y
 * criterio de validación confirmados con el usuario — ver
 * lib/csv-migracion/tipos.ts.
 *
 * Todo acá usa el cliente CON sesión (createClient()), no service_role
 * — las policies de RLS ya dejan pasar a superadmin sin la restricción
 * de empresa_id (mismo patrón que EliminarEmpresa/BorradoEnBloque), así
 * que alcanza con el mismo chequeo de rol que ya usa el resto de este
 * Panel.
 */
async function requireSuperadmin() {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") throw new Error("Solo superadmin puede usar la migración por CSV.");
  return perfil;
}

function esTablaImportable(tabla: string): tabla is TablaImportable {
  return (TABLAS_IMPORTABLES as readonly string[]).includes(tabla);
}

/** Paso 1 — valida el CSV ya parseado del lado del cliente, sin escribir nada todavía. */
export async function previsualizarImportacionCsv(
  empresaId: number,
  tabla: TablaImportable,
  headers: string[],
  filas: Record<string, string>[]
): Promise<ResultadoValidacion> {
  await requireSuperadmin();
  if (!esTablaImportable(tabla)) throw new Error("Tabla no importable.");
  const supabase = await createClient();
  return validarFilas(supabase, empresaId, tabla, headers, filas);
}

/** Paso 2 — inserta las filas ya validadas (las que el usuario confirmó desde la previsualización). */
export async function confirmarImportacionCsv(
  tabla: TablaImportable,
  filasValidas: FilaValidada[]
): Promise<{ ok: boolean; insertados: number; error?: string }> {
  await requireSuperadmin();
  if (!esTablaImportable(tabla)) return { ok: false, insertados: 0, error: "Tabla no importable." };
  if (filasValidas.length === 0) return { ok: true, insertados: 0 };

  const supabase = await createClient();
  const TAMANO_LOTE = 500;
  let insertados = 0;

  for (let i = 0; i < filasValidas.length; i += TAMANO_LOTE) {
    const lote = filasValidas.slice(i, i + TAMANO_LOTE).map((f) => f.valores);
    // Cast necesario: `lote` se arma dinámicamente por tabla (ver
    // validar.ts) — no hay un tipo Insert<T> fijo que le podamos calzar
    // acá sin repetir a mano el switch de columnas por tabla.
    const { error } = await supabase.from(tabla).insert(lote as never);
    if (error) {
      return {
        ok: false,
        insertados,
        error: `Se importaron ${insertados} fila(s) antes de este error: ${error.message}`,
      };
    }
    insertados += lote.length;
  }

  return { ok: true, insertados };
}

export interface FilaExportada {
  columnas: string[];
  filas: Record<string, unknown>[];
}

/**
 * Exportación — a diferencia de v1 (volcado crudo `SELECT *` para todo
 * menos Contratos), acá se usan los mismos encabezados que ya define
 * cada ColumnaImport para las 4 tablas importables: así un CSV
 * exportado se puede volver a importar sin tener que retocarle las
 * columnas (round-trip limpio). Pagos Históricos y Permisos de Usuario
 * quedan como volcado crudo (solo-exportables, ver tipos.ts).
 *
 * Nota sobre Contratos: "HONORARIOS PAGADOS"/"GARANTÍA PAGADA" leen acá
 * de `honorarios_pagados_base`/`garantia_pagada_base` — las columnas
 * NUEVAS que la Carga de Contratos de v2 usa como valor vigente (ver
 * docs/DESIGN_LOG.md) — no de las viejas que sigue usando v1. Es una
 * decisión deliberada, no un descuido: mantiene simetría con lo que
 * importa esta misma herramienta.
 */
export async function exportarTablaCsv(empresaId: number, tabla: TablaExportable): Promise<{ ok: boolean; datos?: FilaExportada; error?: string }> {
  await requireSuperadmin();
  const supabase = await createClient();

  if (esTablaImportable(tabla)) {
    const columnas = COLUMNAS_POR_TABLA[tabla];
    const camposSql = Array.from(new Set(columnas.map((c) => c.campo)));
    const { data, error } = await supabase.from(tabla).select(camposSql.join(", ")).eq("empresa_id", empresaId);
    if (error) return { ok: false, error: error.message };

    const filas = (data ?? []).map((fila) => {
      const registro = fila as Record<string, unknown>;
      const salida: Record<string, unknown> = {};
      for (const columna of columnas) salida[columna.encabezado] = registro[columna.campo] ?? "";
      return salida;
    });

    return { ok: true, datos: { columnas: columnas.map((c) => c.encabezado), filas } };
  }

  if (tabla === "pagos_historial") {
    const { data, error } = await supabase.from("pagos_historial").select("*").eq("empresa_id", empresaId).order("fecha", { ascending: false });
    if (error) return { ok: false, error: error.message };
    const filas = (data ?? []).map((fila) => {
      const { empresa_id: _empresaId, ...resto } = fila as Record<string, unknown>;
      return resto;
    });
    const primeraFila = filas[0];
    const columnas = primeraFila ? Object.keys(primeraFila) : [];
    return { ok: true, datos: { columnas, filas } };
  }

  // permisos_usuario no tiene empresa_id (ver docs/DESIGN_LOG.md) — se
  // escopea por los usernames de la empresa elegida, vía usuarios_central.
  const { data: usuarios, error: errUsuarios } = await supabase.from("usuarios_central").select("username").eq("empresa_id", empresaId);
  if (errUsuarios) return { ok: false, error: errUsuarios.message };
  const usernames = (usuarios ?? []).map((u) => u.username);
  if (usernames.length === 0) return { ok: true, datos: { columnas: ["username", "pestana"], filas: [] } };

  const { data, error } = await supabase.from("permisos_usuario").select("username, pestana").in("username", usernames).order("username");
  if (error) return { ok: false, error: error.message };
  return { ok: true, datos: { columnas: ["username", "pestana"], filas: data ?? [] } };
}
