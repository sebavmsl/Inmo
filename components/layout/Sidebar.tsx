"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import type { Pestana } from "@/lib/auth/permissions";
import { logout } from "@/app/login/actions";
import { APP_VERSION } from "@/lib/version";

/**
 * Puerto del bloque "RENDERIZADO EFECTIVO: MENÚ LATERAL" de app.py
 * (líneas ~2153-2186). En vez de botones que cambian `pestana_activa` en
 * session_state, son <Link> a rutas reales — así cada pestaña tiene su
 * propia URL, se puede compartir/recargar, etc.
 */
export function Sidebar({
  pestanas,
  nombreEmpresa,
  username,
}: {
  pestanas: Pestana[];
  nombreEmpresa: string;
  username: string;
}) {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 flex-col border-r border-brand-100 bg-white">
      <div className="border-b border-brand-100 px-4 py-4">
        <p className="truncate text-sm font-semibold text-brand-900">{nombreEmpresa}</p>
        <p className="truncate text-xs text-brand-500">{username}</p>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {pestanas.map((p) => {
          const activa = pathname === p.href || pathname.startsWith(p.href + "/");
          return (
            <Link
              key={p.clave}
              href={p.href}
              className={clsx(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
                activa
                  ? "bg-brand-600 text-white"
                  : "text-brand-700 hover:bg-brand-50"
              )}
            >
              <span aria-hidden>{p.icono}</span>
              {p.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-brand-100 p-3">
        <form action={logout}>
          <button
            type="submit"
            className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-brand-600 hover:bg-brand-50"
          >
            Cerrar sesión
          </button>
        </form>
        <p className="mt-2 px-3 text-[11px] text-brand-300">{APP_VERSION}</p>
      </div>
    </aside>
  );
}
