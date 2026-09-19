"use client";

import { useState } from "react";
import { subirComprobante } from "@/app/portal/actions";

export default function SubirComprobantePage() {
  const [codigoContrato, setCodigoContrato] = useState("");
  const [monto, setMonto] = useState(0);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    if (!archivo || !codigoContrato) return;
    setEnviando(true);
    const res = await subirComprobante(codigoContrato, monto, archivo);
    setEnviando(false);
    setResultado(res.ok ? "Comprobante subido. El staff lo va a revisar en breve." : res.error ?? "Error al subir.");
  }

  return (
    <div className="space-y-4 rounded-lg border border-brand-100 bg-white p-5">
      <h1 className="text-lg font-semibold text-brand-900">📎 Subir Comprobante de Pago</h1>
      <p className="text-sm text-brand-500">
        Esto no registra el pago automáticamente — queda pendiente de revisión por el staff.
      </p>

      <label className="block max-w-xs text-sm">
        <span className="mb-1 block text-brand-700">Código de contrato</span>
        <input value={codigoContrato} onChange={(e) => setCodigoContrato(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>
      <label className="block max-w-xs text-sm">
        <span className="mb-1 block text-brand-700">Monto que pagaste</span>
        <input type="number" value={monto} onChange={(e) => setMonto(Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>
      <label className="block max-w-xs text-sm">
        <span className="mb-1 block text-brand-700">Archivo (foto o PDF)</span>
        <input type="file" accept="image/*,application/pdf" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} className="w-full text-sm" />
      </label>

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button
        onClick={handleSubmit}
        disabled={enviando || !archivo || !codigoContrato}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {enviando ? "Subiendo…" : "Subir"}
      </button>
    </div>
  );
}
