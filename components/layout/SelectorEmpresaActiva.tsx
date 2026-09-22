"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { seleccionarEmpresaActiva } from "@/app/(protected)/actions";

const VALOR_SIN_EMPRESA = "__sin_empresa__";

interface OpcionEmpresa {
  id: number;
  nombreComercial: string;
}

/**
 * Selector global de empresa para superadmin — siempre visible arriba
 * (en el Sidebar, presente en todos los módulos protegidos, ver
 * app/(protected)/layout.tsx). superadmin no tiene empresa propia: por
 * defecto "trabaja" con el grupo sin empresa asignada, y acá puede
 * cambiar a una empresa puntual — la elección queda guardada (cookie) y
 * afecta lectura Y escritura en todos los módulos, ver
 * lib/auth/session.ts (getSessionProfile).
 */
export function SelectorEmpresaActiva({
  empresas,
  empresaIdActual,
  colapsado = false,
  onExpandir,
}: {
  empresas: OpcionEmpresa[];
  empresaIdActual: number | null;
  /** true cuando el Sidebar está en modo "solo íconos" (ver Sidebar.tsx). */
  colapsado?: boolean;
  /** Se llama al hacer clic en la versión colapsada, para expandir el Sidebar y poder elegir. */
  onExpandir?: () => void;
}) {
  const router = useRouter();
  const [pendiente, iniciarTransicion] = useTransition();
  const [valorLocal, setValorLocal] = useState(empresaIdActual === null ? VALOR_SIN_EMPRESA : String(empresaIdActual));

  function onChange(valor: string) {
    setValorLocal(valor);
    iniciarTransicion(async () => {
      await seleccionarEmpresaActiva(valor === VALOR_SIN_EMPRESA ? null : Number(valor));
      router.refresh();
    });
  }

  const nombreActual =
    empresaIdActual === null
      ? "Sin empresa asignada (huérfanos)"
      : empresas.find((e) => e.id === empresaIdActual)?.nombreComercial ?? "Empresa";

  // Con el Sidebar colapsado no entra el <select> completo (el ancho es
  // solo el del ícono) — en vez de armar un popover, mostramos un botón
  // chico que expande el Sidebar para poder elegir con el select de
  // siempre. El nombre de la empresa activa queda como tooltip (title).
  if (colapsado) {
    return (
      <div className="flex justify-center border-b border-brand-100 bg-amber-50/60 px-2 py-2">
        <button
          type="button"
          onClick={onExpandir}
          title={`Trabajando como: ${nombreActual} (clic para cambiar)`}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-base text-amber-700 hover:bg-amber-100"
        >
          🏢
        </button>
      </div>
    );
  }

  return (
    <div className="border-b border-brand-100 bg-amber-50/60 px-3 py-2">
      <label className="block text-[11px] font-medium uppercase tracking-wide text-amber-700">
        Trabajando como
      </label>
      <select
        value={valorLocal}
        disabled={pendiente}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-amber-200 bg-white px-2 py-1 text-xs text-brand-800 disabled:opacity-60"
      >
        <option value={VALOR_SIN_EMPRESA}>Sin empresa asignada (huérfanos)</option>
        {empresas.map((e) => (
          <option key={e.id} value={e.id}>
            {e.nombreComercial}
          </option>
        ))}
      </select>
    </div>
  );
}
