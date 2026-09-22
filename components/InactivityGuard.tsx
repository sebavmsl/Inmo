"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

/** Avisa este tanto ANTES del cierre real (ver docs/DESIGN_LOG.md, "Aviso previo + cierre automático"). */
const AVISO_SEGUNDOS_ANTES = 60;
/** No resetear el timer ni pingear el servidor en CADA evento de mouse/teclado — alcanza con una vez cada tanto. */
const THROTTLE_ACTIVIDAD_MS = 5_000;
/** Cada cuánto se renueva la cookie de actividad del lado del servidor (capa 2) mientras hay uso real. */
const THROTTLE_PING_MS = 60_000;
const EVENTOS_ACTIVIDAD = ["mousedown", "mousemove", "keydown", "scroll", "touchstart"] as const;

/**
 * Cierre de sesión por inactividad — capa 1 (cliente). Cualquier
 * interacción con la página cuenta como actividad (regla confirmada).
 * A los (timeoutMinutos - 1 min) sin actividad, avisa con un modal y un
 * countdown; si nadie hace nada, a los timeoutMinutos exactos cierra la
 * sesión sola. "Seguir conectado" reinicia el conteo.
 *
 * También manda un ping al servidor (throttleado) para que la capa 2
 * (middleware, ver lib/supabase/middleware.ts) sepa cuál fue la última
 * actividad real, por si este componente deja de correr (pestaña
 * dormida, navegador cerrado) — así la sesión igual se corta en el
 * próximo request, no solo cuando el JS del cliente llega a avisar.
 */
export function InactivityGuard({ timeoutMinutos }: { timeoutMinutos: number }) {
  const pathname = usePathname();
  const [avisoVisible, setAvisoVisible] = useState(false);
  const [segundosRestantes, setSegundosRestantes] = useState(AVISO_SEGUNDOS_ANTES);

  const timerAvisoRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerLogoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerCountdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ultimoPingRef = useRef(0);
  const ultimoResetRef = useRef(0);

  const irACerrarSesion = useCallback(() => {
    window.location.href = `/auth/cerrar-por-inactividad?volver=${encodeURIComponent(pathname)}`;
  }, [pathname]);

  const pingActividad = useCallback(() => {
    fetch("/api/actividad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timeoutMinutos }),
      keepalive: true,
    }).catch(() => {
      // Si falla el ping no pasa nada grave: la capa 2 es defensa en
      // profundidad, no la única línea — la capa 1 (este componente)
      // igual va a cerrar la sesión sola si sigue sin haber actividad.
    });
  }, [timeoutMinutos]);

  const limpiarTimers = useCallback(() => {
    if (timerAvisoRef.current) clearTimeout(timerAvisoRef.current);
    if (timerLogoutRef.current) clearTimeout(timerLogoutRef.current);
    if (timerCountdownRef.current) clearInterval(timerCountdownRef.current);
  }, []);

  const iniciarTimers = useCallback(() => {
    limpiarTimers();
    const totalMs = timeoutMinutos * 60_000;
    const msHastaAviso = Math.max(totalMs - AVISO_SEGUNDOS_ANTES * 1000, 0);

    timerAvisoRef.current = setTimeout(() => {
      setAvisoVisible(true);
      setSegundosRestantes(AVISO_SEGUNDOS_ANTES);
      timerCountdownRef.current = setInterval(() => {
        setSegundosRestantes((s) => Math.max(s - 1, 0));
      }, 1000);
    }, msHastaAviso);

    timerLogoutRef.current = setTimeout(irACerrarSesion, totalMs);
  }, [timeoutMinutos, limpiarTimers, irACerrarSesion]);

  const registrarActividad = useCallback(() => {
    if (avisoVisible) return; // mientras el aviso está visible, solo "Seguir conectado" cuenta

    const ahora = Date.now();
    if (ahora - ultimoResetRef.current > THROTTLE_ACTIVIDAD_MS) {
      ultimoResetRef.current = ahora;
      iniciarTimers();
    }
    if (ahora - ultimoPingRef.current > THROTTLE_PING_MS) {
      ultimoPingRef.current = ahora;
      pingActividad();
    }
  }, [avisoVisible, iniciarTimers, pingActividad]);

  function seguirConectado() {
    setAvisoVisible(false);
    pingActividad();
    iniciarTimers();
  }

  // Arranque + limpieza de timers al montar/desmontar (una sola vez).
  useEffect(() => {
    iniciarTimers();
    pingActividad();
    return limpiarTimers;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeoutMinutos]);

  // Listeners de actividad — se re-suscriben si registrarActividad
  // cambia de identidad (depende de avisoVisible), para que dejen de
  // resetear timers mientras el modal de aviso está abierto.
  useEffect(() => {
    EVENTOS_ACTIVIDAD.forEach((ev) => window.addEventListener(ev, registrarActividad, { passive: true }));
    return () => {
      EVENTOS_ACTIVIDAD.forEach((ev) => window.removeEventListener(ev, registrarActividad));
    };
  }, [registrarActividad]);

  if (!avisoVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 text-center shadow-xl">
        <h2 className="mb-2 text-base font-semibold text-brand-900">¿Seguís ahí?</h2>
        <p className="mb-4 text-sm text-brand-600">
          Por inactividad, la sesión se va a cerrar en <span className="font-semibold">{segundosRestantes}s</span>.
        </p>
        <button
          onClick={seguirConectado}
          className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Seguir conectado
        </button>
      </div>
    </div>
  );
}
