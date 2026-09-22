import type { FilaHistorial } from "@/lib/historial/queries";
import { formatMoneda } from "@/lib/format";

function fmtUsd(valor: number): string {
  return valor > 0 ? `U$S ${valor.toLocaleString("es-AR", { minimumFractionDigits: 2 })}` : "—";
}

/**
 * Ampliación de esta sesión (antes solo tenía 9 columnas): paridad con
 * el desglose completo de `_cached_historial_pagos` de v1 (app.py
 * líneas 1587-1645 y tabla de línea 5178) — domicilio vía join,
 * desglose de servicios, honorarios/garantía/concepto extra, USD por
 * concepto y descarga directa del comprobante de cada fila (reusa
 * /api/pagos/comprobante-pdf, ya blindado para staff e inquilino —
 * cumple el rol de "Reimprimir Comprobante" de v1 sin necesitar una
 * pantalla de selección aparte).
 */
export function TablaHistorial({ filas }: { filas: FilaHistorial[] }) {
  if (filas.length === 0) {
    return <p className="text-sm text-brand-500">No hay pagos registrados todavía.</p>;
  }

  const totalAlquiler = filas.reduce((acc, f) => acc + f.montoAlquiler, 0);
  const totalServicios = filas.reduce((acc, f) => acc + f.montoServicios, 0);
  const totalAbonado = filas.reduce((acc, f) => acc + f.montoAbonado, 0);
  const totalRetencion = filas.reduce((acc, f) => acc + f.retencionAgencia, 0);

  return (
    <div>
      <p className="mb-2 text-xs text-brand-400">
        Los valores en USD se calculan con la cotización registrada al momento de cada cobro.
      </p>

      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Total alquiler</p>
          <p className="font-semibold">{formatMoneda(totalAlquiler)}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Total servicios</p>
          <p className="font-semibold">{formatMoneda(totalServicios)}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Total abonado</p>
          <p className="font-semibold">{formatMoneda(totalAbonado)}</p>
        </div>
        <div className="rounded-lg bg-brand-50 p-3 text-sm">
          <p className="text-xs text-brand-500">Retención agencia total</p>
          <p className="font-semibold">{formatMoneda(totalRetencion)}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-brand-100">
        <table className="w-full text-xs">
          <thead className="bg-brand-50 text-left font-medium uppercase text-brand-500">
            <tr>
              <th className="px-2 py-1.5">Comprobante</th>
              <th className="px-2 py-1.5">Fecha</th>
              <th className="px-2 py-1.5">Mes/Año</th>
              <th className="px-2 py-1.5">Propiedad</th>
              <th className="px-2 py-1.5">Domicilio</th>
              <th className="px-2 py-1.5">Inquilino</th>
              <th className="px-2 py-1.5">Período</th>
              <th className="px-2 py-1.5">Alquiler</th>
              <th className="px-2 py-1.5">Expensas</th>
              <th className="px-2 py-1.5">Cochera</th>
              <th className="px-2 py-1.5">Imp. Inmob.</th>
              <th className="px-2 py-1.5">Luz</th>
              <th className="px-2 py-1.5">Gas</th>
              <th className="px-2 py-1.5">Municip.</th>
              <th className="px-2 py-1.5">OO.SS.</th>
              <th className="px-2 py-1.5">Servicios</th>
              <th className="px-2 py-1.5">Honorarios</th>
              <th className="px-2 py-1.5">Garantía</th>
              <th className="px-2 py-1.5">Concepto extra</th>
              <th className="px-2 py-1.5">Abonado</th>
              <th className="px-2 py-1.5">Saldo</th>
              <th className="px-2 py-1.5">Retención Ag.</th>
              <th className="px-2 py-1.5">Cotiz. USD</th>
              <th className="px-2 py-1.5">Alquiler USD</th>
              <th className="px-2 py-1.5">Método</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={f.nroComprobante ?? i} className="border-b border-brand-50">
                <td className="whitespace-nowrap px-2 py-1.5">
                  {f.nroComprobante ? (
                    <a
                      href={`/api/pagos/comprobante-pdf?comprobante=${encodeURIComponent(f.nroComprobante)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-600 underline hover:text-brand-700"
                      title="Descargar / reimprimir comprobante"
                    >
                      {f.nroComprobante}
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="whitespace-nowrap px-2 py-1.5">{new Date(f.fecha).toLocaleDateString("es-AR")}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{f.mesAnio || "-"}</td>
                <td className="px-2 py-1.5">{f.propiedad}</td>
                <td className="px-2 py-1.5">{f.domicilio}</td>
                <td className="px-2 py-1.5">{f.inquilino}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{f.periodo}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoAlquiler)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoExpensas)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoCochera)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoImpInmobiliario)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoEdesal)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoGas)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoMunicipalidad)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoOoss)}</td>
                <td className="whitespace-nowrap px-2 py-1.5 font-medium">{formatMoneda(f.montoServicios)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoHonorarios)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.montoGarantia)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">
                  {f.montoConceptoExtra > 0 ? `${formatMoneda(f.montoConceptoExtra)}${f.conceptoExtraDesc ? ` (${f.conceptoExtraDesc})` : ""}` : "—"}
                </td>
                <td className="whitespace-nowrap px-2 py-1.5 font-medium">{formatMoneda(f.montoAbonado)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{f.saldoPendiente > 0 ? formatMoneda(f.saldoPendiente) : "—"}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.retencionAgencia)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{f.cotizacionUsd ? f.cotizacionUsd.toLocaleString("es-AR") : "—"}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{fmtUsd(f.alquilerUsd)}</td>
                <td className="whitespace-nowrap px-2 py-1.5">{f.metodoPago ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
