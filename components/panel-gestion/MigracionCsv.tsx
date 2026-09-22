"use client";

import { useState } from "react";
import {
  previsualizarImportacionCsv,
  confirmarImportacionCsv,
  exportarTablaCsv,
  type FilaExportada,
} from "@/app/(protected)/panel-gestion/actions-csv";
import { parsearCsv } from "@/lib/csv-migracion/parseCsv";
import { TABLAS_IMPORTABLES, TABLAS_EXPORTABLES, LABEL_TABLA, type TablaImportable, type TablaExportable, type ResultadoValidacion } from "@/lib/csv-migracion/tipos";

function descargarCsv(nombreArchivo: string, datos: FilaExportada) {
  const filasCsv = datos.filas.map((f) => datos.columnas.map((c) => f[c]));
  const csv = [datos.columnas, ...filasCsv]
    .map((fila) => fila.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivo;
  a.click();
  URL.revokeObjectURL(url);
}

function limitar(lista: string[], max = 8): string[] {
  if (lista.length <= max) return lista;
  return [...lista.slice(0, max), `…y ${lista.length - max} más.`];
}

export function MigracionCsv({ empresas }: { empresas: { id: number; nombreComercial: string }[] }) {
  const [empresaId, setEmpresaId] = useState<number | null>(empresas[0]?.id ?? null);

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🚀 Migración de Datos (CSV)</h2>
      <p className="text-xs text-brand-500">
        Herramienta de bajo nivel para migrar/respaldar datos tabla por tabla. Exclusiva de superadmin.
      </p>

      <label className="block max-w-sm text-sm">
        <span className="mb-1 block text-brand-700">Empresa a operar</span>
        <select
          value={empresaId ?? ""}
          onChange={(e) => setEmpresaId(e.target.value ? Number(e.target.value) : null)}
          className="w-full rounded border border-brand-100 px-2 py-1.5"
        >
          {empresas.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nombreComercial}
            </option>
          ))}
        </select>
      </label>

      {empresaId === null ? (
        <p className="text-sm text-brand-400">No hay empresas registradas.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <PanelExportar empresaId={empresaId} />
          <PanelImportar empresaId={empresaId} />
        </div>
      )}
    </div>
  );
}

function PanelExportar({ empresaId }: { empresaId: number }) {
  const [tabla, setTabla] = useState<TablaExportable>(TABLAS_EXPORTABLES[0]);
  const [cargando, setCargando] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

  async function handleExportar() {
    setCargando(true);
    setMensaje(null);
    try {
      const res = await exportarTablaCsv(empresaId, tabla);
      if (!res.ok || !res.datos) {
        setMensaje(res.error ?? "Error al exportar.");
        return;
      }
      if (res.datos.filas.length === 0) {
        setMensaje("No hay registros para exportar.");
        return;
      }
      descargarCsv(`${tabla}_${new Date().toISOString().slice(0, 10)}.csv`, res.datos);
      setMensaje(`${res.datos.filas.length} fila(s) exportada(s).`);
    } catch (e) {
      setMensaje(e instanceof Error ? e.message : "Error al exportar.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-brand-50 p-3">
      <h3 className="text-sm font-medium text-brand-800">📥 Exportar (bajar CSV)</h3>
      <select value={tabla} onChange={(e) => setTabla(e.target.value as TablaExportable)} className="w-full rounded border border-brand-100 px-2 py-1.5 text-sm">
        {TABLAS_EXPORTABLES.map((t) => (
          <option key={t} value={t}>
            {LABEL_TABLA[t]}
          </option>
        ))}
      </select>
      <button
        onClick={handleExportar}
        disabled={cargando}
        className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50 disabled:opacity-60"
      >
        {cargando ? "Exportando…" : `⬇️ Descargar '${LABEL_TABLA[tabla]}'`}
      </button>
      {mensaje && <p className="text-sm text-brand-600">{mensaje}</p>}
    </div>
  );
}

function PanelImportar({ empresaId }: { empresaId: number }) {
  const [tabla, setTabla] = useState<TablaImportable>(TABLAS_IMPORTABLES[0]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [filasCrudas, setFilasCrudas] = useState<Record<string, string>[]>([]);
  const [nombreArchivo, setNombreArchivo] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoValidacion | null>(null);
  const [cargando, setCargando] = useState(false);
  const [mensajeFinal, setMensajeFinal] = useState<string | null>(null);

  function resetear() {
    setHeaders([]);
    setFilasCrudas([]);
    setNombreArchivo(null);
    setResultado(null);
    setMensajeFinal(null);
  }

  async function handleArchivo(archivo: File | null) {
    resetear();
    if (!archivo) return;
    const texto = await archivo.text();
    const { headers: h, filas } = parsearCsv(texto);
    setHeaders(h);
    setFilasCrudas(filas);
    setNombreArchivo(archivo.name);
  }

  async function handlePrevisualizar() {
    setCargando(true);
    setMensajeFinal(null);
    try {
      const res = await previsualizarImportacionCsv(empresaId, tabla, headers, filasCrudas);
      setResultado(res);
    } catch (e) {
      setMensajeFinal(e instanceof Error ? e.message : "Error al validar el CSV.");
    } finally {
      setCargando(false);
    }
  }

  async function handleConfirmar() {
    if (!resultado || resultado.filasValidas.length === 0) return;
    setCargando(true);
    try {
      const res = await confirmarImportacionCsv(tabla, resultado.filasValidas);
      setMensajeFinal(res.ok ? `✅ ${res.insertados} fila(s) importada(s).` : res.error ?? "Error al importar.");
      if (res.ok) {
        setResultado(null);
        setFilasCrudas([]);
        setHeaders([]);
        setNombreArchivo(null);
      }
    } catch (e) {
      setMensajeFinal(e instanceof Error ? e.message : "Error al importar.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-brand-50 p-3">
      <h3 className="text-sm font-medium text-brand-800">📤 Importar (subir CSV)</h3>
      <select
        value={tabla}
        onChange={(e) => {
          setTabla(e.target.value as TablaImportable);
          resetear();
        }}
        className="w-full rounded border border-brand-100 px-2 py-1.5 text-sm"
      >
        {TABLAS_IMPORTABLES.map((t) => (
          <option key={t} value={t}>
            {LABEL_TABLA[t]}
          </option>
        ))}
      </select>

      <input
        type="file"
        accept=".csv,text/csv"
        onChange={(e) => handleArchivo(e.target.files?.[0] ?? null)}
        className="w-full text-sm"
      />

      {nombreArchivo && !resultado && (
        <button
          onClick={handlePrevisualizar}
          disabled={cargando || filasCrudas.length === 0}
          className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50 disabled:opacity-60"
        >
          {cargando ? "Validando…" : `Previsualizar (${filasCrudas.length} fila(s) leídas)`}
        </button>
      )}

      {resultado && (
        <div className="space-y-2 rounded-md bg-brand-50 p-3 text-sm">
          <p className="font-medium text-brand-800">
            {resultado.filasValidas.length} fila(s) lista(s) para importar
            {resultado.errores.length > 0 && ` · ${resultado.errores.length} con errores (se omiten)`}
          </p>

          {resultado.avisos.length > 0 && (
            <ul className="list-inside list-disc text-amber-700">
              {limitar(resultado.avisos).map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}

          {resultado.errores.length > 0 && (
            <ul className="list-inside list-disc text-red-600">
              {limitar(resultado.errores).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}

          {resultado.filasValidas.length > 0 && (
            <div className="flex gap-2">
              <button
                onClick={handleConfirmar}
                disabled={cargando}
                className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
              >
                {cargando ? "Importando…" : `⬆️ Confirmar e importar ${resultado.filasValidas.length}`}
              </button>
              <button onClick={resetear} className="rounded border border-brand-100 px-3 py-1.5 text-sm text-brand-500">
                Cancelar
              </button>
            </div>
          )}
        </div>
      )}

      {mensajeFinal && <p className="text-sm text-brand-600">{mensajeFinal}</p>}
    </div>
  );
}
