"use client";

import { useState, useTransition } from "react";
import { registrarLiquidacion } from "@/app/(protected)/rendicion/actions";
import { formatMoneda } from "@/lib/format";
import type { ResumenRendicion } from "@/lib/rendicion/queries";

export function ResumenLiquidacion({
  propietarios,
  resumenInicial,
  propietarioInicial,
  periodoInicial,
}: {
  propietarios: string[];
  resumenInicial: ResumenRendicion | null;
  propietarioInicial: string;
  periodoInicial: string;
}) {
  const [propietario, setPropietario] = useState(propietarioInicial);
  const [periodo, setPeriodo] = useState(periodoInicial);
  const [montoLiquidado, setMontoLiquidado] = useState(resumenInicial?.montoALiquidar ?? 0);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [pendiente, startTransition] = useTransition();

  const resumen = resumenInicial;

  function handleCambio(nuevoPropietario: string, nuevoPeriodo: string) {
    const params = new URLSearchParams({ propietario: nuevoPropietario, periodo: nuevoPeriodo });
    window.location.href = `/rendicion?${params.toString()}`;
  }

  async function handleRegistrar() {
    if (!resumen) return;
    setMensaje(null);
    startTransition(async () => {
      const res = await registrarLiquidacion(resumen, montoLiquidado);
      setMensaje(res.ok ? "Liquidación registrada correctamente." : res.error ?? "Error al registrar.");
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <select
          value={propietario}
          onChange={(e) => handleCambio(e.target.value, periodo)}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          <option value="">Seleccionar propietario…</option>
          {propietarios.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          type="month"
          value={periodo}
          onChange={(e) => handleCambio(propietario, e.target.value)}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        />
      </div>

      {!resumen ? (
        <p className="text-sm text-brand-500">Seleccioná un propietario y período para ver el resumen.</p>
      ) : resumen.propiedades === 0 ? (
        <p className="text-sm text-brand-500">Este propietario no tiene propiedades cargadas.</p>
      ) : (
        <div className="space-y-4 rounded-lg border border-brand-100 bg-white p-5">
          <p className="text-sm text-brand-500">
            {resumen.propiedades} propiedad(es) — {resumen.propietario} — {resumen.periodoMes}
          </p>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metrica label="💰 Total Cobrado" valor={resumen.totalCobrado} />
            <Metrica label="🏢 Comisión (−)" valor={resumen.comision} />
            <Metrica label="📤 Neto a Rendir" valor={resumen.netoARendir} destacado />
            <Metrica label="↩️ Saldo Anterior" valor={resumen.saldoAnterior} />
          </div>

          <p className="text-xs text-brand-400">
            Informativo, no se descuenta del Neto a Rendir: Servicios {formatMoneda(resumen.servicios)} · Otros{" "}
            {formatMoneda(resumen.otros)}
          </p>

          {resumen.gastosRetencion.length > 0 && (
            <div className="rounded-md bg-amber-50 p-3 text-sm">
              <p className="mb-1 font-medium text-amber-800">
                Gastos a retener: {formatMoneda(resumen.montoRetencionGastos)}
              </p>
              <ul className="list-inside list-disc text-amber-700">
                {resumen.gastosRetencion.map((g) => (
                  <li key={g.id}>
                    {g.descripcion} — {formatMoneda(g.monto)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-lg bg-brand-50 p-3">
            <p className="text-sm">
              Monto a liquidar: <strong>{formatMoneda(resumen.montoALiquidar)}</strong>
            </p>
            <label className="mt-2 block max-w-xs text-sm">
              <span className="mb-1 block text-brand-700">Monto efectivamente liquidado</span>
              <input
                type="number"
                value={montoLiquidado}
                onChange={(e) => setMontoLiquidado(Number(e.target.value))}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
            {montoLiquidado !== resumen.montoALiquidar && (
              <p className="mt-1 text-xs text-amber-600">
                Diferencia de {formatMoneda(resumen.montoALiquidar - montoLiquidado)} queda como saldo pendiente para
                el próximo período.
              </p>
            )}
          </div>

          {mensaje && <p className="text-sm text-brand-600">{mensaje}</p>}

          <button
            onClick={handleRegistrar}
            disabled={pendiente}
            className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {pendiente ? "Registrando…" : "💾 Registrar Liquidación"}
          </button>
        </div>
      )}
    </div>
  );
}

function Metrica({ label, valor, destacado }: { label: string; valor: number; destacado?: boolean }) {
  return (
    <div>
      <p className="text-xs text-brand-500">{label}</p>
      <p className={`text-lg font-semibold ${destacado ? "text-brand-900" : "text-brand-700"}`}>{formatMoneda(valor)}</p>
    </div>
  );
}
