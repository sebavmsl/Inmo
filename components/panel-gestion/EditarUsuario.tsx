"use client";

import { useState } from "react";
import { enviarLinkAcceso } from "@/app/(protected)/panel-gestion/actions";

export function EditarUsuario() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleSubmit() {
    setEnviando(true);
    setResultado(null);
    const res = await enviarLinkAcceso({
      tabla: "usuarios_central",
      identificador: { username },
      email,
    });
    setEnviando(false);
    setResultado(res.ok ? `Link enviado a ${email}.` : res.error ?? "Error al enviar.");
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🔑 Enviar Link de Acceso</h2>
      <p className="text-xs text-brand-400">
        Si el usuario nunca migró a v2, se lo invita por primera vez. Si ya tiene cuenta, se le manda un reset de
        contraseña.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
        <input placeholder="Email (confirmá o corregí)" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="rounded border border-brand-100 px-2 py-1.5 text-sm" />
      </div>
      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}
      <button
        onClick={handleSubmit}
        disabled={enviando || !username || !email}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {enviando ? "Enviando…" : "Enviar Link"}
      </button>
    </div>
  );
}
