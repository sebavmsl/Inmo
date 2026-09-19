"use client";

import { useState } from "react";
import { actualizarIndicesManual } from "@/app/(protected)/planilla/actions";

/**
 * Puerto del botón "🔄 Actualizar índices" de la Planilla. Respaldo real
 * ante fallo del cron (ver DESIGN_LOG.md) — refresca en vivo, sin asumir
 * que el cron ya corrió. Checkbox "solo pendientes" destildado por
 * defecto, mismo comportamiento que v1 cuando no se usa.
 */
export function BotonActualizarIndices() {
  const [soloPendientes, setSoloPendientes] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function handleClick() {
    setCargando(true);
    setResultado(null);
    try {
      const { actualizados, sinResultado, total } = await actualizarIndicesManual(soloPendientes);
      setResultado(
        total === 0
          ? "No hay contratos elegibles este mes."
          : `${actualizados} de ${total} actualizados` +
              (sinResultado > 0 ? ` (${sinResultado} sin datos de índice disponibles)` : "")
      );
    } catch (e) {
      setResultado(e instanceof Error ? e.message : "Error al actualizar índices.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        onClick={handleClick}
        disabled={cargando}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {cargando ? "Actualizando…" : "🔄 Actualizar índices"}
      </button>
      <label className="flex items-center gap-1.5 text-sm text-brand-700">
        <input
          type="checkbox"
          checked={soloPendientes}
          onChange={(e) => setSoloPendientes(e.target.checked)}
        />
        Solo contratos sin actualizar este mes
      </label>
      {resultado && <span className="text-sm text-brand-500">{resultado}</span>}
    </div>
  );
}
