export function PlaceholderModulo({
  titulo,
  moduloNumero,
}: {
  titulo: string;
  moduloNumero: number;
}) {
  return (
    <div className="rounded-xl border border-dashed border-brand-200 bg-white p-8 text-center">
      <p className="text-xs font-medium uppercase tracking-wide text-brand-400">
        Módulo {moduloNumero}
      </p>
      <h1 className="mt-1 text-lg font-semibold text-brand-900">{titulo}</h1>
      <p className="mt-2 text-sm text-brand-500">
        Todavía no implementado — llega en la próxima entrega (v2.00x).
      </p>
    </div>
  );
}
