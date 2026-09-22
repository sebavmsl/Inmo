"use client";

import { useEffect, useState } from "react";
import { listarInquilinos, actualizarInquilino, type InquilinoEditable } from "@/app/(protected)/auxiliares/actions";
import { usePresencia } from "@/lib/concurrencia/usePresencia";

export function EditarInquilino() {
  const [inquilinos, setInquilinos] = useState<InquilinoEditable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState<InquilinoEditable | null>(null);

  async function recargar() {
    setCargando(true);
    setInquilinos(await listarInquilinos());
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, []);

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🧑 Editar Inquilino</h2>

      {cargando ? (
        <p className="text-sm text-brand-400">Cargando…</p>
      ) : inquilinos.length === 0 ? (
        <p className="text-sm text-brand-500">No hay inquilinos registrados para editar.</p>
      ) : (
        <select
          value={editando?.id ?? ""}
          onChange={(e) => setEditando(inquilinos.find((i) => i.id === Number(e.target.value)) ?? null)}
          className="w-full max-w-md rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          <option value="">Seleccionar inquilino…</option>
          {inquilinos.map((i) => (
            <option key={i.id} value={i.id}>
              {i.apellidos}, {i.nombres} (DNI {i.dni})
            </option>
          ))}
        </select>
      )}

      {editando && (
        <FormularioEditarInquilino
          key={editando.id}
          inquilino={editando}
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

function FormularioEditarInquilino({
  inquilino,
  onCancelar,
  onGuardado,
}: {
  inquilino: InquilinoEditable;
  onCancelar: () => void;
  onGuardado: () => void;
}) {
  const [dni, setDni] = useState(inquilino.dni);
  const [nombres, setNombres] = useState(inquilino.nombres);
  const [apellidos, setApellidos] = useState(inquilino.apellidos);
  const [telefono, setTelefono] = useState(inquilino.telefono ?? "");
  const [email, setEmail] = useState(inquilino.email ?? "");
  const [confirmoCambioDni, setConfirmoCambioDni] = useState(false);
  const [pideConfirmacionDni, setPideConfirmacionDni] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);

  const otrosEditando = usePresencia("inquilinos", String(inquilino.id));

  async function handleSubmit(confirmar = false) {
    setGuardando(true);
    setError(null);
    setConflicto(false);
    const res = await actualizarInquilino({
      id: inquilino.id,
      dni,
      nombres,
      apellidos,
      telefono,
      email,
      confirmoCambioDni: confirmar,
      updatedAtEsperado: inquilino.updatedAt,
    });
    setGuardando(false);
    if (!res.ok) {
      if (res.requiereConfirmacionDni) {
        setPideConfirmacionDni(true);
        setError(res.error ?? null);
        return;
      }
      setError(res.error ?? "Error al guardar.");
      setConflicto(!!res.conflicto);
      return;
    }
    onGuardado();
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      <h3 className="text-sm font-semibold text-brand-800">
        Editando: {inquilino.apellidos}, {inquilino.nombres}
      </h3>

      {otrosEditando.length > 0 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          También hay alguien más editando esto ahora mismo: {otrosEditando.map((e) => e.username).join(", ")}.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Apellidos</span>
          <input value={apellidos} onChange={(e) => setApellidos(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Nombres</span>
          <input value={nombres} onChange={(e) => setNombres(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">DNI / CUIT</span>
          <input
            value={dni}
            onChange={(e) => {
              setDni(e.target.value);
              setPideConfirmacionDni(false);
              setConfirmoCambioDni(false);
            }}
            className="w-full rounded border border-brand-100 px-2 py-1.5"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Teléfono</span>
          <input value={telefono} onChange={(e) => setTelefono(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-brand-700">Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
        </label>
      </div>

      {pideConfirmacionDni && (
        <div className="space-y-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <p>{error}</p>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={confirmoCambioDni} onChange={(e) => setConfirmoCambioDni(e.target.checked)} />
            Entiendo el riesgo y quiero guardar el DNI nuevo igual.
          </label>
        </div>
      )}
      {error && !pideConfirmacionDni && (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{error}</p>
          {conflicto && (
            <button onClick={onGuardado} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">
              Refrescar (volvé a seleccionar el inquilino para reintentar)
            </button>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit(pideConfirmacionDni ? confirmoCambioDni : false)}
          disabled={guardando || conflicto || !apellidos || !nombres || (pideConfirmacionDni && !confirmoCambioDni)}
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
