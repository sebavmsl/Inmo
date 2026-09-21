import { redirect } from "next/navigation";
import { requireInquilinoContratos } from "@/lib/inquilino/session";
import { createClient } from "@/lib/supabase/server";
import { formatMoneda } from "@/lib/format";

export default async function MiCuentaPage({
  searchParams,
}: {
  searchParams: Promise<{ contrato?: string }>;
}) {
  const contratos = await requireInquilinoContratos();
  const { contrato: codigoElegido } = await searchParams;

  // requireInquilinoContratos() ya garantiza contratos.length > 0 (redirige
  // si está vacío) — este chequeo es solo para que TypeScript lo sepa
  // también (con noUncheckedIndexedAccess, contratos[0] tipa como
  // "T | undefined" aunque en la práctica nunca lo sea acá).
  const primero = contratos[0];
  if (!primero) redirect("/portal/login");
  const seleccionado = contratos.find((c) => c.codigoContrato === codigoElegido) ?? primero;

  const supabase = await createClient();
  const { data: contratoDetalle } = await supabase
    .from("contratos")
    .select("saldo_actual, fin_contrato, alquiler, alquiler_calculado")
    .eq("codigo", seleccionado.codigoContrato)
    .single();

  const { data: pagos } = await supabase
    .from("pagos_historial")
    .select("fecha, periodo, monto_abonado, nro_comprobante, tipo_pago")
    .eq("codigo_contrato", seleccionado.codigoContrato)
    .order("fecha", { ascending: false })
    .limit(12);

  const saldo = contratoDetalle?.saldo_actual ?? 0;
  const alquilerVigente = contratoDetalle?.alquiler_calculado ?? contratoDetalle?.alquiler ?? 0;

  return (
    <div className="space-y-4">
      {contratos.length > 1 && (
        <div className="flex gap-2">
          {contratos.map((c) => (
            <a
              key={c.codigoContrato}
              href={`/portal/mi-cuenta?contrato=${c.codigoContrato}`}
              className={`rounded-full px-3 py-1 text-xs ${
                c.codigoContrato === seleccionado.codigoContrato ? "bg-brand-600 text-white" : "bg-white text-brand-600"
              }`}
            >
              {c.nombreEmpresa} — {c.aliasPropiedad}
            </a>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-brand-100 bg-white p-5">
        <h1 className="mb-1 text-lg font-semibold text-brand-900">{seleccionado.aliasPropiedad}</h1>
        <p className="mb-4 text-sm text-brand-500">{seleccionado.nombreEmpresa}</p>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-brand-500">Alquiler vigente</p>
            <p className="text-lg font-semibold text-brand-900">{formatMoneda(alquilerVigente)}</p>
          </div>
          <div>
            <p className="text-xs text-brand-500">Saldo</p>
            <p className={`text-lg font-semibold ${saldo > 0 ? "text-amber-700" : "text-green-700"}`}>
              {formatMoneda(Math.abs(saldo))} {saldo < 0 && "(a favor)"}
            </p>
          </div>
          <div>
            <p className="text-xs text-brand-500">Fin de contrato</p>
            <p className="text-lg font-semibold text-brand-900">{contratoDetalle?.fin_contrato ?? "-"}</p>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-brand-100 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-brand-800">Últimos pagos</h2>
        {!pagos || pagos.length === 0 ? (
          <p className="text-sm text-brand-500">Todavía no hay pagos registrados.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-brand-400">
              <tr>
                <th className="py-1">Fecha</th>
                <th className="py-1">Período</th>
                <th className="py-1">Tipo</th>
                <th className="py-1">Monto</th>
                <th className="py-1">Comprobante</th>
              </tr>
            </thead>
            <tbody>
              {pagos.map((p, i) => (
                <tr key={i} className="border-t border-brand-50">
                  <td className="py-1.5">{new Date(p.fecha).toLocaleDateString("es-AR")}</td>
                  <td className="py-1.5">{p.periodo}</td>
                  <td className="py-1.5">{p.tipo_pago}</td>
                  <td className="py-1.5">{formatMoneda(p.monto_abonado)}</td>
                  <td className="py-1.5">
                    {p.nro_comprobante && (
                      <a href={`/api/pagos/comprobante-pdf?comprobante=${p.nro_comprobante}`} className="text-brand-600 hover:underline">
                        Descargar
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
