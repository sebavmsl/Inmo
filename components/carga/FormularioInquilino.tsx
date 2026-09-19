"use client";

import { useState } from "react";
import { crearInquilino } from "@/app/(protected)/auxiliares/actions";

export function FormularioInquilino() {
  const [dni, setDni] = useState("");
  const [nombres, setNombres] = useState("");
  const [apellidos, setApellidos] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    setEnviando(true);
    const res = await crearInquilino({ dni, nombres, apellidos, telefono, email });
    setEnviando(false);
    setResultado(res.ok ? "Inquilino creado." : res.error ?? "Error.");
    if (res.ok) {
      setDni("");
      setNombres("");
      setApellidos("");
      setTelefono("");
      setEmail("");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🧑 Nuevo Inquilino</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <input placeholder="DNI" value={dni} onChange={(e) => setDni(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Nombres" value={nombres} onChange={(e) => setNombres(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Apellidos" value={apellidos} onChange={(e) => setApellidos(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Teléfono (con código país, sin espacios)" value={telefono} onChange={(e) => setTelefono(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
      </div>
      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}
      <button onClick={handleSubmit} disabled={enviando} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
        {enviando ? "Guardando…" : "Guardar Inquilino"}
      </button>
    </div>
  );
}
