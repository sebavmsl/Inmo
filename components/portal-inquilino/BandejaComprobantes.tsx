"use client";

import { useState, useTransition } from "react";
import type { FilaComprobante } from "@/lib/portal-inquilino/queries";
import { revisarComprobante } from "@/app/(protected)/portal-inquilino/actions";
import { formatMoneda } from "@/lib/format";

const ETIQUETA_ESTADO: Record<FilaComprobante["estado"], string> = {
  pendiente: "⏳ Pendiente",
  aprobado: "✅ Aprobado",
  rechazado: "❌ Rechazado",
};

export function BandejaComprobantes({
  filas,
  onActualizar,
}: {
  filas: FilaComprobante[];
  onActualizar: (id: number, cambios: Partial<FilaComprobante>) => void;
}) {
  const [filtro, setFiltro] = useState<FilaComprobante["estado"] | "todos">("pendiente");
  const [pendiente, startTransition] = useTransition();
  const [idEnProceso, setIdEnProceso] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filasFiltradas = filtro === "todos" ? filas : filas.filter((f) => f.estado === filtro);

  function decidir(id: number, decision: "aprobado" | "rechazado") {
    setError(null);
    setIdEnProceso(id);
    startTransition(async () => {
      const res = await revisarComprobante(id, decision);
      setIdEnProceso(null);
      if (!res.ok) {
        setError(res.error ?? "Error al actualizar el comprobante.");
        return;
      }
      onActualizar(id, { estado: decision, fechaRevision: new Date().toISOString() });
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-brand-700">Estado:</span>
        <select
          value={filtro}
          onChange={(e) => setFiltro(e.target.value as typeof filtro)}
          className="rounded border border-brand-100 px-2 py-1.5"
        >
          <option value="pendiente">Pendientes</option>
          <option value="aprobado">Aprobados</option>
          <option value="rechazado">Rechazados</option>
          <option value="todos">Todos</option>
        </select>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {filasFiltradas.length === 0 ? (
        <p className="text-sm text-brand-500">No hay comprobantes en ese estado.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-brand-100">
          <table className="w-full text-sm">
            <thead className="bg-brand-50 text-left text-xs font-medium uppercase text-brand-500">
              <tr>
                <th className="px-3 py-2">Subido</th>
                <th className="px-3 py-2">Contrato</th>
                <th className="px-3 py-2">Propiedad</th>
                <th className="px-3 py-2">Inquilino</th>
                <th className="px-3 py-2">Monto declarado</th>
                <th className="px-3 py-2">Archivo</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filasFiltradas.map((f) => (
                <tr key={f.id} className="border-b border-brand-50 align-top">
                  <td className="px-3 py-2">{new Date(f.fechaSubida).toLocaleDateString("es-AR")}</td>
                  <td className="px-3 py-2">{f.codigoContrato}</td>
                  <td className="px-3 py-2">{f.propiedad}</td>
                  <td className="px-3 py-2">{f.inquilino}</td>
                  <td className="px-3 py-2">{f.montoDeclarado !== null ? formatMoneda(f.montoDeclarado) : "—"}</td>
                  <td className="px-3 py-2">
                    {f.urlArchivo ? (
                      <a href={f.urlArchivo} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline">
                        Ver
                      </a>
                    ) : (
                      <span className="text-brand-400">no disponible</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {ETIQUETA_ESTADO[f.estado]}
                    {f.estado !== "pendiente" && f.revisadoPor && (
                      <div className="text-xs text-brand-400">por {f.revisadoPor}</div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {f.estado === "pendiente" && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => decidir(f.id, "aprobado")}
                          disabled={pendiente && idEnProceso === f.id}
                          className="rounded border border-green-200 px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-50 disabled:opacity-60"
                        >
                          Aprobar
                        </button>
                        <button
                          onClick={() => decidir(f.id, "rechazado")}
                          disabled={pendiente && idEnProceso === f.id}
                          className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
                        >
                          Rechazar
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
