"use client";

import { useState } from "react";
import { enviarRecibosPreliminaresMasivo } from "@/app/(protected)/planilla/actions";

export function BotonEnviarMasivo() {
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleClick() {
    setCargando(true);
    setResultado(null);
    try {
      const { enviados, errores } = await enviarRecibosPreliminaresMasivo();
      setResultado(`${enviados} enviados` + (errores > 0 ? `, ${errores} con error` : ""));
    } catch (e) {
      setResultado(e instanceof Error ? e.message : "Error al enviar.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleClick}
        disabled={cargando}
        className="rounded-lg border border-brand-200 px-4 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {cargando ? "Enviando…" : "📲 Enviar preliminares (verificados)"}
      </button>
      {resultado && <span className="text-sm text-brand-500">{resultado}</span>}
    </div>
  );
}
