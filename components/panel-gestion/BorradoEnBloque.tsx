"use client";

import { useState } from "react";
import { borrarEnBloque } from "@/app/(protected)/panel-gestion/actions";

const TABLAS = ["contratos", "inquilinos", "propiedades", "pagos_historial"] as const;

export function BorradoEnBloque({ empresas }: { empresas: { id: number; nombreComercial: string }[] }) {
  const [empresaId, setEmpresaId] = useState<number | null>(empresas[0]?.id ?? null);
  const [tabla, setTabla] = useState<(typeof TABLAS)[number]>("contratos");
  const [idsTexto, setIdsTexto] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  const ids = idsTexto
    .split(",")
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n));

  const frasePendiente = `FORZAR BORRADO ${ids.length} FILAS`;

  async function handleSubmit() {
    if (!empresaId) return;
    setEnviando(true);
    setResultado(null);
    const res = await borrarEnBloque(empresaId, tabla, ids, confirmacion);
    setEnviando(false);
    setResultado(res.ok ? `${res.eliminados} filas eliminadas.` : res.error ?? "Error al borrar.");
    if (res.ok) {
      setIdsTexto("");
      setConfirmacion("");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-red-200 bg-red-50/30 p-5">
      <h2 className="text-sm font-semibold text-red-800">🗑️ Eliminar Filas / Registros en Bloque</h2>
      <p className="text-xs text-red-600">Acción irreversible. Solo superadmin.</p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <select
          value={empresaId ?? ""}
          onChange={(e) => setEmpresaId(e.target.value ? Number(e.target.value) : null)}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          {empresas.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nombreComercial}
            </option>
          ))}
        </select>
        <select value={tabla} onChange={(e) => setTabla(e.target.value as typeof tabla)} className="rounded border border-brand-100 px-2 py-1.5 text-sm">
          {TABLAS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          placeholder="IDs separados por coma (ej: 12, 15, 20)"
          value={idsTexto}
          onChange={(e) => setIdsTexto(e.target.value)}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        />
      </div>

      {ids.length > 0 && (
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">
            Escribí exactamente: <code className="rounded bg-brand-100 px-1">{frasePendiente}</code>
          </span>
          <input
            value={confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
      )}

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button
        onClick={handleSubmit}
        disabled={enviando || !empresaId || ids.length === 0 || confirmacion !== frasePendiente}
        className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
      >
        {enviando ? "Borrando…" : "Borrar Definitivamente"}
      </button>
    </div>
  );
}
