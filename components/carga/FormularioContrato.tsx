"use client";

import { useState } from "react";
import { crearContrato, type DatosContrato } from "@/app/(protected)/carga/actions";

const INDICES = ["ICL", "IPC", "UVA", "Otro"] as const;
const FRECUENCIAS = ["mensual", "bimestral", "trimestral", "cuatrimestral", "semestral", "anual"] as const;
const CARGOS = ["Inquilino", "Propietario"] as const;

const CAMPOS_CARGO: { campo: keyof DatosContrato; label: string }[] = [
  { campo: "cargoElectricidad", label: "Electricidad" },
  { campo: "cargoGas", label: "Gas" },
  { campo: "cargoMunicipalidad", label: "Municipalidad" },
  { campo: "cargoOoss", label: "OO.SS." },
  { campo: "cargoExpensas", label: "Expensas" },
  { campo: "cargoImpInmobiliario", label: "Imp. Inmobiliario" },
];

const VACIO: DatosContrato = {
  codigo: "",
  aliasPropiedad: "",
  dniInquilino: "",
  fechaInicio: new Date().toISOString().slice(0, 10),
  finContrato: "",
  calcDuracion: 24,
  indice: "ICL",
  frecuenciaActualizacion: "semestral",
  montoInicial: 0,
  honorariosPct: 7, // default confirmado en DESIGN_LOG.md (distinto al 5% de v1)
  montoHonorarios: null,
  cuotaHonorarios: 1,
  montoGarantia: null,
  cuotasDeposito: 1,
  honorariosPagadosBase: 0,
  cuotasHonorariosPagadasBase: 0,
  garantiaPagadaBase: 0,
  cuotasDepositoPagadasBase: 0,
  cargoElectricidad: "Inquilino",
  cargoGas: "Inquilino",
  cargoMunicipalidad: "Inquilino",
  cargoOoss: "Inquilino",
  cargoExpensas: "Inquilino",
  cargoImpInmobiliario: "Propietario", // default real de v1
  cochera: 0,
};

export function FormularioContrato() {
  const [datos, setDatos] = useState<DatosContrato>(VACIO);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; mensaje: string } | null>(null);

  function set<K extends keyof DatosContrato>(campo: K, valor: DatosContrato[K]) {
    setDatos((prev) => ({ ...prev, [campo]: valor }));
  }

  async function handleSubmit() {
    setEnviando(true);
    setResultado(null);
    const res = await crearContrato(datos);
    setEnviando(false);
    setResultado(
      res.ok
        ? { ok: true, mensaje: "Contrato creado correctamente." }
        : { ok: false, mensaje: res.error ?? "Error al crear el contrato." }
    );
    if (res.ok) setDatos(VACIO);
  }

  return (
    <div className="space-y-5 rounded-lg border border-brand-100 bg-white p-5">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Código de contrato</span>
          <input value={datos.codigo} onChange={(e) => set("codigo", e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Alias de propiedad</span>
          <input value={datos.aliasPropiedad} onChange={(e) => set("aliasPropiedad", e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">DNI del inquilino</span>
          <input value={datos.dniInquilino} onChange={(e) => set("dniInquilino", e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Fecha de inicio</span>
          <input type="date" value={datos.fechaInicio} onChange={(e) => set("fechaInicio", e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Fin de contrato</span>
          <input type="date" value={datos.finContrato} onChange={(e) => set("finContrato", e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Duración total (meses)</span>
          <input type="number" value={datos.calcDuracion} onChange={(e) => set("calcDuracion", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Índice de actualización</span>
          <select value={datos.indice} onChange={(e) => set("indice", e.target.value as DatosContrato["indice"])} className="w-full rounded border border-brand-100 px-2 py-1.5">
            {INDICES.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Frecuencia de actualización</span>
          <select value={datos.frecuenciaActualizacion} onChange={(e) => set("frecuenciaActualizacion", e.target.value as DatosContrato["frecuenciaActualizacion"])} className="w-full rounded border border-brand-100 px-2 py-1.5">
            {FRECUENCIAS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Alquiler inicial</span>
          <input type="number" value={datos.montoInicial} onChange={(e) => set("montoInicial", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Cochera</span>
          <input type="number" value={datos.cochera} onChange={(e) => set("cochera", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-brand-800">Servicios y expensas — a cargo de</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {CAMPOS_CARGO.map(({ campo, label }) => (
            <label key={campo} className="block text-sm">
              <span className="mb-1 block text-brand-700">{label}</span>
              <select
                value={datos[campo] as string}
                onChange={(e) => set(campo, e.target.value as DatosContrato[typeof campo])}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              >
                {CARGOS.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-brand-800">Honorarios de gestión (en cuotas)</h3>
        <p className="mb-2 text-xs text-brand-400">
          Si dejás el total pactado vacío, se usa el alquiler inicial como base — igual que v1.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Total pactado</span>
            <input
              type="number"
              value={datos.montoHonorarios ?? ""}
              placeholder="= alquiler inicial"
              onChange={(e) => set("montoHonorarios", e.target.value === "" ? null : Number(e.target.value))}
              className="w-full rounded border border-brand-100 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Cuotas pactadas</span>
            <input type="number" value={datos.cuotaHonorarios} onChange={(e) => set("cuotaHonorarios", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Ya pagado ($, previo a v2)</span>
            <input type="number" value={datos.honorariosPagadosBase} onChange={(e) => set("honorariosPagadosBase", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Cuotas ya pagadas (previo a v2)</span>
            <input type="number" value={datos.cuotasHonorariosPagadasBase} onChange={(e) => set("cuotasHonorariosPagadasBase", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-brand-800">Depósito de garantía (en cuotas)</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Total pactado</span>
            <input
              type="number"
              value={datos.montoGarantia ?? ""}
              placeholder="= alquiler inicial"
              onChange={(e) => set("montoGarantia", e.target.value === "" ? null : Number(e.target.value))}
              className="w-full rounded border border-brand-100 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Cuotas pactadas</span>
            <input type="number" value={datos.cuotasDeposito} onChange={(e) => set("cuotasDeposito", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Ya pagado ($, previo a v2)</span>
            <input type="number" value={datos.garantiaPagadaBase} onChange={(e) => set("garantiaPagadaBase", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Cuotas ya pagadas (previo a v2)</span>
            <input type="number" value={datos.cuotasDepositoPagadasBase} onChange={(e) => set("cuotasDepositoPagadasBase", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
          </label>
        </div>
      </div>

      <label className="block max-w-xs text-sm">
        <span className="mb-1 block text-brand-700">% de comisión mensual (honorarios_pct)</span>
        <input type="number" step="0.5" value={datos.honorariosPct} onChange={(e) => set("honorariosPct", Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>

      {resultado && (
        <p className={`rounded-md px-3 py-2 text-sm ${resultado.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {resultado.mensaje}
        </p>
      )}

      <button
        onClick={handleSubmit}
        disabled={enviando}
        className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {enviando ? "Guardando…" : "💾 Guardar Contrato"}
      </button>
    </div>
  );
}
