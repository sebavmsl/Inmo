"use client";

import { useState } from "react";
import { eliminarEmpresa } from "@/app/(protected)/panel-gestion/actions";

export function EliminarEmpresa({ empresas }: { empresas: { id: number; nombreComercial: string }[] }) {
  const [empresaId, setEmpresaId] = useState<number | null>(null);
  const [confirmacion, setConfirmacion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  const empresaSel = empresas.find((e) => e.id === empresaId);

  async function handleSubmit() {
    if (!empresaId) return;
    setEnviando(true);
    setResultado(null);
    const res = await eliminarEmpresa(empresaId, confirmacion);
    setEnviando(false);
    setResultado(res.ok ? "Empresa eliminada." : res.error ?? "Error al eliminar.");
    if (res.ok) {
      setEmpresaId(null);
      setConfirmacion("");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-red-200 bg-red-50/30 p-5">
      <h2 className="text-sm font-semibold text-red-800">🗑️ Eliminar Empresa</h2>
      <p className="text-xs text-red-600">Borra todos los datos de la empresa (contratos, pagos, gastos, etc). Irreversible.</p>

      <select
        value={empresaId ?? ""}
        onChange={(e) => setEmpresaId(Number(e.target.value))}
        className="rounded border border-brand-100 px-2 py-1.5 text-sm"
      >
        <option value="">Seleccionar empresa…</option>
        {empresas.map((e) => (
          <option key={e.id} value={e.id}>
            {e.nombreComercial}
          </option>
        ))}
      </select>

      {empresaSel && (
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">
            Escribí el nombre exacto: <code className="rounded bg-brand-100 px-1">{empresaSel.nombreComercial}</code>
          </span>
          <input
            value={confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)}
            className="w-full max-w-sm rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
      )}

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button
        onClick={handleSubmit}
        disabled={enviando || !empresaSel || confirmacion !== empresaSel.nombreComercial}
        className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
      >
        {enviando ? "Eliminando…" : "Eliminar Definitivamente"}
      </button>
    </div>
  );
}
