"use client";

import { useEffect, useState } from "react";
import { registrarPresencia, quitarPresencia, listarPresencia, type EditorPresente, type TablaConLock } from "@/lib/concurrencia/queries";

const INTERVALO_HEARTBEAT_MS = 20_000;

/**
 * Hook para cualquier formulario de edición: mientras está montado,
 * avisa presencia cada 20s (heartbeat) y devuelve quién más está
 * editando el mismo registro — ya filtrado del lado del servidor (ver
 * lib/concurrencia/queries.ts): nunca incluye al propio usuario ni a
 * superadmin.
 *
 * `registroId === null` (p.ej. un formulario de ALTA, que todavía no
 * tiene id) desactiva el hook sin condicionales en cada llamador.
 */
export function usePresencia(tabla: TablaConLock, registroId: string | null): EditorPresente[] {
  const [otrosEditando, setOtrosEditando] = useState<EditorPresente[]>([]);

  useEffect(() => {
    if (!registroId) {
      setOtrosEditando([]);
      return;
    }

    let cancelado = false;

    async function latido() {
      await registrarPresencia(tabla, registroId as string);
      const otros = await listarPresencia(tabla, registroId as string);
      if (!cancelado) setOtrosEditando(otros);
    }

    latido();
    const intervalo = setInterval(latido, INTERVALO_HEARTBEAT_MS);

    return () => {
      cancelado = true;
      clearInterval(intervalo);
      quitarPresencia(tabla, registroId as string);
    };
  }, [tabla, registroId]);

  return otrosEditando;
}
