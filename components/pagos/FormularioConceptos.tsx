"use client";

import { useState, useMemo } from "react";
import { impactarCobro, type ConceptosPago } from "@/app/(protected)/pagos/actions";
import { enviarComprobanteWhatsapp } from "@/lib/whatsapp/comprobante";
import { calcularSaldoNuevo } from "@/lib/pagos/calculo-saldo";
import { CampoCotizacionUsd } from "@/components/cotizacion/CampoCotizacionUsd";
import { formatMoneda } from "@/lib/format";
import type { ContratoParaPago } from "@/lib/pagos/queries";
import type { TipoPago } from "@/lib/types/database.types";

const TIPOS_PAGO: TipoPago[] = ["Normal", "Complemento", "Corrección"];

export function FormularioConceptos({ contrato, periodoSugerido }: { contrato: ContratoParaPago; periodoSugerido: string }) {
  const [tipoPago, setTipoPago] = useState<TipoPago>("Normal");
  const [periodo, setPeriodo] = useState(periodoSugerido);
  const [conceptos, setConceptos] = useState<ConceptosPago>({
    alquiler: contrato.alquilerSugerido,
    expensas: contrato.ultimosConceptos.expensas,
    edesal: contrato.ultimosConceptos.edesal,
    gas: contrato.ultimosConceptos.gas,
    municipalidad: contrato.ultimosConceptos.municipalidad,
    cochera: contrato.ultimosConceptos.cochera,
    ooss: contrato.ultimosConceptos.ooss,
    impInmobiliario: contrato.ultimosConceptos.impInmobiliario,
    honorarios: contrato.honorarios.sugeridaPorCuota,
    garantia: contrato.garantia.sugeridaPorCuota,
    conceptoExtra: 0,
  });
  const [diferenciaCorreccion, setDiferenciaCorreccion] = useState(0);
  const [cotizacionUsd, setCotizacionUsd] = useState(0);
  const [montoAbonado, setMontoAbonado] = useState(0);
  const [metodoPago, setMetodoPago] = useState("Transferencia Bancaria");
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; mensaje: string; nroComprobante?: string } | null>(null);
  const [enviandoWa, setEnviandoWa] = useState(false);
  const [mensajeWa, setMensajeWa] = useState<string | null>(null);

  async function handleEnviarWhatsapp() {
    if (!resultado?.nroComprobante) return;
    setEnviandoWa(true);
    setMensajeWa(null);
    const res = await enviarComprobanteWhatsapp(resultado.nroComprobante);
    setMensajeWa(res.ok ? "Enviado por WhatsApp ✅" : res.error ?? "Error al enviar.");
    setEnviandoWa(false);
  }

  const totalACubrir = useMemo(() => {
    if (tipoPago === "Corrección") return diferenciaCorreccion;
    const suma = Object.values(conceptos).reduce((a, b) => a + b, 0);
    return tipoPago === "Normal" ? suma : 0; // Complemento no agrega cargos nuevos
  }, [tipoPago, conceptos, diferenciaCorreccion]);

  const previa = useMemo(
    () =>
      calcularSaldoNuevo({
        tipoPago,
        saldoActualAntes: contrato.saldoActual,
        conceptos: tipoPago === "Normal" ? conceptos : null,
        diferenciaCorreccion: tipoPago === "Corrección" ? diferenciaCorreccion : null,
        montoAbonado,
        honorariosPct: contrato.honorariosPct,
      }),
    [tipoPago, conceptos, diferenciaCorreccion, montoAbonado, contrato]
  );

  function setConcepto<K extends keyof ConceptosPago>(campo: K, valor: number) {
    setConceptos((prev) => ({ ...prev, [campo]: valor }));
  }

  async function handleSubmit() {
    setEnviando(true);
    setResultado(null);
    const res = await impactarCobro({
      codigoContrato: contrato.codigo,
      tipoPago,
      periodo,
      conceptos: tipoPago === "Normal" ? conceptos : null,
      diferenciaCorreccion: tipoPago === "Corrección" ? diferenciaCorreccion : null,
      montoAbonado,
      metodoPago,
      comentario,
      cotizacionUsd: cotizacionUsd || null,
    });
    setEnviando(false);
    setResultado(
      res.ok
        ? { ok: true, mensaje: `Cobro registrado. Comprobante ${res.nroComprobante}.`, nroComprobante: res.nroComprobante }
        : { ok: false, mensaje: res.error ?? "Error al registrar el cobro." }
    );
  }

  const campoInput = (label: string, campo: keyof ConceptosPago) => (
    <label className="block text-sm">
      <span className="mb-1 block text-brand-700">{label}</span>
      <input
        type="number"
        value={conceptos[campo]}
        onChange={(e) => setConcepto(campo, Number(e.target.value))}
        className="w-full rounded border border-brand-100 px-2 py-1.5"
      />
    </label>
  );

  return (
    <div className="space-y-5 rounded-lg border border-brand-100 bg-white p-5">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Tipo de pago</span>
          <select
            value={tipoPago}
            onChange={(e) => setTipoPago(e.target.value as TipoPago)}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          >
            {TIPOS_PAGO.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Período</span>
          <input
            type="text"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Método de pago</span>
          <input
            type="text"
            value={metodoPago}
            onChange={(e) => setMetodoPago(e.target.value)}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
      </div>

      {tipoPago === "Normal" && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-brand-800">Conceptos</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {campoInput("Alquiler", "alquiler")}
            {campoInput("Expensas", "expensas")}
            {campoInput("Edesal", "edesal")}
            {campoInput("Gas", "gas")}
            {campoInput("Municipalidad", "municipalidad")}
            {campoInput("Cochera", "cochera")}
            {campoInput("OO.SS.", "ooss")}
            {campoInput("Imp. Inmobiliario", "impInmobiliario")}
            {campoInput("Honorarios (cuota)", "honorarios")}
            {campoInput("Garantía (cuota)", "garantia")}
            {campoInput("Concepto extra", "conceptoExtra")}
          </div>
        </div>
      )}

      {tipoPago === "Corrección" && (
        <label className="block max-w-xs text-sm">
          <span className="mb-1 block text-brand-700">Diferencia a registrar (negativo = devolución)</span>
          <input
            type="number"
            value={diferenciaCorreccion}
            onChange={(e) => setDiferenciaCorreccion(Number(e.target.value))}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {tipoPago !== "Corrección" && (
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Monto abonado</span>
            <input
              type="number"
              value={montoAbonado}
              onChange={(e) => setMontoAbonado(Number(e.target.value))}
              className="w-full rounded border border-brand-100 px-2 py-1.5"
            />
          </label>
        )}
        <label className="col-span-2 block text-sm">
          <span className="mb-1 block text-brand-700">Comentario</span>
          <input
            type="text"
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
        <CampoCotizacionUsd valor={cotizacionUsd} onChange={setCotizacionUsd} />
      </div>

      <div className="rounded-lg bg-brand-50 p-3 text-sm">
        <p>
          Total a cubrir este movimiento: <strong>{formatMoneda(totalACubrir)}</strong>
        </p>
        <p>
          Saldo actual: {formatMoneda(contrato.saldoActual)} → Saldo estimado tras este cobro:{" "}
          <strong className={previa.saldoNuevo > 0 ? "text-amber-700" : "text-green-700"}>
            {formatMoneda(previa.saldoNuevo)}
          </strong>{" "}
          {previa.saldoNuevo < 0 && "(a favor del inquilino)"}
        </p>
      </div>

      {resultado && (
        <div className={`rounded-md px-3 py-2 text-sm ${resultado.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          <p>{resultado.mensaje}</p>
          {resultado.ok && resultado.nroComprobante && (
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <a href={`/api/pagos/comprobante-pdf?comprobante=${resultado.nroComprobante}`} className="underline">
                Descargar PDF
              </a>
              {contrato.telefonoInquilino && (
                <button
                  onClick={handleEnviarWhatsapp}
                  disabled={enviandoWa}
                  className="rounded border border-green-300 px-2 py-1 text-xs font-medium text-green-800 hover:bg-green-100 disabled:opacity-60"
                >
                  {enviandoWa ? "Enviando…" : "📲 Enviar por WhatsApp"}
                </button>
              )}
              {mensajeWa && <span className="text-xs">{mensajeWa}</span>}
            </div>
          )}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={enviando}
        className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {enviando ? "Registrando…" : "📥 Impactar Cobro"}
      </button>
    </div>
  );
}
