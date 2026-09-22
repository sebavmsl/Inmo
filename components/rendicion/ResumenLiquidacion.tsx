"use client";

import { useState, useTransition } from "react";
import { registrarLiquidacion } from "@/app/(protected)/rendicion/actions";
import { formatMoneda } from "@/lib/format";
import type { ResumenRendicion, LiquidacionExistente } from "@/lib/rendicion/queries";

/**
 * Sección "💵 Liquidación" — solo tiene sentido para UN propietario +
 * UN período específicos (igual que v1, app.py línea 8469: con "Todos"
 * en cualquiera de los dos ni se muestra). El selector de propietario/
 * período ahora vive en SelectorRendicion, un nivel arriba — este
 * componente ya recibe la combinación específica resuelta.
 */
export function ResumenLiquidacion({
  resumen,
  liquidacionExistente,
}: {
  resumen: ResumenRendicion;
  liquidacionExistente: LiquidacionExistente | null;
}) {
  const [montoLiquidado, setMontoLiquidado] = useState(liquidacionExistente?.montoLiquidado ?? resumen.montoALiquidar);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [pendiente, startTransition] = useTransition();

  async function handleRegistrar() {
    setMensaje(null);
    startTransition(async () => {
      const res = await registrarLiquidacion(resumen, montoLiquidado);
      setMensaje(res.ok ? "Liquidación registrada correctamente." : res.error ?? "Error al registrar.");
    });
  }

  if (resumen.propiedades === 0) {
    return <p className="text-sm text-brand-500">Este propietario no tiene propiedades cargadas.</p>;
  }

  const saldoPendienteNuevo = resumen.montoALiquidar - montoLiquidado;
  // El PDF refleja lo que está guardado en la liquidación, así que se
  // habilita solo cuando ya hay una registrada para esta combinación
  // exacta — no alcanza con tener el resumen calculado en pantalla.
  const pdfHabilitado = liquidacionExistente !== null;

  return (
    <div className="space-y-4 rounded-lg border border-brand-100 bg-white p-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metrica label="↩️ Saldo Anterior" valor={resumen.saldoAnterior} />
        <Metrica label="🧾 Retención por Gastos (−)" valor={resumen.montoRetencionGastos} />
        <Metrica label="💵 Monto Total a Liquidar" valor={resumen.montoALiquidar} destacado />
        <div />
      </div>

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

      {liquidacionExistente && (
        <p className="text-xs text-brand-400">
          ℹ️ Ya hay una liquidación registrada para este período (el {new Date(liquidacionExistente.fechaLiquidacion).toLocaleString("es-AR")}, por{" "}
          {liquidacionExistente.registradoPor}) — podés corregirla y volver a guardar.
        </p>
      )}

      <div className="rounded-lg bg-brand-50 p-3">
        <label className="block max-w-xs text-sm">
          <span className="mb-1 block text-brand-700">Monto efectivamente liquidado</span>
          <input
            type="number"
            value={montoLiquidado}
            onChange={(e) => setMontoLiquidado(Number(e.target.value))}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
        {Math.abs(saldoPendienteNuevo) > 0.01 ? (
          <p className="mt-1 text-xs text-amber-600">
            {saldoPendienteNuevo > 0
              ? `Queda un saldo pendiente a favor del propietario de ${formatMoneda(saldoPendienteNuevo)}, que se arrastra al próximo período.`
              : `Se liquidó ${formatMoneda(Math.abs(saldoPendienteNuevo))} de más — queda a favor de la inmobiliaria para el próximo período.`}
          </p>
        ) : (
          <p className="mt-1 text-xs text-green-700">✅ El monto liquidado coincide con lo que corresponde. Sin saldo pendiente.</p>
        )}
      </div>

      {mensaje && <p className="text-sm text-brand-600">{mensaje}</p>}

      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleRegistrar}
          disabled={pendiente}
          className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-60"
        >
          {pendiente ? "Registrando…" : "💾 Registrar Liquidación"}
        </button>

        {pdfHabilitado ? (
          <a
            href={`/api/rendicion/pdf?propietario=${encodeURIComponent(resumen.propietario)}&periodo=${encodeURIComponent(resumen.periodoMes)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-brand-200 px-5 py-2.5 font-medium text-brand-700 transition hover:bg-brand-50"
          >
            📄 Descargar PDF de Rendición
          </a>
        ) : (
          <button
            disabled
            title="Primero registrá la liquidación."
            className="cursor-not-allowed rounded-lg border border-brand-100 px-5 py-2.5 font-medium text-brand-300"
          >
            📄 Descargar PDF de Rendición
          </button>
        )}
      </div>
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
