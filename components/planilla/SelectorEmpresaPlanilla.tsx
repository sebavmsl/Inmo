"use client";

import { useRouter } from "next/navigation";

const VALOR_SIN_EMPRESA = "__sin_empresa__";

interface OpcionEmpresa {
  id: number;
  nombreComercial: string;
}

/**
 * Solo para superadmin (ver Planilla page.tsx). superadmin no tiene
 * `empresa_id` propio, así que por defecto (sin query param `?empresa=`)
 * se muestran los contratos sin empresa asignada — nunca "todas mezcladas"
 * — y este desplegable permite pasar a ver una inmobiliaria puntual.
 */
export function SelectorEmpresaPlanilla({
  empresas,
  seleccionado,
}: {
  empresas: OpcionEmpresa[];
  seleccionado: number | null;
}) {
  const router = useRouter();

  return (
    <label className="flex items-center gap-2 text-sm text-brand-700">
      <span className="whitespace-nowrap font-medium">Empresa:</span>
      <select
        value={seleccionado === null ? VALOR_SIN_EMPRESA : String(seleccionado)}
        onChange={(e) => {
          const valor = e.target.value;
          router.push(valor === VALOR_SIN_EMPRESA ? "/planilla" : `/planilla?empresa=${valor}`);
        }}
        className="rounded-lg border border-brand-200 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
      >
        <option value={VALOR_SIN_EMPRESA}>Sin empresa asignada (huérfanos)</option>
        {empresas.map((e) => (
          <option key={e.id} value={e.id}>
            {e.nombreComercial}
          </option>
        ))}
      </select>
    </label>
  );
}
