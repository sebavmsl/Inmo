import type { SupabaseClient } from "@supabase/supabase-js";
import { COLUMNAS_POR_TABLA, parsearValor } from "@/lib/csv-migracion/columnas";
import type { FilaValidada, ResultadoValidacion, TablaImportable } from "@/lib/csv-migracion/tipos";
import type { Database } from "@/lib/types/database.types";

type Cliente = SupabaseClient<Database>;

/**
 * Arma cada fila del CSV según las columnas de la tabla, sin todavía
 * chequear relaciones (propiedad/inquilino/dni existentes) — eso es
 * distinto por tabla y lo hace cada validador de abajo.
 */
function armarValores(
  tabla: TablaImportable,
  headers: string[],
  fila: Record<string, string>,
  filaCsv: number
): { valores: Record<string, unknown>; errores: string[] } {
  const columnas = COLUMNAS_POR_TABLA[tabla];
  const valores: Record<string, unknown> = {};
  const errores: string[] = [];

  for (const columna of columnas) {
    if (!headers.includes(columna.encabezado)) continue; // columna opcional ausente del CSV — se usa porDefecto/null más abajo, ni se procesa acá
    const { valor, error } = parsearValor(columna, fila[columna.encabezado]);
    if (error) {
      errores.push(`Fila ${filaCsv}: ${error}`);
      continue;
    }
    valores[columna.campo] = valor;
  }
  // Columnas opcionales que ni siquiera vinieron en el CSV: completar con porDefecto/null igual,
  // para que el insert final tenga un valor explícito.
  for (const columna of columnas) {
    if (!(columna.campo in valores) && !headers.includes(columna.encabezado)) {
      valores[columna.campo] = columna.porDefecto ?? null;
    }
  }

  return { valores, errores };
}

function columnasFaltantes(tabla: TablaImportable, headers: string[]): string[] {
  return COLUMNAS_POR_TABLA[tabla]
    .filter((c) => c.requerido && !headers.includes(c.encabezado))
    .map((c) => c.encabezado);
}

export async function validarFilas(
  supabase: Cliente,
  empresaId: number,
  tabla: TablaImportable,
  headers: string[],
  filasCsv: Record<string, string>[]
): Promise<ResultadoValidacion> {
  const faltantes = columnasFaltantes(tabla, headers);
  if (faltantes.length > 0) {
    return {
      filasValidas: [],
      errores: [`El CSV no tiene la(s) columna(s) requerida(s): ${faltantes.join(", ")}.`],
      avisos: [],
    };
  }

  switch (tabla) {
    case "propiedades":
      return validarPropiedades(supabase, empresaId, headers, filasCsv);
    case "inquilinos":
      return validarInquilinos(supabase, empresaId, headers, filasCsv);
    case "gastos_propiedades":
      return validarGastos(supabase, empresaId, headers, filasCsv);
    case "contratos":
      return validarContratos(supabase, empresaId, headers, filasCsv);
  }
}

async function validarPropiedades(
  supabase: Cliente,
  empresaId: number,
  headers: string[],
  filasCsv: Record<string, string>[]
): Promise<ResultadoValidacion> {
  const { data: existentes } = await supabase.from("propiedades").select("alias_propiedad").eq("empresa_id", empresaId);
  const aliasExistentes = new Set((existentes ?? []).map((p) => p.alias_propiedad.trim().toLowerCase()));
  const vistosEnArchivo = new Set<string>();

  const filasValidas: FilaValidada[] = [];
  const errores: string[] = [];

  filasCsv.forEach((fila, idx) => {
    const filaCsv = idx + 2;
    const { valores, errores: erroresFila } = armarValores("propiedades", headers, fila, filaCsv);
    if (erroresFila.length > 0) {
      errores.push(...erroresFila);
      return;
    }
    const alias = String(valores.alias_propiedad).trim();
    const claveNorm = alias.toLowerCase();
    if (aliasExistentes.has(claveNorm)) {
      errores.push(`Fila ${filaCsv}: ya existe una propiedad con alias "${alias}" — se omite.`);
      return;
    }
    if (vistosEnArchivo.has(claveNorm)) {
      errores.push(`Fila ${filaCsv}: alias "${alias}" repetido dentro del mismo CSV — se omite.`);
      return;
    }
    vistosEnArchivo.add(claveNorm);
    valores.empresa_id = empresaId;
    filasValidas.push({ filaCsv, valores, resumen: alias });
  });

  return { filasValidas, errores, avisos: [] };
}

async function validarInquilinos(
  supabase: Cliente,
  empresaId: number,
  headers: string[],
  filasCsv: Record<string, string>[]
): Promise<ResultadoValidacion> {
  const { data: existentes } = await supabase.from("inquilinos").select("dni").eq("empresa_id", empresaId);
  const dniExistentes = new Set((existentes ?? []).map((i) => i.dni.trim()));
  const vistosEnArchivo = new Set<string>();

  const filasValidas: FilaValidada[] = [];
  const errores: string[] = [];

  filasCsv.forEach((fila, idx) => {
    const filaCsv = idx + 2;
    const { valores, errores: erroresFila } = armarValores("inquilinos", headers, fila, filaCsv);
    if (erroresFila.length > 0) {
      errores.push(...erroresFila);
      return;
    }
    const dni = String(valores.dni).trim();
    if (dniExistentes.has(dni)) {
      errores.push(`Fila ${filaCsv}: ya existe un inquilino con DNI ${dni} — se omite.`);
      return;
    }
    if (vistosEnArchivo.has(dni)) {
      errores.push(`Fila ${filaCsv}: DNI ${dni} repetido dentro del mismo CSV — se omite.`);
      return;
    }
    vistosEnArchivo.add(dni);
    valores.dni = dni;
    valores.empresa_id = empresaId;
    filasValidas.push({ filaCsv, valores, resumen: `${valores.nombres} ${valores.apellidos} (DNI ${dni})` });
  });

  return { filasValidas, errores, avisos: [] };
}

async function validarGastos(
  supabase: Cliente,
  empresaId: number,
  headers: string[],
  filasCsv: Record<string, string>[]
): Promise<ResultadoValidacion> {
  const { data: propiedades } = await supabase.from("propiedades").select("id, alias_propiedad").eq("empresa_id", empresaId);
  const idPorAlias = new Map((propiedades ?? []).map((p) => [p.alias_propiedad.trim().toLowerCase(), p.id]));

  const filasValidas: FilaValidada[] = [];
  const errores: string[] = [];

  filasCsv.forEach((fila, idx) => {
    const filaCsv = idx + 2;
    const { valores, errores: erroresFila } = armarValores("gastos_propiedades", headers, fila, filaCsv);
    if (erroresFila.length > 0) {
      errores.push(...erroresFila);
      return;
    }
    const alias = String(valores.propiedad_id).trim();
    const propiedadId = idPorAlias.get(alias.toLowerCase());
    if (!propiedadId) {
      errores.push(`Fila ${filaCsv}: la propiedad "${alias}" no existe — se omite.`);
      return;
    }
    valores.propiedad_id = propiedadId;
    valores.empresa_id = empresaId;
    filasValidas.push({ filaCsv, valores, resumen: `${alias} — ${valores.fecha} — ${valores.descripcion || "(sin descripción)"}` });
  });

  return { filasValidas, errores, avisos: [] };
}

async function validarContratos(
  supabase: Cliente,
  empresaId: number,
  headers: string[],
  filasCsv: Record<string, string>[]
): Promise<ResultadoValidacion> {
  const [{ data: propiedades }, { data: inquilinos }] = await Promise.all([
    supabase.from("propiedades").select("alias_propiedad").eq("empresa_id", empresaId),
    supabase.from("inquilinos").select("dni").eq("empresa_id", empresaId),
  ]);
  const aliasValidos = new Set((propiedades ?? []).map((p) => p.alias_propiedad.trim().toLowerCase()));
  const dniValidos = new Set((inquilinos ?? []).map((i) => i.dni.trim()));

  const filasValidas: FilaValidada[] = [];
  const errores: string[] = [];
  const avisos: string[] = [];

  filasCsv.forEach((fila, idx) => {
    const filaCsv = idx + 2;
    const { valores, errores: erroresFila } = armarValores("contratos", headers, fila, filaCsv);
    if (erroresFila.length > 0) {
      errores.push(...erroresFila);
      return;
    }
    const alias = String(valores.alias_propiedad).trim();
    if (!aliasValidos.has(alias.toLowerCase())) {
      errores.push(`Fila ${filaCsv}: la propiedad "${alias}" no existe — se omite.`);
      return;
    }

    let dni = valores.dni_inquilino ? String(valores.dni_inquilino).trim() : null;
    if (dni) {
      if (!dniValidos.has(dni)) {
        avisos.push(`Fila ${filaCsv}: el inquilino DNI ${dni} no existe — se importa el contrato sin inquilino.`);
        dni = null;
      }
    }

    valores.alias_propiedad = alias;
    valores.dni_inquilino = dni;
    valores.empresa_id = empresaId;
    filasValidas.push({ filaCsv, valores, resumen: `${alias}${dni ? ` — DNI ${dni}` : ""}` });
  });

  return { filasValidas, errores, avisos };
}
