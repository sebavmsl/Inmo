"use client";

import { useEffect, useState } from "react";
import { obtenerCotizacionUsd } from "@/lib/cotizacion/queries";

const ETIQUETA_FUENTE: Record<string, string> = {
  bna: "BNA (recién traída)",
  ultimo_conocido: "último valor conocido — BNA no respondió",
  sin_dato: "sin dato todavía — cargala a mano",
};

/**
 * Campo de cotización del dólar para Pagos/Gastos (Módulo 4). Se
 * autocarga al montar (BNA, con fallback al último valor usado en la
 * empresa — nunca 0 salvo que no haya ningún antecedente). Solo es
 * editable a mano para quien tiene el permiso "cotizacion_manual" (ver
 * lib/auth/permissions.ts) — para el resto queda de solo lectura, con
 * el botón de refresco igual disponible.
 */
export function CampoCotizacionUsd({ valor, onChange }: { valor: number; onChange: (v: number) => void }) {
  const [cargando, setCargando] = useState(true);
  const [puedeEditar, setPuedeEditar] = useState(false);
  const [fuente, setFuente] = useState<string | null>(null);

  async function cargar() {
    setCargando(true);
    const res = await obtenerCotizacionUsd();
    onChange(res.valor);
    setPuedeEditar(res.puedeEditar);
    setFuente(res.fuente);
    setCargando(false);
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <label className="block text-sm">
      <span className="mb-1 block text-brand-700">Cotización USD (BNA)</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={valor}
          disabled={!puedeEditar}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full rounded border border-brand-100 px-2 py-1.5 disabled:bg-brand-50 disabled:text-brand-500"
        />
        <button
          type="button"
          onClick={cargar}
          disabled={cargando}
          title="Volver a traer de BNA"
          className="shrink-0 rounded border border-brand-100 px-2 py-1.5 text-xs text-brand-600 hover:bg-brand-50 disabled:opacity-60"
        >
          {cargando ? "…" : "🔄"}
        </button>
      </div>
      {fuente && (
        <span className="mt-1 block text-xs text-brand-400">
          {ETIQUETA_FUENTE[fuente]}
          {!puedeEditar && " · no tenés permiso para editarla a mano"}
        </span>
      )}
    </label>
  );
}
