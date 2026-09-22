"use client";

import { useState } from "react";
import { actualizarConfiguracionEmpresa } from "@/app/(protected)/panel-gestion/actions";

interface Props {
  empresaId: number;
  actualizarAlquilerAuto: boolean;
  whatsappHabilitado: boolean;
  timeoutInactividadMinutos: number;
}

/**
 * Toggles de configuración por empresa — las 3 columnas ya existían en
 * configuraciones_empresa (creadas en el alta de empresa o agregadas
 * con default, ver 0015_inactividad.sql), pero hasta ahora no había
 * forma de editarlas después desde la UI.
 */
export function Configuraciones({
  empresaId,
  actualizarAlquilerAuto,
  whatsappHabilitado,
  timeoutInactividadMinutos,
}: Props) {
  const [alquilerAuto, setAlquilerAuto] = useState(actualizarAlquilerAuto);
  const [whatsapp, setWhatsapp] = useState(whatsappHabilitado);
  const [timeoutMin, setTimeoutMin] = useState(timeoutInactividadMinutos);
  const [guardando, setGuardando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function toggle(campo: "actualizar_alquiler_auto" | "whatsapp_habilitado", valorNuevo: boolean) {
    setGuardando(campo);
    setError(null);
    const res = await actualizarConfiguracionEmpresa(empresaId, { [campo]: valorNuevo });
    setGuardando(null);
    if (!res.ok) {
      setError(res.error ?? "Error al guardar.");
      return;
    }
    if (campo === "actualizar_alquiler_auto") setAlquilerAuto(valorNuevo);
    else setWhatsapp(valorNuevo);
  }

  async function guardarTimeout() {
    setGuardando("timeout_inactividad_minutos");
    setError(null);
    const res = await actualizarConfiguracionEmpresa(empresaId, { timeout_inactividad_minutos: timeoutMin });
    setGuardando(null);
    if (!res.ok) setError(res.error ?? "Error al guardar.");
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🔧 Configuración de la empresa</h2>

      <label className="flex items-center justify-between gap-3 text-sm">
        <span>
          Actualización automática del alquiler por índice
          <span className="block text-xs text-brand-400">Aplica el índice pactado sin confirmación manual cada mes.</span>
        </span>
        <input
          type="checkbox"
          checked={alquilerAuto}
          disabled={guardando === "actualizar_alquiler_auto"}
          onChange={(e) => toggle("actualizar_alquiler_auto", e.target.checked)}
        />
      </label>

      <label className="flex items-center justify-between gap-3 text-sm">
        <span>
          WhatsApp habilitado
          <span className="block text-xs text-brand-400">Muestra los botones de envío por WhatsApp a quienes tengan el permiso.</span>
        </span>
        <input
          type="checkbox"
          checked={whatsapp}
          disabled={guardando === "whatsapp_habilitado"}
          onChange={(e) => toggle("whatsapp_habilitado", e.target.checked)}
        />
      </label>

      <div className="flex items-center justify-between gap-3 text-sm">
        <span>
          Cierre de sesión por inactividad
          <span className="block text-xs text-brand-400">
            Minutos sin actividad antes de cerrar la sesión sola (con aviso previo de 1 minuto).
          </span>
        </span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={1440}
            value={timeoutMin}
            onChange={(e) => setTimeoutMin(Number(e.target.value))}
            className="w-20 rounded border border-brand-100 px-2 py-1 text-sm"
          />
          <button
            onClick={guardarTimeout}
            disabled={guardando === "timeout_inactividad_minutos" || timeoutMin === timeoutInactividadMinutos}
            className="rounded border border-brand-200 px-2 py-1 text-xs text-brand-600 hover:bg-brand-50 disabled:opacity-50"
          >
            Guardar
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
