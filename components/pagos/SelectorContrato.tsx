"use client";

import { useRouter } from "next/navigation";

interface OpcionContrato {
  codigo: string;
  aliasPropiedad: string;
  inquilino: string;
}

export function SelectorContrato({
  contratos,
  seleccionado,
}: {
  contratos: OpcionContrato[];
  seleccionado?: string;
}) {
  const router = useRouter();

  return (
    <select
      value={seleccionado ?? ""}
      onChange={(e) => router.push(e.target.value ? `/pagos?contrato=${e.target.value}` : "/pagos")}
      className="w-full max-w-md rounded-lg border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
    >
      <option value="">Seleccionar contrato…</option>
      {contratos.map((c) => (
        <option key={c.codigo} value={c.codigo}>
          {c.aliasPropiedad} — {c.inquilino} ({c.codigo})
        </option>
      ))}
    </select>
  );
}
