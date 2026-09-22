"use client";

import { useEffect, useState } from "react";
import { listarContratos, editarContrato, type DatosEditarContrato } from "@/app/(protected)/carga/actions";
import type { ContratoEditable } from "@/lib/carga/queries";
import { usePresencia } from "@/lib/concurrencia/usePresencia";
import { INDICES, FRECUENCIAS, CARGOS } from "@/components/carga/FormularioContrato";
import { bloqueadoPorActualizacionPendiente } from "@/lib/carga/validaciones";

const ESTADOS = ["Activo", "Finalizado", "Cancelado"] as const;

const CAMPOS_CARGO: { campo: keyof DatosEditarContrato; label: string }[] = [
  { campo: "cargoElectricidad", label: "Electricidad" },
  { campo: "cargoGas", label: "Gas" },
  { campo: "cargoMunicipalidad", label: "Municipalidad" },
  { campo: "cargoOoss", label: "OO.SS." },
  { campo: "cargoExpensas", label: "Expensas" },
  { campo: "cargoImpInmobiliario", label: "Imp. Inmobiliario" },
];

/**
 * Edición de contratos existentes (módulo "Carga de Contratos") — patrón
 * seleccionar-y-editar igual que EditarPropiedad.tsx/EditarInquilino.tsx.
 * NO permite tocar `montoInicial` (histórico del alta) ni `alquiler`
 * (lo mantiene el motor de índices de Planilla). Antes de habilitar el
 * formulario se corre `bloqueadoPorActualizacionPendiente()` (mismo
 * criterio de urgencia que colorea la Planilla) — si el contrato tiene
 * una actualización de índice vencida o de este mes, se bloquea la
 * edición de otros campos con un cartel, en vez del formulario, y se
 * redirige al usuario a Planilla. Se calcula apenas se selecciona el
 * contrato (no recién al fallar el guardado) y se vuelve a validar en
 * el servidor antes de guardar, por si cambió entretanto.
 */
export function EditarContrato() {
  const [contratos, setContratos] = useState<ContratoEditable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [editando, setEditando] = useState<ContratoEditable | null>(null);

  // Antes, si listarContratos() tiraba una excepción (error de red, de
  // RLS/permisos, lo que sea), el catch faltante dejaba `cargando` en
  // true para siempre — el "Cargando…" quedaba pegado sin ningún
  // mensaje, indistinguible de una consulta lenta de verdad. Con el
  // try/catch, un error real se ve como error (no como carga eterna).
  async function recargar() {
    setCargando(true);
    setErrorCarga(null);
    try {
      setContratos(await listarContratos());
    } catch (e) {
      setErrorCarga(e instanceof Error ? e.message : "Error cargando los contratos.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    recargar();
  }, []);

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <h2 className="text-sm font-semibold text-brand-800">📄 Editar Contrato</h2>

      {cargando ? (
        <p className="text-sm text-brand-400">Cargando…</p>
      ) : errorCarga ? (
        <div className="space-y-2">
          <p className="text-sm text-red-600">⚠️ {errorCarga}</p>
          <button
            onClick={recargar}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
          >
            Reintentar
          </button>
        </div>
      ) : contratos.length === 0 ? (
        <p className="text-sm text-brand-500">No hay contratos registrados para editar.</p>
      ) : (
        <select
          value={editando?.codigo ?? ""}
          onChange={(e) => setEditando(contratos.find((c) => c.codigo === e.target.value) ?? null)}
          className="w-full max-w-md rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          <option value="">Seleccionar contrato…</option>
          {contratos.map((c) => (
            <option key={c.codigo} value={c.codigo}>
              {c.codigo} | {c.aliasPropiedad} — {c.inquilino} ({c.estado})
            </option>
          ))}
        </select>
      )}

      {editando && (
        <FormularioEditarContrato
          key={editando.codigo}
          contrato={editando}
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

function FormularioEditarContrato({
  contrato,
  onCancelar,
  onGuardado,
}: {
  contrato: ContratoEditable;
  onCancelar: () => void;
  onGuardado: () => void;
}) {
  const [datos, setDatos] = useState<DatosEditarContrato>({
    estado: contrato.estado,
    dniInquilino: contrato.dniInquilino,
    fechaInicio: contrato.fechaInicio,
    finContrato: contrato.finContrato,
    calcDuracion: contrato.calcDuracion,
    indice: contrato.indice,
    frecuenciaMeses: contrato.frecuenciaMeses,
    honorariosPct: contrato.honorariosPct,
    montoHonorarios: contrato.montoHonorarios,
    cuotaHonorarios: contrato.cuotaHonorarios,
    montoGarantia: contrato.montoGarantia,
    cuotasDeposito: contrato.cuotasDeposito,
    cargoElectricidad: contrato.cargoElectricidad,
    cargoGas: contrato.cargoGas,
    cargoMunicipalidad: contrato.cargoMunicipalidad,
    cargoOoss: contrato.cargoOoss,
    cargoExpensas: contrato.cargoExpensas,
    cargoImpInmobiliario: contrato.cargoImpInmobiliario,
    cochera: contrato.cochera,
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);

  // Bloqueo por actualización de índice pendiente — se calcula al
  // instante con los mismos datos que ya trae el listado (finContrato/
  // proxActualizacion), sin esperar a un intento de guardado fallido.
  // bloqueadoPorActualizacionPendiente() es una función pura (sin acceso
  // a datos), así que puede correr en el cliente; el server action la
  // vuelve a correr igual antes de guardar, por si el contrato cambió
  // entre que se cargó la lista y que se intenta guardar.
  const bloqueoInicial = bloqueadoPorActualizacionPendiente({
    estado: contrato.estado,
    finContrato: contrato.finContrato,
    proxActualizacion: contrato.proxActualizacion,
  });
  const [bloqueado, setBloqueado] = useState(bloqueoInicial.bloqueado);
  const [motivoBloqueo, setMotivoBloqueo] = useState<string | null>(bloqueoInicial.motivo);

  const otrosEditando = usePresencia("contratos", contrato.codigo);

  function set<K extends keyof DatosEditarContrato>(campo: K, valor: DatosEditarContrato[K]) {
    setDatos((prev) => ({ ...prev, [campo]: valor }));
  }

  async function handleSubmit() {
    setGuardando(true);
    setError(null);
    setConflicto(false);
    const res = await editarContrato(contrato.codigo, datos, contrato.updatedAt);
    setGuardando(false);
    if (!res.ok) {
      setError(res.error ?? "Error al guardar.");
      setConflicto(!!res.conflicto);
      if (res.bloqueado) {
        setBloqueado(true);
        setMotivoBloqueo(res.error ?? "Edición bloqueada.");
      }
      return;
    }
    onGuardado();
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      <h3 className="text-sm font-semibold text-brand-800">
        Editando: {contrato.codigo} — {contrato.aliasPropiedad}
      </h3>

      {otrosEditando.length > 0 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          También hay alguien más editando esto ahora mismo: {otrosEditando.map((e) => e.username).join(", ")}.
        </p>
      )}

      {bloqueado && (
        <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          🔒 {motivoBloqueo}
        </p>
      )}

      {!bloqueado && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Estado</span>
              <select
                value={datos.estado}
                onChange={(e) => set("estado", e.target.value)}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              >
                {ESTADOS.map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">DNI del inquilino</span>
              <input
                value={datos.dniInquilino}
                onChange={(e) => set("dniInquilino", e.target.value)}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Fecha de inicio</span>
              <input
                type="date"
                value={datos.fechaInicio}
                onChange={(e) => set("fechaInicio", e.target.value)}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Fin de contrato</span>
              <input
                type="date"
                value={datos.finContrato ?? ""}
                onChange={(e) => set("finContrato", e.target.value || null)}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Duración total (meses)</span>
              <input
                type="number"
                value={datos.calcDuracion ?? ""}
                onChange={(e) => set("calcDuracion", e.target.value === "" ? null : Number(e.target.value))}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Índice de actualización</span>
              <select
                value={datos.indice}
                onChange={(e) => set("indice", e.target.value as DatosEditarContrato["indice"])}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              >
                {INDICES.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Frecuencia de actualización</span>
              <select
                value={datos.frecuenciaMeses}
                onChange={(e) => set("frecuenciaMeses", Number(e.target.value))}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              >
                {FRECUENCIAS.map((f) => (
                  <option key={f.meses} value={f.meses}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Cochera</span>
              <input
                type="number"
                value={datos.cochera ?? ""}
                onChange={(e) => set("cochera", e.target.value === "" ? null : Number(e.target.value))}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              />
            </label>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Servicios y expensas — a cargo de</h4>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {CAMPOS_CARGO.map(({ campo, label }) => (
                <label key={campo} className="block text-sm">
                  <span className="mb-1 block text-brand-700">{label}</span>
                  <select
                    value={datos[campo] as string}
                    onChange={(e) => set(campo, e.target.value as DatosEditarContrato[typeof campo])}
                    className="w-full rounded border border-brand-100 px-2 py-1.5"
                  >
                    {CARGOS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Honorarios de gestión (en cuotas)</h4>
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
                <input
                  type="number"
                  value={datos.cuotaHonorarios}
                  onChange={(e) => set("cuotaHonorarios", Number(e.target.value))}
                  className="w-full rounded border border-brand-100 px-2 py-1.5"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">% de comisión mensual</span>
                <input
                  type="number"
                  step="0.5"
                  value={datos.honorariosPct}
                  onChange={(e) => set("honorariosPct", Number(e.target.value))}
                  className="w-full rounded border border-brand-100 px-2 py-1.5"
                />
              </label>
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Depósito de garantía (en cuotas)</h4>
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
                <input
                  type="number"
                  value={datos.cuotasDeposito}
                  onChange={(e) => set("cuotasDeposito", Number(e.target.value))}
                  className="w-full rounded border border-brand-100 px-2 py-1.5"
                />
              </label>
            </div>
          </div>
        </>
      )}

      {error && !bloqueado && (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{error}</p>
          {conflicto && (
            <button
              onClick={onGuardado}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              Refrescar (volvé a seleccionar el contrato para reintentar)
            </button>
          )}
        </div>
      )}

      <div className="flex gap-2">
        {!bloqueado && (
          <button
            onClick={handleSubmit}
            disabled={guardando || conflicto}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {guardando ? "Guardando…" : "Guardar Cambios"}
          </button>
        )}
        <button onClick={onCancelar} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50">
          Cerrar
        </button>
      </div>
    </div>
  );
}
