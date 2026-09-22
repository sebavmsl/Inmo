"use client";

import { useMemo, useState } from "react";
import type { FilaGasto } from "@/lib/gastos/queries";
import { formatMoneda } from "@/lib/format";

/**
 * Módulo 2 (Tier A). Filtros por propiedad/categoría/texto + 4 totales
 * + export CSV — mismo criterio que la subpestaña "Historial de
 * Gastos" de app.py.
 */
export function TablaGastos({ filas }: { filas: FilaGasto[] }) {
  const [propiedad, setPropiedad] = useState("Todas");
  const [categoria, setCategoria] = useState("Todas");
  const [texto, setTexto] = useState("");

  const propiedades = useMemo(() => Array.from(new Set(filas.map((f) => f.propiedad))).sort(), [filas]);
  const categorias = useMemo(() => Array.from(new Set(filas.map((f) => f.categoria))).sort(), [filas]);

  const filtradas = useMemo(() => {
    const t = texto.trim().toLowerCase();
    return filas.filter((f) => {
      if (propiedad !== "Todas" && f.propiedad !== propiedad) return false;
      if (categoria !== "Todas" && f.categoria !== categoria) return false;
      if (t) {
        const enTexto = `${f.descripcion} ${f.proveedor ?? ""} ${f.observaciones ?? ""}`.toLowerCase();
        if (!enTexto.includes(t)) return false;
      }
      return true;
    });
  }, [filas, propiedad, categoria, texto]);

  const totalArs = filtradas.reduce((acc, f) => acc + f.monto, 0);
  const totalUsd = filtradas.reduce((acc, f) => acc + (f.montoUsd ?? 0), 0);
  const cantidad = filtradas.length;
  const promedio = cantidad > 0 ? totalArs / cantidad : 0;

  function exportarCsv() {
    const encabezado = [
      "Propiedad",
      "Propietario",
      "Fecha",
      "Categoría",
      "Tipo",
      "Descripción",
      "Monto ($)",
      "Cotización USD",
      "Monto (USD)",
      "Proveedor",
      "Comprobante",
      "Pagado por",
      "Observaciones",
    ];
    const filasCsv = filtradas.map((f) => [
      f.propiedad,
      f.propietario,
      f.fecha,
      f.categoria,
      f.tipoGasto,
      f.descripcion,
      f.monto,
      f.cotizacionUsd ?? "",
      f.montoUsd ?? "",
      f.proveedor ?? "",
      f.comprobante ?? "",
      f.pagadoPor,
      f.observaciones ?? "",
    ]);
    const csv = [encabezado, ...filasCsv]
      .map((fila) => fila.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "gastos_propiedades.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (filas.length === 0) {
    return <p className="text-sm text-brand-500">Aún no se registraron gastos.</p>;
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-brand-400">
        Los valores en USD corresponden a la cotización del momento en que se registró cada gasto.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Propiedad</span>
          <select value={propiedad} onChange={(e) => setPropiedad(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
            <option>Todas</option>
            {propiedades.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Categoría</span>
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
            <option>Todas</option>
            {categorias.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Buscar texto</span>
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Descripción, proveedor…"
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Total filtrado</p>
          <p className="font-semibold">{formatMoneda(totalArs)}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Total (USD)</p>
          <p className="font-semibold">U$S {totalUsd.toLocaleString("es-AR", { minimumFractionDigits: 2 })}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Cantidad</p>
          <p className="font-semibold">{cantidad}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Promedio por gasto</p>
          <p className="font-semibold">{formatMoneda(promedio)}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-brand-100">
        <table className="w-full text-sm">
          <thead className="bg-brand-50 text-left text-xs font-medium uppercase text-brand-500">
            <tr>
              <th className="px-3 py-2">Propiedad</th>
              <th className="px-3 py-2">Propietario</th>
              <th className="px-3 py-2">Fecha</th>
              <th className="px-3 py-2">Categoría</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Descripción</th>
              <th className="px-3 py-2">Monto ($)</th>
              <th className="px-3 py-2">Monto (USD)</th>
              <th className="px-3 py-2">Proveedor</th>
              <th className="px-3 py-2">Comprobante</th>
              <th className="px-3 py-2">Pagado por</th>
            </tr>
          </thead>
          <tbody>
            {filtradas.map((f) => (
              <tr key={f.id} className="border-b border-brand-50">
                <td className="px-3 py-2">{f.propiedad}</td>
                <td className="px-3 py-2">{f.propietario}</td>
                <td className="px-3 py-2">{new Date(f.fecha).toLocaleDateString("es-AR")}</td>
                <td className="px-3 py-2">{f.categoria}</td>
                <td className="px-3 py-2">{f.tipoGasto}</td>
                <td className="px-3 py-2">{f.descripcion}</td>
                <td className="px-3 py-2">{formatMoneda(f.monto)}</td>
                <td className="px-3 py-2">{f.montoUsd ? `U$S ${f.montoUsd.toLocaleString("es-AR", { minimumFractionDigits: 2 })}` : "—"}</td>
                <td className="px-3 py-2">{f.proveedor ?? "-"}</td>
                <td className="px-3 py-2">{f.comprobante ?? "-"}</td>
                <td className="px-3 py-2">{f.pagadoPor}</td>
              </tr>
            ))}
            {filtradas.length === 0 && (
              <tr>
                <td colSpan={11} className="px-3 py-4 text-center text-brand-400">
                  Ningún gasto matchea los filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <button onClick={exportarCsv} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50">
        ⬇️ Exportar a CSV
      </button>
    </div>
  );
}
