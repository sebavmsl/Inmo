import type { FilaPlanilla } from "@/lib/planilla/types";
import { FilaContrato } from "@/components/planilla/FilaContrato";

export function TablaCobranzas({ filas, soloLectura }: { filas: FilaPlanilla[]; soloLectura: boolean }) {
  const activos = filas.filter((f) => !f.estadoVencido);
  const pagaron = activos.filter((f) => f.pagado).length;
  const faltan = activos.length - pagaron;

  if (filas.length === 0) {
    return <p className="text-sm text-brand-500">No hay contratos para mostrar este mes.</p>;
  }

  return (
    <div>
      <div className="mb-3 flex gap-4 text-sm">
        <span className="text-green-700">✅ {pagaron} pagaron</span>
        <span className="text-amber-700">⏳ {faltan} faltan</span>
        <span className="text-brand-500">{activos.length} total</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-brand-100">
        <table className="w-full">
          <thead className="bg-brand-50 text-left text-xs font-medium uppercase text-brand-500">
            <tr>
              <th className="px-3 py-2"></th>
              <th className="px-3 py-2">Propiedad</th>
              <th className="px-3 py-2">Inquilino</th>
              <th className="px-3 py-2">Alquiler</th>
              <th className="px-3 py-2">Saldo</th>
              <th className="px-3 py-2">Expensas (WhatsApp)</th>
              <th className="px-3 py-2 text-center">✓</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {filas.map((fila) => (
              <FilaContrato key={fila.codigo} fila={fila} soloLectura={soloLectura} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex gap-4 text-xs text-brand-400">
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded bg-amber-50" /> Actualizar este mes
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded bg-blue-50" /> Actualizar mes próximo
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded bg-red-50" /> Renovar contrato
        </span>
      </div>
    </div>
  );
}
