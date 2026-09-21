"use client";

import { useState } from "react";
import { crearPropiedad } from "@/app/(protected)/auxiliares/actions";

export function FormularioPropiedad() {
  const [aliasPropiedad, setAlias] = useState("");
  const [calle, setCalle] = useState("");
  const [numero, setNumero] = useState("");
  const [propietario, setPropietario] = useState("");
  const [grupo, setGrupo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    setEnviando(true);
    const res = await crearPropiedad({ aliasPropiedad, calle, numero, propietario, grupo: grupo || null });
    setEnviando(false);
    setResultado(res.ok ? "Propiedad creada." : res.error ?? "Error.");
    if (res.ok) {
      setAlias("");
      setCalle("");
      setNumero("");
      setPropietario("");
      setGrupo("");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🏠 Nueva Propiedad</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <input placeholder="Alias" value={aliasPropiedad} onChange={(e) => setAlias(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Calle" value={calle} onChange={(e) => setCalle(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Número" value={numero} onChange={(e) => setNumero(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Propietario" value={propietario} onChange={(e) => setPropietario(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Grupo/Edificio (opcional, gastos compartidos)" value={grupo} onChange={(e) => setGrupo(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
      </div>
      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}
      <button onClick={handleSubmit} disabled={enviando} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
        {enviando ? "Guardando…" : "Guardar Propiedad"}
      </button>
    </div>
  );
}
