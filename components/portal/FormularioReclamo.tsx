"use client";

import { useState } from "react";
import { crearReclamo } from "@/app/portal/actions";
import type { InquilinoContrato } from "@/lib/inquilino/session";

/** Mismo fix de esta sesión que FormularioSubirComprobante.tsx: selector de contrato, no texto libre. */
export function FormularioReclamo({ contratos }: { contratos: InquilinoContrato[] }) {
  const [codigoContrato, setCodigoContrato] = useState(contratos[0]?.codigoContrato ?? "");
  const [descripcion, setDescripcion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    if (!codigoContrato || !descripcion) return;
    setEnviando(true);
    const res = await crearReclamo(codigoContrato, descripcion);
    setEnviando(false);
    setResultado(res.ok ? "Reclamo enviado." : res.error ?? "Error al enviar.");
    if (res.ok) setDescripcion("");
  }

  return (
    <div className="space-y-4 rounded-lg border border-brand-100 bg-white p-5">
      <h1 className="text-lg font-semibold text-brand-900">🛠️ Avisar un Problema</h1>

      <label className="block max-w-xs text-sm">
        <span className="mb-1 block text-brand-700">Contrato</span>
        <select value={codigoContrato} onChange={(e) => setCodigoContrato(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
          {contratos.map((c) => (
            <option key={`${c.empresaId}-${c.codigoContrato}`} value={c.codigoContrato}>
              {c.aliasPropiedad}
              {contratos.length > 1 ? ` — ${c.nombreEmpresa}` : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-brand-700">Descripción del problema</span>
        <textarea
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          rows={4}
          className="w-full rounded border border-brand-100 px-2 py-1.5"
        />
      </label>

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button
        onClick={handleSubmit}
        disabled={enviando || !codigoContrato || !descripcion}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {enviando ? "Enviando…" : "Enviar Reclamo"}
      </button>
    </div>
  );
}
