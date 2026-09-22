"use client";

import { useEffect, useMemo, useState } from "react";
import { listarPropiedades, asignarGrupo, type PropiedadEditable } from "@/app/(protected)/auxiliares/actions";

/**
 * Puerto de la subpestaña "🏢 Nuevo Edificio/Grupo" de app.py: asigna un
 * mismo nombre de grupo a 2+ propiedades de una sola vez, para usarlo
 * después en gastos compartidos (Módulo 2/7).
 */
export function FormularioGrupo() {
  const [propiedades, setPropiedades] = useState<PropiedadEditable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [nombreGrupo, setNombreGrupo] = useState("");
  const [seleccionadas, setSeleccionadas] = useState<Set<number>>(new Set());
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  async function recargar() {
    setCargando(true);
    setPropiedades(await listarPropiedades());
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, []);

  const gruposExistentes = useMemo(
    () => Array.from(new Set(propiedades.map((p) => p.grupo).filter((g): g is string => !!g))).sort(),
    [propiedades]
  );

  function toggle(id: number) {
    setSeleccionadas((prev) => {
      const nuevo = new Set(prev);
      if (nuevo.has(id)) nuevo.delete(id);
      else nuevo.add(id);
      return nuevo;
    });
  }

  async function handleSubmit() {
    setEnviando(true);
    setResultado(null);
    const res = await asignarGrupo(nombreGrupo, Array.from(seleccionadas));
    setEnviando(false);
    setResultado(res.ok ? `Grupo "${nombreGrupo.trim()}" guardado con ${seleccionadas.size} propiedades.` : res.error ?? "Error.");
    if (res.ok) {
      setNombreGrupo("");
      setSeleccionadas(new Set());
      await recargar();
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">🏢 Nuevo Edificio/Grupo</h2>
      <p className="text-xs text-brand-400">Asigná un nombre de grupo a un conjunto de propiedades para usarlo en gastos compartidos.</p>

      {gruposExistentes.length > 0 && (
        <p className="text-xs text-brand-500">Grupos existentes: {gruposExistentes.join(", ")}</p>
      )}

      <input
        placeholder="Nombre del Grupo / Edificio (ej: Tucumán 150)"
        value={nombreGrupo}
        onChange={(e) => setNombreGrupo(e.target.value)}
        className="w-full max-w-sm rounded border border-brand-100 px-2 py-1.5 text-sm"
      />

      {cargando ? (
        <p className="text-sm text-brand-400">Cargando…</p>
      ) : (
        <div className="max-h-56 space-y-1 overflow-y-auto rounded border border-brand-100 p-2">
          {propiedades.map((p) => (
            <label key={p.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={seleccionadas.has(p.id)} onChange={() => toggle(p.id)} />
              {p.aliasPropiedad} <span className="text-xs text-brand-400">(grupo actual: {p.grupo || "ninguno"})</span>
            </label>
          ))}
          {propiedades.length === 0 && <p className="text-sm text-brand-400">No hay propiedades registradas.</p>}
        </div>
      )}

      {resultado && <p className="text-sm text-brand-600">{resultado}</p>}

      <button
        onClick={handleSubmit}
        disabled={enviando || !nombreGrupo.trim() || seleccionadas.size < 2}
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {enviando ? "Guardando…" : "💾 Guardar Grupo"}
      </button>
    </div>
  );
}
