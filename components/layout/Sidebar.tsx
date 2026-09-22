"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import type { Pestana } from "@/lib/auth/permissions";
import { logout } from "@/app/login/actions";
import { APP_VERSION } from "@/lib/version";
import { SelectorEmpresaActiva } from "@/components/layout/SelectorEmpresaActiva";

/** Preferencia puramente de UI (no afecta datos/permisos) — se guarda en localStorage, no en el servidor. */
const CLAVE_COLAPSADO = "sidebar_colapsado";

/**
 * Puerto del bloque "RENDERIZADO EFECTIVO: MENÚ LATERAL" de app.py
 * (líneas ~2153-2186). En vez de botones que cambian `pestana_activa` en
 * session_state, son <Link> a rutas reales — así cada pestaña tiene su
 * propia URL, se puede compartir/recargar, etc.
 *
 * Colapsable a "solo íconos" (V2.009): el estado vive en localStorage, no
 * en cookie — es una preferencia de pantalla, no de sesión/servidor, así
 * que no hace falta revalidar nada al cambiarlo. Arranca expandido en el
 * primer render (igual que el servidor) y recién después de montar se
 * ajusta a lo guardado, para no pelear con hydration.
 */
export function Sidebar({
  pestanas,
  nombreEmpresa,
  username,
  esSuperadmin,
  empresaIdActual,
  empresas,
}: {
  pestanas: Pestana[];
  nombreEmpresa: string;
  username: string;
  esSuperadmin: boolean;
  empresaIdActual: number | null;
  empresas: { id: number; nombreComercial: string }[];
}) {
  const pathname = usePathname();
  const [colapsado, setColapsado] = useState(false);

  useEffect(() => {
    if (window.localStorage.getItem(CLAVE_COLAPSADO) === "1") setColapsado(true);
  }, []);

  function guardarColapsado(valor: boolean) {
    setColapsado(valor);
    window.localStorage.setItem(CLAVE_COLAPSADO, valor ? "1" : "0");
  }

  return (
    <aside
      className={clsx(
        "flex flex-shrink-0 flex-col border-r border-brand-100 bg-white transition-[width] duration-150",
        colapsado ? "w-16" : "w-64"
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-brand-100 px-3 py-4">
        {!colapsado && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-brand-900">{nombreEmpresa}</p>
            <p className="truncate text-xs text-brand-500">{username}</p>
          </div>
        )}
        <button
          type="button"
          onClick={() => guardarColapsado(!colapsado)}
          title={colapsado ? "Expandir menú" : "Colapsar menú"}
          aria-label={colapsado ? "Expandir menú" : "Colapsar menú"}
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-brand-500 hover:bg-brand-50"
        >
          {colapsado ? "»" : "«"}
        </button>
      </div>

      {esSuperadmin && (
        <SelectorEmpresaActiva
          empresas={empresas}
          empresaIdActual={empresaIdActual}
          colapsado={colapsado}
          onExpandir={() => guardarColapsado(false)}
        />
      )}

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {pestanas.map((p) => {
          const activa = pathname === p.href || pathname.startsWith(p.href + "/");
          return (
            <Link
              key={p.clave}
              href={p.href}
              title={colapsado ? p.label : undefined}
              className={clsx(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
                colapsado && "justify-center px-2",
                activa
                  ? "bg-brand-600 text-white"
                  : "text-brand-700 hover:bg-brand-50"
              )}
            >
              <span aria-hidden>{p.icono}</span>
              {!colapsado && p.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-brand-100 p-3">
        <form action={logout}>
          <button
            type="submit"
            title={colapsado ? "Cerrar sesión" : undefined}
            className={clsx(
              "w-full rounded-lg px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50",
              colapsado ? "text-center" : "text-left"
            )}
          >
            {colapsado ? "⏻" : "Cerrar sesión"}
          </button>
        </form>
        {!colapsado && <p className="mt-2 px-3 text-[11px] text-brand-300">{APP_VERSION}</p>}
      </div>
    </aside>
  );
}
