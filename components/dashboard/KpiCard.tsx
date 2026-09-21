import clsx from "clsx";

export function KpiCard({
  titulo,
  valor,
  detalle,
  tono = "neutral",
}: {
  titulo: string;
  valor: string | number;
  detalle?: string;
  tono?: "neutral" | "alerta" | "ok";
}) {
  return (
    <div className="rounded-xl border border-brand-100 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-brand-500">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold text-brand-900">{valor}</p>
      {detalle && (
        <p
          className={clsx(
            "mt-1 text-xs font-medium",
            tono === "alerta" && "text-amber-600",
            tono === "ok" && "text-green-600",
            tono === "neutral" && "text-brand-400"
          )}
        >
          {detalle}
        </p>
      )}
    </div>
  );
}
