"use client";

import { useState } from "react";
import { crearGasto } from "@/app/(protected)/gastos/actions";

const PAGADO_POR = ["Inmobiliaria", "Propietario", "Inquilino", "Otro"] as const;

interface Propiedad {
  id: number;
  aliasPropiedad: string;
  grupo: string | null;
}

export function FormularioGasto({ propiedades }: { propiedades: Propiedad[] }) {
  const [esCompartido, setEsCompartido] = useState(false);
  const [propiedadId, setPropiedadId] = useState<number | null>(null);
  const [grupo, setGrupo] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [categoria, setCategoria] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [monto, setMonto] = useState(0);
  const [proveedor, setProveedor] = useState("");
  const [comprobante, setComprobante] = useState("");
  const [pagadoPor, setPagadoPor] = useState<(typeof PAGADO_POR)[number]>("Propietario");
  const [tipoGasto, setTipoGasto] = useState("Ordinario");
  const [observaciones, setObservaciones] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  const gruposDisponibles = Array.from(new Set(propiedades.map((p) => p.grupo).filter(Boolean))) as string[];

  async function handleSubmit() {
    setEnviando(true);
    const res = await crearGasto({
      propiedadId: esCompartido ? null : propiedadId,
      grupo: esCompartido ? grupo : null,
      fecha,
      categoria,
      descripcion,
      monto,
      proveedor,
      comprobante,
      pagadoPor,
      observaciones,
      tipoGasto,
      cotizacionUsd: null,
    });
    setEnviando(false);
    setResultado(res.ok ? "Gasto registrado." : res.error ?? "Error al registrar el gasto.");
  }

  return (
    <div className="space-y-4 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🔧 Registrar Gasto</h2>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={esCompartido} onChange={(e) => setEsCompartido(e.target.checked)} />
        Gasto compartido (se reparte entre todas las propiedades de un grupo/edificio)
      </label>

      {esCompartido ? (
        <label className="block max-w-xs text-sm">
          <span className="mb-1 block text-brand-700">Grupo/Edificio</span>
          <select value={grupo} onChange={(e) => setGrupo(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
            <option value="">Seleccionar…</option>
            {gruposDisponibles.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
      ) : (
        <label className="block max-w-xs text-sm">
          <span className="mb-1 block text-brand-700">Propiedad</span>
          <select value={propiedadId ?? ""} onChange={(e) => setPropiedadId(Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5">
            <option value="">Seleccionar…</option>
            {propiedades.map((p) => <option key={p.id} value={p.id}>{p.aliasPropiedad}</option>)}
          </select>
        </label>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Fecha</span>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Categoría</span>
          <input value={categoria} onChange={(e) => setCategoria(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Monto</span>
          <input type="number" value={monto} onChange={(e) => setMonto(Number(e.target.value))} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Pagado por</span>
          <select value={pagadoPor} onChange={(e) => setPagadoPor(e.target.value as typeof pagadoPor)} className="w-full rounded border border-brand-100 px-2 py-1.5">
            {PAGADO_POR.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Tipo de gasto</span>
          <select value={tipoGasto} onChange={(e) => setTipoGasto(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
            <option value="Ordinario">Ordinario</option>
            <option value="Extraordinario">Extraordinario</option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Proveedor</span>
          <input value={proveedor} onChange={(e) => setProveedor(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">N° Comprobante</span>
          <input value={comprobante} onChange={(e) => setComprobante(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block text-brand-700">Descripción</span>
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-brand-700">Observaciones</span>
        <input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button onClick={handleSubmit} disabled={enviando} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
        {enviando ? "Guardando…" : "Guardar Gasto"}
      </button>
    </div>
  );
}
