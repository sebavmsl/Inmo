"use client";

import { useState } from "react";
import { crearPropiedad } from "@/app/(protected)/auxiliares/actions";

const CAMPO_VACIO = {
  aliasPropiedad: "",
  calle: "",
  numero: "",
  departamento: "",
  propietario: "",
  ciudad: "",
  provincia: "",
  tipo: "",
  nis: "",
  cuentaGas: "",
  finca: "",
  cuentaOoss: "",
  nroPadron: "",
  grupo: "",
  expensasAdministradaPorPropietario: false,
};

export function FormularioPropiedad() {
  const [datos, setDatos] = useState(CAMPO_VACIO);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  function campo<K extends keyof typeof CAMPO_VACIO>(k: K, v: (typeof CAMPO_VACIO)[K]) {
    setDatos((d) => ({ ...d, [k]: v }));
  }

  async function handleSubmit() {
    setEnviando(true);
    const res = await crearPropiedad({ ...datos, grupo: datos.grupo || null });
    setEnviando(false);
    setResultado(res.ok ? "Propiedad creada." : res.error ?? "Error.");
    if (res.ok) setDatos(CAMPO_VACIO);
  }

  const input = (placeholder: string, campoKey: keyof typeof CAMPO_VACIO) => (
    <input
      placeholder={placeholder}
      value={datos[campoKey]}
      onChange={(e) => campo(campoKey, e.target.value)}
      className="rounded border border-brand-100 px-2 py-1.5 text-sm"
    />
  );

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🏠 Nueva Propiedad</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {input("Alias", "aliasPropiedad")}
        {input("Calle", "calle")}
        {input("Número", "numero")}
        {input("Departamento (opcional)", "departamento")}
        {input("Propietario", "propietario")}
        {input("Grupo/Edificio (opcional, gastos compartidos)", "grupo")}
        {input("Ciudad", "ciudad")}
        {input("Provincia", "provincia")}
        {input("Características", "tipo")}
        {input("NIS Nro (luz)", "nis")}
        {input("Cuenta Nro (gas)", "cuentaGas")}
        {input("Finca Nro", "finca")}
        {input("Cuenta Nro (OO.SS.)", "cuentaOoss")}
        {input("Nro Padrón", "nroPadron")}
      </div>
      <label className="flex items-center gap-2 text-sm text-brand-700">
        <input
          type="checkbox"
          checked={datos.expensasAdministradaPorPropietario}
          onChange={(e) => campo("expensasAdministradaPorPropietario", e.target.checked)}
        />
        Las expensas de esta propiedad las administra el propietario (no suman al Neto a Rendir)
      </label>
      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}
      <button onClick={handleSubmit} disabled={enviando} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
        {enviando ? "Guardando…" : "Guardar Propiedad"}
      </button>
    </div>
  );
}
