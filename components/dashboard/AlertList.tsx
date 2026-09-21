import type { AlertaVencimiento, AlertaActualizacion } from "@/lib/dashboard/metrics";

function Aviso({
  tono,
  children,
}: {
  tono: "warning" | "info" | "success";
  children: React.ReactNode;
}) {
  const estilos = {
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    info: "bg-blue-50 text-blue-800 border-blue-200",
    success: "bg-green-50 text-green-800 border-green-200",
  } as const;

  return (
    <div className={`rounded-md border px-3 py-2 text-sm ${estilos[tono]}`}>{children}</div>
  );
}

/** Puerto de la columna "📅 Alertas de Vencimiento de Plazos" (app.py líneas 2603-2609). */
export function ListaAlertasVencimiento({ alertas }: { alertas: AlertaVencimiento[] }) {
  if (alertas.length === 0) {
    return <Aviso tono="success">✅ No hay contratos por vencer en los próximos 60 días.</Aviso>;
  }
  return (
    <div className="space-y-2">
      {alertas.map((a, i) => (
        <Aviso key={i} tono="warning">
          ⚠️ El contrato de <strong>{a.inquilino}</strong> ({a.aliasPropiedad}) vence en{" "}
          <strong>{a.diasParaVencer} días</strong> ({a.fechaTexto}).
        </Aviso>
      ))}
    </div>
  );
}

/** Puerto de la columna "📈 Alertas de Actualización de Valores" (app.py líneas 2611-2620). */
export function ListaAlertasActualizacion({ alertas }: { alertas: AlertaActualizacion[] }) {
  if (alertas.length === 0) {
    return (
      <Aviso tono="success">
        ✅ No hay actualizaciones de alquiler este mes ni el próximo.
      </Aviso>
    );
  }
  return (
    <div className="space-y-2">
      {alertas.map((a, i) => {
        const texto =
          a.urgencia === "fallback" ? (
            <>
              📈 Corresponde ajustar alquiler a <strong>{a.inquilino}</strong> (
              {a.aliasPropiedad}). Período: {a.frecuenciaLabel}.
            </>
          ) : (
            <>
              {a.urgencia === "este_mes" ? "📈 ESTE MES" : "📅 MES PRÓXIMO"} — Ajustar alquiler
              de <strong>{a.inquilino}</strong> ({a.aliasPropiedad}). Frecuencia:{" "}
              {a.frecuenciaLabel}. Próx. actualización: {a.proximaActualizacionTexto}.
            </>
          );
        return (
          <Aviso key={i} tono={a.urgencia === "este_mes" ? "warning" : "info"}>
            {texto}
          </Aviso>
        );
      })}
    </div>
  );
}
