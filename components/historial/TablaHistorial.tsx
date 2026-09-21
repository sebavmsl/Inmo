import type { FilaHistorial } from "@/lib/historial/queries";
import { formatMoneda } from "@/lib/format";

export function TablaHistorial({ filas }: { filas: FilaHistorial[] }) {
  if (filas.length === 0) {
    return <p className="text-sm text-brand-500">No hay pagos registrados todavía.</p>;
  }

  const totalAbonado = filas.reduce((acc, f) => acc + f.montoAbonado, 0);
  const totalRetencion = filas.reduce((acc, f) => acc + f.retencionAgencia, 0);

  return (
    <div>
      <div className="mb-3 flex gap-4 text-sm text-brand-600">
        <span>Total abonado: <strong>{formatMoneda(totalAbonado)}</strong></span>
        <span>Retención agencia total: <strong>{formatMoneda(totalRetencion)}</strong></span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-brand-100">
        <table className="w-full text-sm">
          <thead className="bg-brand-50 text-left text-xs font-medium uppercase text-brand-500">
            <tr>
              <th className="px-3 py-2">Comprobante</th>
              <th className="px-3 py-2">Fecha</th>
              <th className="px-3 py-2">Propiedad</th>
              <th className="px-3 py-2">Inquilino</th>
              <th className="px-3 py-2">Período</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Abonado</th>
              <th className="px-3 py-2">Saldo</th>
              <th className="px-3 py-2">Retención Agencia</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={f.nroComprobante ?? i} className="border-b border-brand-50">
                <td className="px-3 py-2">{f.nroComprobante ?? "-"}</td>
                <td className="px-3 py-2">{new Date(f.fecha).toLocaleDateString("es-AR")}</td>
                <td className="px-3 py-2">{f.propiedad}</td>
                <td className="px-3 py-2">{f.inquilino}</td>
                <td className="px-3 py-2">{f.periodo}</td>
                <td className="px-3 py-2">{f.tipoPago}</td>
                <td className="px-3 py-2">{formatMoneda(f.montoAbonado)}</td>
                <td className="px-3 py-2">{f.saldoPendiente > 0 ? formatMoneda(f.saldoPendiente) : "—"}</td>
                <td className="px-3 py-2">{formatMoneda(f.retencionAgencia)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
