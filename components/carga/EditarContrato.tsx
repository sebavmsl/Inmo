"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listarContratos, editarContrato, opcionesAlta, type DatosEditarContrato } from "@/app/(protected)/carga/actions";
import type { ContratoEditable } from "@/lib/carga/queries";
import { usePresencia } from "@/lib/concurrencia/usePresencia";
import { CARGOS, ESTADOS_CONTRATO, FRECUENCIAS, INDICES, SERVICIOS, type OpcionesAlta } from "@/lib/carga/tipos";
import { TIPOS_GARANTIA, tieneDeposito, tienePagare, type Cargo } from "@/lib/carga/calculoContrato";
import { bloqueadoPorActualizacionPendiente } from "@/lib/carga/validaciones";

const INPUT = "w-full rounded border border-brand-100 px-2 py-1.5";

function aNumero(v: string): number {
  return v === "" ? 0 : Number(v);
}

/**
 * Edición de contratos existentes (módulo "Carga de Contratos") — patrón
 * seleccionar-y-editar igual que EditarPropiedad.tsx/EditarInquilino.tsx.
 * Sirve para corregir datos mal cargados: permite tocar el monto inicial
 * y las fechas (con aviso, Entrega 2), pero no el alquiler vigente (lo
 * mantienen Pagos y la actualización de índices de Planilla). Para seguir
 * con el mismo inquilino en un contrato nuevo está el botón "Renovar". Antes de habilitar el
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
  const [inquilinos, setInquilinos] = useState<OpcionesAlta["inquilinos"]>([]);

  // Antes, si listarContratos() tiraba una excepción (error de red, de
  // RLS/permisos, lo que sea), el catch faltante dejaba `cargando` en
  // true para siempre — el "Cargando…" quedaba pegado sin ningún
  // mensaje, indistinguible de una consulta lenta de verdad. Con el
  // try/catch, un error real se ve como error (no como carga eterna).
  async function recargar() {
    setCargando(true);
    setErrorCarga(null);
    try {
      const [lista, opciones] = await Promise.all([listarContratos(), opcionesAlta()]);
      setContratos(lista);
      setInquilinos(opciones.inquilinos);
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
          value={editando ? String(editando.codigo) : ""}
          onChange={(e) => setEditando(contratos.find((c) => String(c.codigo) === e.target.value) ?? null)}
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
          inquilinos={inquilinos}
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
  inquilinos,
  onCancelar,
  onGuardado,
}: {
  contrato: ContratoEditable;
  inquilinos: OpcionesAlta["inquilinos"];
  onCancelar: () => void;
  onGuardado: () => void;
}) {
  const [datos, setDatos] = useState<DatosEditarContrato>({
    estado: contrato.estado,
    dniInquilino: contrato.dniInquilino,
    fechaInicio: contrato.fechaInicio,
    finContrato: contrato.finContrato,
    diaVencimiento: contrato.diaVencimiento,
    montoInicial: contrato.montoInicial,
    indice: contrato.indice,
    frecuenciaMeses: contrato.frecuenciaMeses,
    honorariosPct: contrato.honorariosPct,
    montoHonorarios: contrato.montoHonorarios,
    cuotaHonorarios: contrato.cuotaHonorarios,
    tipoGarantia: (TIPOS_GARANTIA as readonly string[]).includes(contrato.tipoGarantia) ? contrato.tipoGarantia : "Sin Garantía",
    montoGarantia: contrato.montoGarantia,
    cuotasDeposito: contrato.cuotasDeposito,
    montoPagare: contrato.montoPagare,
    servicios: contrato.servicios,
    cargos: {
      electricidad: contrato.cargoElectricidad,
      gas: contrato.cargoGas,
      municipalidad: contrato.cargoMunicipalidad,
      ooss: contrato.cargoOoss,
      expensas: contrato.cargoExpensas,
      impInmobiliario: contrato.cargoImpInmobiliario,
    },
    cargoGeneralServicios: contrato.cargoGeneralServicios,
    cochera: contrato.cochera,
    cocheraMontoInicial: contrato.cocheraMontoInicial,
    cocheraActualizaConIndice: contrato.cocheraActualizaConIndice,
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);

  // Bloqueo por actualización de índice pendiente — se calcula al
  // instante con los mismos datos que ya trae el listado; el server
  // action lo vuelve a correr antes de guardar.
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

  const cambiaronDatosOriginales =
    datos.montoInicial !== contrato.montoInicial ||
    datos.fechaInicio !== contrato.fechaInicio ||
    datos.finContrato !== contrato.finContrato;
  const cocheraConIndicePosible = ["ICL", "IPC", "UVA"].includes(datos.indice) && datos.frecuenciaMeses > 0;
  const inquilinoEnLista = inquilinos.some((i) => i.dni === datos.dniInquilino);

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
    <div className="space-y-4 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-brand-800">
          Editando: {contrato.codigo} — {contrato.aliasPropiedad}
        </h3>
        <Link
          href={`/carga?renovar=${contrato.codigo}#alta`}
          className="rounded-lg border border-brand-300 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
        >
          🔁 Renovar con el mismo inquilino
        </Link>
      </div>

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
              <select value={datos.estado} onChange={(e) => set("estado", e.target.value)} className={INPUT}>
                {ESTADOS_CONTRATO.map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block text-brand-700">Inquilino</span>
              <select value={datos.dniInquilino} onChange={(e) => set("dniInquilino", e.target.value)} className={INPUT}>
                {!inquilinoEnLista && <option value={datos.dniInquilino}>DNI {datos.dniInquilino}</option>}
                {inquilinos.map((i) => (
                  <option key={i.dni} value={i.dni}>
                    {i.nombre} — DNI {i.dni}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Fecha de inicio</span>
              <input type="date" value={datos.fechaInicio} onChange={(e) => set("fechaInicio", e.target.value)} className={INPUT} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Fin de contrato</span>
              <input
                type="date"
                value={datos.finContrato ?? ""}
                onChange={(e) => set("finContrato", e.target.value || null)}
                className={INPUT}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Día de vencimiento</span>
              <input
                type="number"
                min={1}
                max={31}
                value={datos.diaVencimiento}
                onChange={(e) => set("diaVencimiento", Math.round(aNumero(e.target.value)))}
                className={INPUT}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Monto inicial ($)</span>
              <input
                type="number"
                value={datos.montoInicial}
                onChange={(e) => set("montoInicial", aNumero(e.target.value))}
                className={INPUT}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Índice de actualización</span>
              <select
                value={datos.indice}
                onChange={(e) => set("indice", e.target.value as DatosEditarContrato["indice"])}
                className={INPUT}
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
                className={INPUT}
              >
                {FRECUENCIAS.map((f) => (
                  <option key={f.meses} value={f.meses}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {cambiaronDatosOriginales && (
            <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              ⚠️ Estás cambiando datos originales del contrato (monto inicial o fechas). Usalo solo para corregir un error de carga: los
              pagos ya registrados no se recalculan, y si cambian las fechas se recalculan la duración y la próxima actualización. Para
              seguir con el mismo inquilino en un contrato nuevo, usá &quot;Renovar&quot;.
            </p>
          )}

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Servicios — monto del mes y a cargo de</h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {SERVICIOS.map((sv) => (
                <div key={sv.monto} className="grid grid-cols-[1fr_auto] items-end gap-2">
                  <label className="block text-sm">
                    <span className="mb-1 block text-brand-700">{sv.label} ($)</span>
                    <input
                      type="number"
                      value={datos.servicios[sv.monto]}
                      onChange={(e) => set("servicios", { ...datos.servicios, [sv.monto]: aNumero(e.target.value) })}
                      className={INPUT}
                    />
                  </label>
                  <select
                    value={datos.cargos[sv.cargo]}
                    onChange={(e) => set("cargos", { ...datos.cargos, [sv.cargo]: e.target.value as Cargo })}
                    className="rounded border border-brand-100 px-2 py-1.5 text-sm"
                    aria-label={`${sv.label}: a cargo de`}
                  >
                    {CARGOS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-4">
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Cargo general de servicios ($)</span>
                <input
                  type="number"
                  value={datos.cargoGeneralServicios}
                  onChange={(e) => set("cargoGeneralServicios", aNumero(e.target.value))}
                  className={INPUT}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Cochera del mes ($)</span>
                <input
                  type="number"
                  value={datos.cochera ?? ""}
                  onChange={(e) => set("cochera", e.target.value === "" ? null : Number(e.target.value))}
                  className={INPUT}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Cochera — monto inicial ($)</span>
                <input
                  type="number"
                  value={datos.cocheraMontoInicial}
                  onChange={(e) => set("cocheraMontoInicial", aNumero(e.target.value))}
                  className={INPUT}
                />
              </label>
              <label className={`flex items-start gap-2 pt-6 text-sm ${cocheraConIndicePosible ? "text-brand-700" : "text-brand-300"}`}>
                <input
                  type="checkbox"
                  checked={datos.cocheraActualizaConIndice && cocheraConIndicePosible}
                  disabled={!cocheraConIndicePosible}
                  onChange={(e) => set("cocheraActualizaConIndice", e.target.checked)}
                  className="mt-0.5"
                />
                <span>Se actualiza con el índice</span>
              </label>
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Honorarios y comisión</h4>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Total de honorarios ($)</span>
                <input
                  type="number"
                  value={datos.montoHonorarios ?? ""}
                  placeholder="= monto inicial"
                  onChange={(e) => set("montoHonorarios", e.target.value === "" ? null : Number(e.target.value))}
                  className={INPUT}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Cuotas pactadas</span>
                <input
                  type="number"
                  min={1}
                  value={datos.cuotaHonorarios}
                  onChange={(e) => set("cuotaHonorarios", Math.max(1, Math.round(aNumero(e.target.value))))}
                  className={INPUT}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">% de comisión mensual</span>
                <input
                  type="number"
                  step="0.5"
                  value={datos.honorariosPct}
                  onChange={(e) => set("honorariosPct", aNumero(e.target.value))}
                  className={INPUT}
                />
              </label>
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-sm font-semibold text-brand-800">Garantía</h4>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <label className="block text-sm">
                <span className="mb-1 block text-brand-700">Tipo de garantía</span>
                <select value={datos.tipoGarantia} onChange={(e) => set("tipoGarantia", e.target.value)} className={INPUT}>
                  {TIPOS_GARANTIA.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
              {tieneDeposito(datos.tipoGarantia) && (
                <>
                  <label className="block text-sm">
                    <span className="mb-1 block text-brand-700">Depósito ($)</span>
                    <input
                      type="number"
                      value={datos.montoGarantia ?? ""}
                      placeholder="= monto inicial"
                      onChange={(e) => set("montoGarantia", e.target.value === "" ? null : Number(e.target.value))}
                      className={INPUT}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block text-brand-700">Cuotas del depósito</span>
                    <input
                      type="number"
                      min={1}
                      value={datos.cuotasDeposito}
                      onChange={(e) => set("cuotasDeposito", Math.max(1, Math.round(aNumero(e.target.value))))}
                      className={INPUT}
                    />
                  </label>
                </>
              )}
              {tienePagare(datos.tipoGarantia) && (
                <label className="block text-sm">
                  <span className="mb-1 block text-brand-700">Monto del pagaré ($)</span>
                  <input
                    type="number"
                    value={datos.montoPagare}
                    onChange={(e) => set("montoPagare", aNumero(e.target.value))}
                    className={INPUT}
                  />
                </label>
              )}
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
