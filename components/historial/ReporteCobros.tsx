"use client";

import { useMemo, useState } from "react";
import type { FilaHistorial } from "@/lib/historial/queries";
import { formatMoneda } from "@/lib/format";

const TODOS_LOS_USUARIOS = "Toda la empresa";

/**
 * "Generar Reporte de Cobros" — puerto de la sección de reportes de
 * app.py (líneas 4813-4910): filtro por rango de fechas + usuario que
 * registró el cobro, totales, y descarga en CSV.
 *
 * Simplificación deliberada de esta sesión: v1 además genera un PDF con
 * ReportLab (líneas 4912-5001). Acá se ofrece solo CSV — mismo patrón ya
 * usado en Gastos (TablaGastos.tsx) — porque cubre el mismo dato y evita
 * sumar una dependencia de generación de PDF solo para este reporte. Si
 * hace falta el PDF más adelante, se agrega aparte.
 *
 * También se deja afuera "TOTAL ($)" como columna propia: en el esquema
 * real, `pagos_historial` no distingue un "importe total facturado" de
 * "monto abonado" — v1 muestra el mismo valor (`monto_abonado`) bajo dos
 * encabezados distintos. Acá se muestra una sola vez, como "Abonado".
 */
export function ReporteCobros({ filas }: { filas: FilaHistorial[] }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const [desde, setDesde] = useState("2020-01-01");
  const [hasta, setHasta] = useState(hoy);
  const [usuario, setUsuario] = useState(TODOS_LOS_USUARIOS);

  const usuarios = useMemo(
    () => [TODOS_LOS_USUARIOS, ...Array.from(new Set(filas.map((f) => f.registradoPor).filter((u): u is string => !!u))).sort()],
    [filas]
  );

  const filtradas = useMemo(() => {
    const desdeDt = new Date(desde);
    const hastaDt = new Date(hasta);
    hastaDt.setHours(23, 59, 59, 999);
    return filas.filter((f) => {
      const fechaDt = new Date(f.fecha);
      if (fechaDt < desdeDt || fechaDt > hastaDt) return false;
      if (usuario !== TODOS_LOS_USUARIOS && f.registradoPor !== usuario) return false;
      return true;
    });
  }, [filas, desde, hasta, usuario]);

  const totalAlquiler = filtradas.reduce((a, f) => a + f.montoAlquiler, 0);
  const totalExpensas = filtradas.reduce((a, f) => a + f.montoExpensas, 0);
  const totalCochera = filtradas.reduce((a, f) => a + f.montoCochera, 0);
  const totalServicios = filtradas.reduce((a, f) => a + f.montoServicios, 0);
  const totalAbonado = filtradas.reduce((a, f) => a + f.montoAbonado, 0);

  function exportarCsv() {
    const encabezado = ["Fecha", "Período", "Mes/Año", "Propiedad", "Domicilio", "Inquilino", "Alquiler ($)", "Expensas ($)", "Cochera ($)", "Servicios ($)", "Abonado ($)"];
    const filasCsv = filtradas.map((f) => [
      new Date(f.fecha).toLocaleDateString("es-AR"),
      f.periodo,
      f.mesAnio,
      f.propiedad,
      f.domicilio,
      f.inquilino,
      f.montoAlquiler,
      f.montoExpensas,
      f.montoCochera,
      f.montoServicios,
      f.montoAbonado,
    ]);
    const totales = [
      [],
      ["TOTALES"],
      ["Total Alquiler", totalAlquiler],
      ["Total Expensas", totalExpensas],
      ["Total Cochera", totalCochera],
      ["Total Servicios", totalServicios],
      ["Total Abonado", totalAbonado],
    ];
    const csv = [encabezado, ...filasCsv, ...totales]
      .map((fila) => fila.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reporte_cobros_${desde}_${hasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <details className="rounded-lg border border-brand-100 bg-white">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-brand-800">
        📋 Generar Reporte de Cobros
      </summary>
      <div className="space-y-4 border-t border-brand-100 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Desde</span>
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Hasta</span>
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Filtrar por usuario</span>
            <select value={usuario} onChange={(e) => setUsuario(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
              {usuarios.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="text-xs text-brand-500">
          <strong>{filtradas.length}</strong> registro{filtradas.length === 1 ? "" : "s"} en el período seleccionado.
        </p>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-brand-50 p-3 text-sm">
            <p className="text-xs text-brand-500">Total alquiler</p>
            <p className="font-semibold">{formatMoneda(totalAlquiler)}</p>
          </div>
          <div className="rounded-lg bg-brand-50 p-3 text-sm">
            <p className="text-xs text-brand-500">Total servicios</p>
            <p className="font-semibold">{formatMoneda(totalServicios)}</p>
          </div>
          <div className="rounded-lg bg-brand-50 p-3 text-sm">
            <p className="text-xs text-brand-500">Total cochera</p>
            <p className="font-semibold">{formatMoneda(totalCochera)}</p>
          </div>
          <div className="rounded-lg bg-brand-50 p-3 text-sm">
            <p className="text-xs text-brand-500">Total abonado</p>
            <p className="font-semibold">{formatMoneda(totalAbonado)}</p>
          </div>
        </div>

        <button onClick={exportarCsv} disabled={filtradas.length === 0} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60">
          ⬇️ Descargar CSV
        </button>
      </div>
    </details>
  );
}
