"use client";

import { useState } from "react";
import { crearEmpresaConAdmin } from "@/app/(protected)/panel-gestion/actions";

export function AltaEmpresa() {
  const [nombreComercial, setNombreComercial] = useState("");
  const [emailAdmin, setEmailAdmin] = useState("");
  const [usernameAdmin, setUsernameAdmin] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    setEnviando(true);
    setResultado(null);
    const res = await crearEmpresaConAdmin({ nombreComercial, emailAdmin, usernameAdmin });
    setEnviando(false);
    setResultado(
      res.ok
        ? `Empresa creada. Se envió un link de acceso a ${emailAdmin}.`
        : res.error ?? "Error al crear la empresa."
    );
    if (res.ok) {
      setNombreComercial("");
      setEmailAdmin("");
      setUsernameAdmin("");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🏢 Alta de Empresa Nueva</h2>
      <p className="text-xs text-brand-400">
        Crea la empresa y su primer usuario admin juntos, atómicamente. Se le manda un link de acceso por email
        (nunca una contraseña provisoria).
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <input placeholder="Nombre comercial" value={nombreComercial} onChange={(e) => setNombreComercial(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Username del admin" value={usernameAdmin} onChange={(e) => setUsernameAdmin(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Email del admin" type="email" value={emailAdmin} onChange={(e) => setEmailAdmin(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
      </div>
      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}
      <button
        onClick={handleSubmit}
        disabled={enviando || !nombreComercial || !emailAdmin || !usernameAdmin}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {enviando ? "Creando…" : "Crear Empresa"}
      </button>
    </div>
  );
}
