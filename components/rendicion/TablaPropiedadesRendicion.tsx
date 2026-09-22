"use client";

import type { FilaPropiedadRendicion, TotalesRendicion } from "@/lib/rendicion/queries";
import { formatMoneda } from "@/lib/format";
import { CATEGORIAS_CONCEPTO, LABEL_CATEGORIA } from "@/lib/conceptos/categorias";

const CATEGORIAS_INFORMATIVAS_UI = CATEGORIAS_CONCEPTO.filter((c) => c !== "ingreso-base" && c !== "expensas");

/**
 * Tabla agrupada por propiedad + KPIs + informativo — puerto de
 * `_agrupado` y las métricas de app.py líneas 8359-8417. Incluye export
 * CSV (v1 también lo ofrece acá, línea 8455).
 */
export function TablaPropiedadesRendicion({
  filas,
  totales,
  propietarioLabel,
  periodoLabel,
}: {
  filas: FilaPropiedadRendicion[];
  totales: TotalesRendicion;
  propietarioLabel: string;
  periodoLabel: string;
}) {
  function exportarCsv() {
    const encabezado = ["Propiedad", "Propietario", "Alquiler ($)", "Cochera ($)", "Expensas ($)", "Total Cobrado ($)", "Comisión ($)", "Neto a Rendir ($)"];
    const filasCsv = filas.map((f) => [f.propiedad, f.propietario, f.alquiler, f.cochera, f.expensas, f.totalCobrado, f.comision, f.netoARendir]);
    const csv = [encabezado, ...filasCsv].map((fila) => fila.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rendicion_${propietarioLabel.replace(/\s+/g, "_")}_${periodoLabel}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (filas.length === 0) {
    return <p className="text-sm text-brand-500">No hay cobros para ese propietario/período.</p>;
  }

  const mostrarColumnaPropietario = !filas.every((f) => f.propietario === propietarioLabel);

  return (
    <div className="space-y-3">
      <p className="text-sm text-brand-500">
        <strong>{filas.length}</strong> propiedad(es) — Propietario: <strong>{propietarioLabel}</strong> — Período: <strong>{periodoLabel}</strong>
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metrica label="💰 Total Cobrado" valor={totales.totalCobrado} />
        <Metrica label="🏢 Comisión Adm. (−)" valor={totales.totalComision} />
        <Metrica label="📤 Neto a Rendir" valor={totales.totalNeto} destacado />
        <div>
          <p className="text-xs text-brand-500">🏠 Propiedades</p>
          <p className="text-lg font-semibold text-brand-700">{totales.propiedades}</p>
        </div>
      </div>

      <p className="text-xs text-brand-400">
        Informativo — no forma parte del Neto a Rendir:{" "}
        {CATEGORIAS_INFORMATIVAS_UI.filter((cat) => (totales.informativoPorCategoria[cat] ?? 0) > 0)
          .map((cat) => `${LABEL_CATEGORIA[cat]} ${formatMoneda(totales.informativoPorCategoria[cat] ?? 0)}`)
          .join(" · ") || "sin conceptos informativos en este período"}
        {totales.totalExpensasInformativas > 0 && (
          <> · Expensas administradas por el propietario {formatMoneda(totales.totalExpensasInformativas)}</>
        )}
      </p>

      <div className="overflow-x-auto rounded-lg border border-brand-100">
        <table className="w-full text-sm">
          <thead className="bg-brand-50 text-left text-xs font-medium uppercase text-brand-500">
            <tr>
              <th className="px-3 py-2">Propiedad</th>
              {mostrarColumnaPropietario && <th className="px-3 py-2">Propietario</th>}
              <th className="px-3 py-2">Alquiler</th>
              <th className="px-3 py-2">Cochera</th>
              <th className="px-3 py-2">Expensas</th>
              <th className="px-3 py-2">Total Cobrado</th>
              <th className="px-3 py-2">Comisión (−)</th>
              <th className="px-3 py-2">Neto a Rendir</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.propiedad} className="border-b border-brand-50">
                <td className="px-3 py-2">{f.propiedad}</td>
                {mostrarColumnaPropietario && <td className="px-3 py-2">{f.propietario}</td>}
                <td className="px-3 py-2">{formatMoneda(f.alquiler)}</td>
                <td className="px-3 py-2">{formatMoneda(f.cochera)}</td>
                <td className="px-3 py-2">{formatMoneda(f.expensas)}</td>
                <td className="px-3 py-2">{formatMoneda(f.totalCobrado)}</td>
                <td className="px-3 py-2">{formatMoneda(f.comision)}</td>
                <td className="px-3 py-2 font-medium">{formatMoneda(f.netoARendir)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button onClick={exportarCsv} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50">
        ⬇️ Descargar CSV
      </button>
    </div>
  );
}

function Metrica({ label, valor, destacado }: { label: string; valor: number; destacado?: boolean }) {
  return (
    <div>
      <p className="text-xs text-brand-500">{label}</p>
      <p className={`text-lg font-semibold ${destacado ? "text-brand-900" : "text-brand-700"}`}>{formatMoneda(valor)}</p>
    </div>
  );
}
