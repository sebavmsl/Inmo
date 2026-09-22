"use client";

import { useState, useTransition } from "react";
import type { FilaReclamo, EstadoReclamo, GastoReciente } from "@/lib/portal-inquilino/queries";
import {
  actualizarReclamo,
  vincularGastoAReclamo,
  crearGastoDesdeReclamo,
  listarGastosRecientesAction,
  type DatosGastoDesdeReclamo,
} from "@/app/(protected)/portal-inquilino/actions";
import { formatMoneda } from "@/lib/format";
import { CampoCotizacionUsd } from "@/components/cotizacion/CampoCotizacionUsd";

const ETIQUETA_ESTADO: Record<EstadoReclamo, string> = {
  abierto: "🔴 Abierto",
  en_progreso: "🟡 En progreso",
  resuelto: "🟢 Resuelto",
};

const PAGADO_POR = ["Inmobiliaria", "Propietario", "Inquilino", "Otro"] as const;

export function BandejaReclamos({
  filas,
  onActualizar,
}: {
  filas: FilaReclamo[];
  onActualizar: (id: number, cambios: Partial<FilaReclamo>) => void;
}) {
  const [filtro, setFiltro] = useState<EstadoReclamo | "todos">("todos");
  const [expandidoId, setExpandidoId] = useState<number | null>(null);

  const filasFiltradas = filtro === "todos" ? filas : filas.filter((f) => f.estado === filtro);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-brand-700">Estado:</span>
        <select
          value={filtro}
          onChange={(e) => setFiltro(e.target.value as typeof filtro)}
          className="rounded border border-brand-100 px-2 py-1.5"
        >
          <option value="todos">Todos</option>
          <option value="abierto">Abiertos</option>
          <option value="en_progreso">En progreso</option>
          <option value="resuelto">Resueltos</option>
        </select>
      </div>

      {filasFiltradas.length === 0 ? (
        <p className="text-sm text-brand-500">No hay reclamos en ese estado.</p>
      ) : (
        <div className="space-y-2">
          {filasFiltradas.map((f) => (
            <FilaReclamoCard
              key={f.id}
              fila={f}
              expandido={expandidoId === f.id}
              onToggle={() => setExpandidoId(expandidoId === f.id ? null : f.id)}
              onActualizar={onActualizar}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FilaReclamoCard({
  fila,
  expandido,
  onToggle,
  onActualizar,
}: {
  fila: FilaReclamo;
  expandido: boolean;
  onToggle: () => void;
  onActualizar: (id: number, cambios: Partial<FilaReclamo>) => void;
}) {
  const [estado, setEstado] = useState<EstadoReclamo>(fila.estado);
  const [respuesta, setRespuesta] = useState(fila.respuestaStaff ?? "");
  const [guardando, startGuardar] = useTransition();
  const [mensaje, setMensaje] = useState<string | null>(null);

  function handleGuardar() {
    setMensaje(null);
    startGuardar(async () => {
      const res = await actualizarReclamo(fila.id, estado, respuesta);
      setMensaje(res.ok ? "Guardado." : res.error ?? "Error al guardar.");
      if (res.ok) onActualizar(fila.id, { estado, respuestaStaff: respuesta || null });
    });
  }

  return (
    <div className="rounded-lg border border-brand-100 bg-white">
      <button onClick={onToggle} className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm">
        <div>
          <span className="font-medium text-brand-800">{fila.propiedad}</span>
          <span className="ml-2 text-brand-500">· {fila.inquilino}</span>
          <span className="ml-2 text-brand-400">· {new Date(fila.fecha).toLocaleDateString("es-AR")}</span>
          <p className="mt-0.5 text-brand-600">{fila.descripcion}</p>
        </div>
        <span className="shrink-0 text-xs font-medium">{ETIQUETA_ESTADO[fila.estado]}</span>
      </button>

      {expandido && (
        <div className="space-y-4 border-t border-brand-50 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Estado</span>
              <select
                value={estado}
                onChange={(e) => setEstado(e.target.value as EstadoReclamo)}
                className="w-full rounded border border-brand-100 px-2 py-1.5"
              >
                <option value="abierto">Abierto</option>
                <option value="en_progreso">En progreso</option>
                <option value="resuelto">Resuelto</option>
              </select>
            </label>
          </div>

          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Respuesta al inquilino</span>
            <textarea
              value={respuesta}
              onChange={(e) => setRespuesta(e.target.value)}
              rows={3}
              className="w-full rounded border border-brand-100 px-2 py-1.5"
            />
          </label>

          {mensaje && <p className="text-sm text-brand-600">{mensaje}</p>}

          <button
            onClick={handleGuardar}
            disabled={guardando}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {guardando ? "Guardando…" : "Guardar"}
          </button>

          <div className="border-t border-brand-50 pt-4">
            <VinculoGasto fila={fila} onActualizar={onActualizar} />
          </div>
        </div>
      )}
    </div>
  );
}

function VinculoGasto({
  fila,
  onActualizar,
}: {
  fila: FilaReclamo;
  onActualizar: (id: number, cambios: Partial<FilaReclamo>) => void;
}) {
  const [modo, setModo] = useState<"ninguno" | "vincular" | "crear">("ninguno");
  const [gastosRecientes, setGastosRecientes] = useState<GastoReciente[] | null>(null);
  const [gastoSeleccionado, setGastoSeleccionado] = useState<number | "">("");
  const [pendiente, startTransition] = useTransition();
  const [mensaje, setMensaje] = useState<string | null>(null);

  async function abrirVincular() {
    setModo("vincular");
    if (!gastosRecientes && fila.propiedadId) {
      const gastos = await listarGastosRecientesAction(fila.propiedadId);
      setGastosRecientes(gastos);
    }
  }

  function handleVincular() {
    if (!gastoSeleccionado) return;
    setMensaje(null);
    startTransition(async () => {
      const res = await vincularGastoAReclamo(fila.id, Number(gastoSeleccionado));
      if (!res.ok) {
        setMensaje(res.error ?? "Error al vincular.");
        return;
      }
      const gasto = gastosRecientes?.find((g) => g.id === Number(gastoSeleccionado));
      onActualizar(fila.id, { gastoId: Number(gastoSeleccionado), gastoDescripcion: gasto?.descripcion ?? null, gastoMonto: gasto?.monto ?? null });
      setModo("ninguno");
    });
  }

  if (fila.gastoId) {
    return (
      <p className="text-sm text-brand-600">
        🔗 Vinculado al gasto #{fila.gastoId} — {fila.gastoDescripcion} ({fila.gastoMonto !== null ? formatMoneda(fila.gastoMonto) : "—"})
      </p>
    );
  }

  if (!fila.propiedadId) {
    return <p className="text-sm text-brand-400">No se pudo resolver la propiedad de este contrato para vincular un gasto.</p>;
  }

  if (modo === "ninguno") {
    return (
      <div className="flex gap-2 text-sm">
        <button onClick={abrirVincular} className="rounded border border-brand-200 px-3 py-1.5 text-brand-600 hover:bg-brand-50">
          Vincular a un gasto ya cargado
        </button>
        <button onClick={() => setModo("crear")} className="rounded border border-brand-200 px-3 py-1.5 text-brand-600 hover:bg-brand-50">
          + Crear el gasto que lo resuelve
        </button>
      </div>
    );
  }

  if (modo === "vincular") {
    return (
      <div className="space-y-2">
        {gastosRecientes === null ? (
          <p className="text-sm text-brand-400">Cargando gastos recientes de la propiedad…</p>
        ) : gastosRecientes.length === 0 ? (
          <p className="text-sm text-brand-400">No hay gastos cargados todavía para esta propiedad.</p>
        ) : (
          <select
            value={gastoSeleccionado}
            onChange={(e) => setGastoSeleccionado(e.target.value ? Number(e.target.value) : "")}
            className="w-full max-w-md rounded border border-brand-100 px-2 py-1.5 text-sm"
          >
            <option value="">Seleccionar…</option>
            {gastosRecientes.map((g) => (
              <option key={g.id} value={g.id}>
                {new Date(g.fecha).toLocaleDateString("es-AR")} · {g.descripcion} · {formatMoneda(g.monto)}
              </option>
            ))}
          </select>
        )}
        {mensaje && <p className="text-sm text-red-600">{mensaje}</p>}
        <div className="flex gap-2">
          <button
            onClick={handleVincular}
            disabled={!gastoSeleccionado || pendiente}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            Vincular
          </button>
          <button onClick={() => setModo("ninguno")} className="rounded border border-brand-100 px-3 py-1.5 text-sm text-brand-500">
            Cancelar
          </button>
        </div>
      </div>
    );
  }

  return <FormularioCrearGasto fila={fila} onCancelar={() => setModo("ninguno")} onActualizar={onActualizar} />;
}

function FormularioCrearGasto({
  fila,
  onCancelar,
  onActualizar,
}: {
  fila: FilaReclamo;
  onCancelar: () => void;
  onActualizar: (id: number, cambios: Partial<FilaReclamo>) => void;
}) {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [categoria, setCategoria] = useState("");
  const [descripcion, setDescripcion] = useState(fila.descripcion);
  const [monto, setMonto] = useState(0);
  const [proveedor, setProveedor] = useState("");
  const [pagadoPor, setPagadoPor] = useState<(typeof PAGADO_POR)[number]>("Propietario");
  const [tipoGasto, setTipoGasto] = useState("Extraordinario");
  const [cotizacionUsd, setCotizacionUsd] = useState(0);
  const [enviando, startTransition] = useTransition();
  const [mensaje, setMensaje] = useState<string | null>(null);

  function handleCrear() {
    if (!fila.propiedadId) return;
    setMensaje(null);
    const datos: DatosGastoDesdeReclamo = {
      propiedadId: fila.propiedadId,
      fecha,
      categoria,
      descripcion,
      monto,
      proveedor,
      pagadoPor,
      tipoGasto,
      cotizacionUsd: cotizacionUsd || null,
    };
    startTransition(async () => {
      const res = await crearGastoDesdeReclamo(fila.id, datos);
      setMensaje(res.ok ? "Gasto creado y vinculado." : res.error ?? "Error al crear el gasto.");
      if (res.ok && res.gastoId) onActualizar(fila.id, { gastoId: res.gastoId, gastoDescripcion: descripcion, gastoMonto: monto });
    });
  }

  return (
    <div className="space-y-3 rounded-md bg-brand-50 p-3">
      <p className="text-xs text-brand-500">Propiedad precargada ({fila.propiedad}) — completá el resto para registrar el gasto.</p>
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
        <CampoCotizacionUsd valor={cotizacionUsd} onChange={setCotizacionUsd} />
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-brand-700">Descripción</span>
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5" />
      </label>

      {mensaje && <p className="text-sm text-brand-600">{mensaje}</p>}

      <div className="flex gap-2">
        <button
          onClick={handleCrear}
          disabled={enviando || !categoria || !descripcion || monto <= 0}
          className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {enviando ? "Creando…" : "Crear gasto y vincular"}
        </button>
        <button onClick={onCancelar} className="rounded border border-brand-100 px-3 py-1.5 text-sm text-brand-500">
          Cancelar
        </button>
      </div>
    </div>
  );
}
