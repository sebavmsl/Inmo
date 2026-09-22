import type { FilaDetalleRendicion } from "@/lib/rendicion/queries";
import { formatMoneda } from "@/lib/format";

/**
 * "Detalle de Recibos Incluidos" — puerto de app.py líneas 8419-8453.
 * Trazabilidad recibo a recibo: incluye, a modo informativo, los demás
 * conceptos cobrados al inquilino que no forman parte del neto del
 * propietario. Colapsado por defecto (a diferencia de v1, que lo
 * muestra siempre abierto) porque para "Todos los períodos" puede ser
 * una lista larga — mismo criterio ya usado en Historial de Pagos para
 * "Generar Reporte de Cobros".
 */
export function DetalleRecibosRendicion({ filas }: { filas: FilaDetalleRendicion[] }) {
  return (
    <details className="rounded-lg border border-brand-100 bg-white">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-brand-800">
        📋 Detalle de Recibos Incluidos ({filas.length})
      </summary>
      <div className="border-t border-brand-100 p-4">
        <p className="mb-3 text-xs text-brand-500">
          Cada fila es un recibo emitido. Incluye, a modo informativo, los demás conceptos cobrados al inquilino que no forman parte del neto del propietario.
        </p>
        {filas.length === 0 ? (
          <p className="text-sm text-brand-500">Sin recibos en este período.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-brand-100">
            <table className="w-full text-xs">
              <thead className="bg-brand-50 text-left font-medium uppercase text-brand-500">
                <tr>
                  <th className="px-2 py-1.5">Fecha</th>
                  <th className="px-2 py-1.5">Propiedad</th>
                  <th className="px-2 py-1.5">Inquilino</th>
                  <th className="px-2 py-1.5">Período</th>
                  <th className="px-2 py-1.5">Alquiler</th>
                  <th className="px-2 py-1.5">Cochera</th>
                  <th className="px-2 py-1.5">Expensas</th>
                  <th className="px-2 py-1.5">Comisión (−)</th>
                  <th className="px-2 py-1.5">Neto</th>
                  <th className="px-2 py-1.5">Imp. Inmob.</th>
                  <th className="px-2 py-1.5">Luz</th>
                  <th className="px-2 py-1.5">Gas</th>
                  <th className="px-2 py-1.5">Municip.</th>
                  <th className="px-2 py-1.5">OO.SS.</th>
                  <th className="px-2 py-1.5">Honorarios</th>
                  <th className="px-2 py-1.5">Garantía</th>
                  <th className="px-2 py-1.5">Concepto extra</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={`${f.propiedad}-${f.periodo}-${i}`} className="border-b border-brand-50">
                    <td className="whitespace-nowrap px-2 py-1.5">{new Date(f.fecha).toLocaleDateString("es-AR")}</td>
                    <td className="px-2 py-1.5">{f.propiedad}</td>
                    <td className="px-2 py-1.5">{f.inquilino}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{f.periodo}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.alquiler)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.cochera)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">
                      {formatMoneda(f.expensas)}
                      {f.expensasInformativas > 0 && <span className="text-brand-400"> (+{formatMoneda(f.expensasInformativas)} inf.)</span>}
                    </td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.comision)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5 font-medium">{formatMoneda(f.neto)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.impInmobiliario)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.edesal)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.gas)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.municipalidad)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.ooss)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.honorarios)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">{formatMoneda(f.garantia)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">
                      {f.conceptoExtra > 0 ? `${formatMoneda(f.conceptoExtra)}${f.conceptoExtraDesc ? ` (${f.conceptoExtraDesc})` : ""}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}
