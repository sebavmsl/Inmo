"use client";

import { useEffect, useState } from "react";
import { listarPropiedades, actualizarPropiedad, type PropiedadEditable } from "@/app/(protected)/auxiliares/actions";
import { usePresencia } from "@/lib/concurrencia/usePresencia";

/**
 * Edición de propiedades (Módulo 3) — a diferencia de v1, cubre TODOS
 * los campos (propietario incluido), no solo alias/calle/número/depto/
 * grupo (ver 0017_auxiliares_completo.sql). Usa el módulo transversal
 * de ediciones simultáneas (presencia + optimistic locking).
 */
export function EditarPropiedad() {
  const [propiedades, setPropiedades] = useState<PropiedadEditable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState<PropiedadEditable | null>(null);

  async function recargar() {
    setCargando(true);
    setPropiedades(await listarPropiedades());
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, []);

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🏠 Editar Propiedad</h2>

      {cargando ? (
        <p className="text-sm text-brand-400">Cargando…</p>
      ) : propiedades.length === 0 ? (
        <p className="text-sm text-brand-500">No hay propiedades registradas para editar.</p>
      ) : (
        <select
          value={editando?.id ?? ""}
          onChange={(e) => setEditando(propiedades.find((p) => p.id === Number(e.target.value)) ?? null)}
          className="w-full max-w-md rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          <option value="">Seleccionar propiedad…</option>
          {propiedades.map((p) => (
            <option key={p.id} value={p.id}>
              Cod: {p.id} | {p.aliasPropiedad} ({p.propietario || "Sin propietario"})
            </option>
          ))}
        </select>
      )}

      {editando && (
        <FormularioEditarPropiedad
          key={editando.id}
          propiedad={editando}
          onCancelar={() => setEditando(null)}
          onGuardado={async () => {
            setEditando(null);
            await recargar();
          }}
        />
      )}
    </div>
  );
}

function FormularioEditarPropiedad({
  propiedad,
  onCancelar,
  onGuardado,
}: {
  propiedad: PropiedadEditable;
  onCancelar: () => void;
  onGuardado: () => void;
}) {
  const [datos, setDatos] = useState({
    aliasPropiedad: propiedad.aliasPropiedad,
    calle: propiedad.calle,
    numero: propiedad.numero,
    departamento: propiedad.departamento ?? "",
    propietario: propiedad.propietario,
    ciudad: propiedad.ciudad ?? "",
    provincia: propiedad.provincia ?? "",
    tipo: propiedad.tipo ?? "",
    nis: propiedad.nis ?? "",
    cuentaGas: propiedad.cuentaGas ?? "",
    finca: propiedad.finca ?? "",
    cuentaOoss: propiedad.cuentaOoss ?? "",
    nroPadron: propiedad.nroPadron ?? "",
    grupo: propiedad.grupo ?? "",
    expensasAdministradaPorPropietario: propiedad.expensasAdministradaPorPropietario,
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);

  const otrosEditando = usePresencia("propiedades", String(propiedad.id));

  function campo<K extends keyof typeof datos>(k: K, v: (typeof datos)[K]) {
    setDatos((d) => ({ ...d, [k]: v }));
  }

  async function handleSubmit() {
    setGuardando(true);
    setError(null);
    setConflicto(false);
    const res = await actualizarPropiedad({
      id: propiedad.id,
      ...datos,
      grupo: datos.grupo || null,
      updatedAtEsperado: propiedad.updatedAt,
    });
    setGuardando(false);
    if (!res.ok) {
      setError(res.error ?? "Error al guardar.");
      setConflicto(!!res.conflicto);
      return;
    }
    onGuardado();
  }

  // Excluye el único campo no-texto (el checkbox de expensas, más abajo)
  // — si `k` pudiera ser esa clave, datos[k] tipa "string | boolean" y
  // <input value=...> no acepta boolean.
  type CampoTexto = Exclude<keyof typeof datos, "expensasAdministradaPorPropietario">;
  const input = (label: string, k: CampoTexto) => (
    <label className="block text-sm">
      <span className="mb-1 block text-brand-700">{label}</span>
      <input value={datos[k]} onChange={(e) => campo(k, e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
    </label>
  );

  return (
    <div className="space-y-3 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      <h3 className="text-sm font-semibold text-brand-800">Editando: {propiedad.aliasPropiedad}</h3>

      {otrosEditando.length > 0 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          También hay alguien más editando esto ahora mismo: {otrosEditando.map((e) => e.username).join(", ")}.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {input("Alias", "aliasPropiedad")}
        {input("Calle", "calle")}
        {input("Número", "numero")}
        {input("Departamento", "departamento")}
        {input("Propietario", "propietario")}
        {input("Grupo/Edificio", "grupo")}
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

      {error && (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{error}</p>
          {conflicto && (
            <button onClick={onGuardado} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">
              Refrescar (volvé a seleccionar la propiedad para reintentar)
            </button>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={guardando || conflicto || !datos.aliasPropiedad || !datos.calle || !datos.numero}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {guardando ? "Guardando…" : "Guardar Cambios"}
        </button>
        <button onClick={onCancelar} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50">
          Cancelar
        </button>
      </div>
    </div>
  );
}
