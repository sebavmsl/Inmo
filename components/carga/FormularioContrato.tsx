"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { crearContrato, datosRenovacion, opcionesAlta, previsualizarAlta } from "@/app/(protected)/carga/actions";
import {
  CARGOS,
  ESTADOS_CONTRATO,
  FRECUENCIAS,
  INDICES,
  METODOS_PAGO,
  SERVICIOS,
  type DatosAltaContrato,
  type MesConfirmado,
  type OpcionesAlta,
  type PrevisualizacionAlta,
} from "@/lib/carga/tipos";
import {
  TIPOS_GARANTIA,
  aISO,
  aTextoAR,
  calcularDuracion,
  calcularMesActual,
  finPorDefecto,
  leerFechaISO,
  tieneDeposito,
  tienePagare,
  type Cargo,
  type TipoGarantia,
} from "@/lib/carga/calculoContrato";
import {
  INDICES_AUTOMATICOS,
  abonadoDelMes,
  mesConfirmadoPorDefecto,
  saldoFinal,
  totalDelMes,
} from "@/lib/carga/armadoAlta";
import { claveHoy } from "@/lib/fechas";
import { formatMoneda } from "@/lib/format";
import type { IndiceActualizacion } from "@/lib/types/database.types";

function primerDiaDelMes(): string {
  return `${claveHoy().slice(0, 7)}-01`;
}

function vacio(): DatosAltaContrato {
  const inicio = primerDiaDelMes();
  return {
    aliasPropiedad: "",
    dniInquilino: "",
    estado: "Activo",
    fechaInicio: inicio,
    finContrato: aISO(finPorDefecto(leerFechaISO(inicio)!)),
    diaVencimiento: 10,
    montoInicial: 0,
    indice: "ICL",
    frecuenciaMeses: 6,
    honorariosPct: 7,
    montoHonorarios: 0,
    cuotaHonorarios: 1,
    tipoGarantia: "Sin Garantía",
    montoGarantia: 0,
    cuotasDeposito: 1,
    montoPagare: 0,
    servicios: { expensas: 0, edesal: 0, gas: 0, municipalidad: 0, ooss: 0, impInmobiliario: 0 },
    cargos: {
      electricidad: "Inquilino",
      gas: "Inquilino",
      municipalidad: "Inquilino",
      ooss: "Inquilino",
      expensas: "Inquilino",
      impInmobiliario: "Propietario",
    },
    cargoGeneralServicios: 0,
    cochera: 0,
    cocheraActualizaConIndice: false,
    alquilerVigente: null,
    codigoAnterior: null,
  };
}

const INPUT = "w-full rounded border border-brand-100 px-2 py-1.5 disabled:bg-brand-50/60 disabled:text-brand-400";

function Campo({ label, children, ayuda }: { label: string; children: React.ReactNode; ayuda?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-brand-700">{label}</span>
      {children}
      {ayuda && <span className="mt-1 block text-xs text-brand-400">{ayuda}</span>}
    </label>
  );
}

function Numero({
  valor,
  onChange,
  step,
  min = 0,
  disabled,
}: {
  valor: number;
  onChange: (n: number) => void;
  step?: number;
  min?: number;
  disabled?: boolean;
}) {
  return (
    <input
      type="number"
      min={min}
      step={step ?? "any"}
      value={Number.isFinite(valor) ? valor : ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
      className={INPUT}
    />
  );
}

/**
 * Alta de contrato (Entrega 2 — V2.018). Dos pasos:
 *   1. Datos del contrato (código automático; propiedad e inquilino de lista).
 *   2. Revisión: duración, mes actual, próxima actualización, alquiler
 *      vigente y — si el contrato ya empezó — los meses transcurridos, cada
 *      uno Pagado o Adeudado, con ajuste, comisión y "paga ahora".
 * Con `renovarCodigo`, el formulario arranca precargado con el contrato a
 * renovar (mismo inquilino y condiciones, fechas a continuación).
 */
export function FormularioContrato({ renovarCodigo, mensajeInicial }: { renovarCodigo?: string; mensajeInicial?: string }) {
  const router = useRouter();
  const [datos, setDatos] = useState<DatosAltaContrato>(vacio);
  const [opciones, setOpciones] = useState<OpcionesAlta | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [finEditado, setFinEditado] = useState(false);
  const [honorariosEditado, setHonorariosEditado] = useState(false);
  const [depositoEditado, setDepositoEditado] = useState(false);

  const [prev, setPrev] = useState<PrevisualizacionAlta | null>(null);
  const [meses, setMeses] = useState<MesConfirmado[]>([]);
  const [alquilerVigente, setAlquilerVigente] = useState(0);
  const [trabajando, setTrabajando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; mensaje: string } | null>(
    mensajeInicial ? { ok: true, mensaje: mensajeInicial } : null
  );

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const op = await opcionesAlta();
        if (!vivo) return;
        setOpciones(op);
        if (renovarCodigo) {
          const r = await datosRenovacion(renovarCodigo);
          if (!vivo) return;
          if (r.ok && r.datos) {
            setDatos(r.datos);
            setFinEditado(true);
            setHonorariosEditado(true);
            setDepositoEditado(true);
          } else setErrorCarga(r.error ?? "No se pudo cargar el contrato a renovar.");
        }
      } catch (e) {
        if (vivo) setErrorCarga(e instanceof Error ? e.message : "Error cargando propiedades e inquilinos.");
      }
    })();
    return () => {
      vivo = false;
    };
  }, [renovarCodigo]);

  const enRevision = prev !== null;

  function set<K extends keyof DatosAltaContrato>(campo: K, valor: DatosAltaContrato[K]) {
    setDatos((d) => {
      const nuevo = { ...d, [campo]: valor };
      if (campo === "fechaInicio" && !finEditado) {
        const ini = leerFechaISO(valor as string);
        if (ini) nuevo.finContrato = aISO(finPorDefecto(ini));
      }
      if (campo === "montoInicial") {
        if (!honorariosEditado) nuevo.montoHonorarios = valor as number;
        if (!depositoEditado) nuevo.montoGarantia = valor as number;
      }
      if (campo === "indice" && !INDICES_AUTOMATICOS.includes(valor as string)) nuevo.cocheraActualizaConIndice = false;
      return nuevo;
    });
  }

  const resumenVivo = useMemo(() => {
    const ini = leerFechaISO(datos.fechaInicio);
    const fin = leerFechaISO(datos.finContrato);
    if (!ini || !fin || aISO(fin) <= aISO(ini)) return null;
    const hoy = leerFechaISO(claveHoy())!;
    return { duracion: calcularDuracion(ini, fin), mesActual: calcularMesActual(ini, hoy) };
  }, [datos.fechaInicio, datos.finContrato]);

  const propiedadElegida = opciones?.propiedades.find((p) => p.alias === datos.aliasPropiedad) ?? null;
  const cocheraConIndicePosible = INDICES_AUTOMATICOS.includes(datos.indice) && datos.frecuenciaMeses > 0;

  async function calcular() {
    setTrabajando(true);
    setResultado(null);
    const r = await previsualizarAlta(datos);
    setTrabajando(false);
    if (!r.ok || !r.previsualizacion) {
      setResultado({ ok: false, mensaje: r.error ?? "No se pudo calcular." });
      return;
    }
    const hoy = claveHoy();
    setPrev(r.previsualizacion);
    setMeses(r.previsualizacion.meses.map((m) => mesConfirmadoPorDefecto(m, hoy)));
    setAlquilerVigente(datos.alquilerVigente ?? r.previsualizacion.alquilerVigenteCalculado);
  }

  function volver() {
    setPrev(null);
    setMeses([]);
    setResultado(null);
  }

  function setMes(nro: number, cambios: Partial<MesConfirmado>) {
    setMeses((ms) =>
      ms.map((m) => {
        if (m.nro !== nro) return m;
        const nuevo = { ...m, ...cambios };
        // Decisión de Carga: comisión destildada si estaba Pagado, tildada si es Adeudado.
        if (cambios.estado && cambios.estado !== m.estado) {
          nuevo.comision = cambios.estado === "Adeudado";
          nuevo.pagaAhora = false;
        }
        if (cambios.ajuste !== undefined && !m.pagaAhora) nuevo.montoPagado = totalDelMes(nuevo);
        if (cambios.pagaAhora && !m.pagaAhora) nuevo.montoPagado = totalDelMes(nuevo);
        return nuevo;
      })
    );
  }

  function marcarTodos(estado: "Pagado" | "Adeudado") {
    setMeses((ms) => ms.map((m) => ({ ...m, estado, comision: estado === "Adeudado", pagaAhora: false })));
  }

  async function guardar() {
    if (!prev) return;
    setTrabajando(true);
    setResultado(null);
    const r = await crearContrato({ ...datos, alquilerVigente }, meses, alquilerVigente);
    if (!r.ok) {
      setTrabajando(false);
      setResultado({ ok: false, mensaje: r.error ?? "Error al crear el contrato." });
      return;
    }
    const cerrados = (r.cerrados ?? []).map((c) => `N° ${c.codigo} quedó ${c.estado}`).join(", ");
    const mensaje = `Contrato N° ${r.codigo} creado.${cerrados ? ` El contrato anterior de la propiedad (${cerrados}) se cerró por renovación.` : ""}${
      meses.length ? ` Se registraron ${meses.length} ${meses.length === 1 ? "mes anterior" : "meses anteriores"}.` : ""
    }`;
    // Se recarga la pantalla con el mensaje en la URL: rearma el alta vacía y
    // la lista de Edición, y sale de ?renovar= para que recargar la página no
    // vuelva a precargar (y a ofrecer guardar) la misma renovación.
    // `trabajando` queda en true a propósito: el botón no se puede volver a
    // apretar mientras se recarga (un segundo guardado crearía otro contrato).
    router.replace(`/carga?ok=${encodeURIComponent(mensaje)}`);
  }

  if (errorCarga) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
        ⚠️ {errorCarga}
      </div>
    );
  }
  if (!opciones) return <div className="rounded-lg border border-brand-100 bg-white p-5 text-sm text-brand-400">Cargando…</div>;

  const saldo = saldoFinal(meses);

  return (
    <div id="alta" className="space-y-5 rounded-lg border border-brand-100 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-brand-900">
          {datos.codigoAnterior ? `🔁 Renovar contrato N° ${datos.codigoAnterior}` : "➕ Nuevo contrato"}
        </h2>
        <span className="text-xs text-brand-400">El código del contrato lo asigna el sistema al guardar.</span>
      </div>

      {datos.codigoAnterior && !enRevision && (
        <p className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
          Precargado con los datos del contrato N° {datos.codigoAnterior}: mismo inquilino y condiciones, fechas a continuación
          y monto inicial igual al último alquiler. Honorarios y depósito arrancan de nuevo. Revisá todo antes de seguir.
        </p>
      )}

      <fieldset disabled={enRevision || trabajando} className="space-y-5">
        {/* 1. Propiedad, inquilino y estado */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">1. Propiedad e inquilino</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Campo label="Propiedad">
              <select value={datos.aliasPropiedad} onChange={(e) => set("aliasPropiedad", e.target.value)} className={INPUT}>
                <option value="">Elegir propiedad…</option>
                {opciones.propiedades.map((p) => (
                  <option key={p.alias} value={p.alias}>
                    {p.alias}
                    {p.direccion ? ` — ${p.direccion}` : ""}
                    {p.contratoActivo ? " (con contrato activo)" : ""}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo label="Inquilino">
              <select value={datos.dniInquilino} onChange={(e) => set("dniInquilino", e.target.value)} className={INPUT}>
                <option value="">Elegir inquilino…</option>
                {opciones.inquilinos.map((i) => (
                  <option key={i.dni} value={i.dni}>
                    {i.nombre} — DNI {i.dni}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo label="Estado del contrato">
              <select value={datos.estado} onChange={(e) => set("estado", e.target.value as DatosAltaContrato["estado"])} className={INPUT}>
                {ESTADOS_CONTRATO.map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </Campo>
          </div>
          {propiedadElegida?.contratoActivo && datos.estado === "Activo" && (
            <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Esta propiedad tiene el contrato activo N° {propiedadElegida.contratoActivo}. Al guardar se cierra: queda Finalizado
              si ya terminó o termina este mes, o Cancelado si se corta antes.
            </p>
          )}
          {opciones.propiedades.length === 0 && (
            <p className="text-xs text-brand-500">No hay propiedades cargadas. Cargalas en Auxiliares.</p>
          )}
        </section>

        {/* 2. Fechas */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">2. Fechas y vencimiento</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Campo label="Inicio del contrato">
              <input type="date" value={datos.fechaInicio} onChange={(e) => set("fechaInicio", e.target.value)} className={INPUT} />
            </Campo>
            <Campo label="Fin del contrato">
              <input
                type="date"
                value={datos.finContrato}
                onChange={(e) => {
                  setFinEditado(true);
                  set("finContrato", e.target.value);
                }}
                className={INPUT}
              />
            </Campo>
            <Campo label="Día de vencimiento" ayuda="Si el mes tiene menos días, vence el último.">
              <Numero valor={datos.diaVencimiento} min={1} step={1} onChange={(n) => set("diaVencimiento", Math.round(n))} />
            </Campo>
            <div className="text-sm">
              <span className="mb-1 block text-brand-700">Duración</span>
              <p className="py-1.5 text-brand-900">
                {resumenVivo ? `${resumenVivo.duracion} meses` : "—"}
                {resumenVivo && resumenVivo.mesActual > 1 && (
                  <span className="block text-xs text-brand-500">Hoy corre el mes {resumenVivo.mesActual}.</span>
                )}
              </p>
            </div>
          </div>
        </section>

        {/* 3. Alquiler */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">3. Alquiler y actualización</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Campo label="Monto inicial ($)">
              <Numero valor={datos.montoInicial} step={1000} onChange={(n) => set("montoInicial", n)} />
            </Campo>
            <Campo label="Índice">
              <select value={datos.indice} onChange={(e) => set("indice", e.target.value as IndiceActualizacion)} className={INPUT}>
                {INDICES.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo label="Frecuencia de actualización">
              <select value={datos.frecuenciaMeses} onChange={(e) => set("frecuenciaMeses", Number(e.target.value))} className={INPUT}>
                {FRECUENCIAS.map((f) => (
                  <option key={f.meses} value={f.meses}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo label="% de comisión mensual" ayuda="A cargo del propietario (retención).">
              <Numero valor={datos.honorariosPct} step={0.5} onChange={(n) => set("honorariosPct", n)} />
            </Campo>
          </div>
        </section>

        {/* 4. Honorarios */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">4. Honorarios de la inmobiliaria (a cargo del inquilino)</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Campo label="Total de honorarios ($)" ayuda="Por defecto, el monto inicial.">
              <Numero
                valor={datos.montoHonorarios}
                step={1000}
                onChange={(n) => {
                  setHonorariosEditado(true);
                  set("montoHonorarios", n);
                }}
              />
            </Campo>
            <Campo label="Cuotas">
              <Numero valor={datos.cuotaHonorarios} min={1} step={1} onChange={(n) => set("cuotaHonorarios", Math.max(1, Math.round(n)))} />
            </Campo>
            <div className="text-sm">
              <span className="mb-1 block text-brand-700">Valor por cuota</span>
              <p className="py-1.5 text-brand-900">{formatMoneda(datos.montoHonorarios / Math.max(1, datos.cuotaHonorarios))}</p>
            </div>
          </div>
        </section>

        {/* 5. Garantía */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">5. Garantía</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Campo label="Tipo de garantía">
              <select
                value={datos.tipoGarantia}
                onChange={(e) => set("tipoGarantia", e.target.value as TipoGarantia)}
                className={INPUT}
              >
                {TIPOS_GARANTIA.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Campo>
            {tieneDeposito(datos.tipoGarantia) && (
              <>
                <Campo
                  label="Depósito ($)"
                  ayuda={datos.codigoAnterior ? "Si se mantiene el depósito del contrato anterior, dejalo en 0." : "Por defecto, el monto inicial."}
                >
                  <Numero
                    valor={datos.montoGarantia}
                    step={1000}
                    onChange={(n) => {
                      setDepositoEditado(true);
                      set("montoGarantia", n);
                    }}
                  />
                </Campo>
                <Campo label="Cuotas del depósito">
                  <Numero valor={datos.cuotasDeposito} min={1} step={1} onChange={(n) => set("cuotasDeposito", Math.max(1, Math.round(n)))} />
                </Campo>
              </>
            )}
            {tienePagare(datos.tipoGarantia) && (
              <Campo label="Monto del pagaré ($)" ayuda="Solo informativo, no suma al cobro.">
                <Numero valor={datos.montoPagare} step={1000} onChange={(n) => set("montoPagare", n)} />
              </Campo>
            )}
          </div>
        </section>

        {/* 6. Servicios */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-800">6. Servicios, cargo general y cochera (montos del mes)</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {SERVICIOS.map((sv) => (
              <div key={sv.monto} className="grid grid-cols-[1fr_auto] items-end gap-2">
                <Campo label={`${sv.label} ($)`}>
                  <Numero
                    valor={datos.servicios[sv.monto]}
                    step={500}
                    onChange={(n) => set("servicios", { ...datos.servicios, [sv.monto]: n })}
                  />
                </Campo>
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
          <p className="text-xs text-brand-400">Solo se cobran al inquilino los servicios a su cargo.</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Campo label="Cargo general de servicios ($)" ayuda="Para contratos que cobran los servicios en un solo monto.">
              <Numero valor={datos.cargoGeneralServicios} step={500} onChange={(n) => set("cargoGeneralServicios", n)} />
            </Campo>
            <Campo label="Cochera — monto inicial ($)">
              <Numero valor={datos.cochera} step={500} onChange={(n) => set("cochera", n)} />
            </Campo>
            <label className={`flex items-start gap-2 pt-6 text-sm ${cocheraConIndicePosible ? "text-brand-700" : "text-brand-300"}`}>
              <input
                type="checkbox"
                checked={datos.cocheraActualizaConIndice}
                disabled={!cocheraConIndicePosible}
                onChange={(e) => set("cocheraActualizaConIndice", e.target.checked)}
                className="mt-0.5"
              />
              <span>
                La cochera se actualiza con el índice
                <span className="block text-xs text-brand-400">Solo con ICL, IPC o UVA. Sube en la misma proporción que el alquiler.</span>
              </span>
            </label>
          </div>
        </section>
      </fieldset>

      {resultado && (
        <p className={`rounded-md px-3 py-2 text-sm ${resultado.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {resultado.mensaje}
        </p>
      )}

      {!enRevision && (
        <button
          onClick={calcular}
          disabled={trabajando}
          className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {trabajando ? "Calculando… (puede tardar si consulta el índice)" : "Calcular y revisar →"}
        </button>
      )}

      {prev && (
        <section className="space-y-4 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
          <h3 className="text-sm font-semibold text-brand-900">Revisión antes de guardar</h3>
          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <span className="block text-brand-500">Duración</span>
              <span className="text-brand-900">{prev.duracion} meses</span>
            </div>
            <div>
              <span className="block text-brand-500">Mes que corre hoy</span>
              <span className="text-brand-900">
                Mes {Math.min(prev.mesActual, prev.duracion)} de {prev.duracion}
              </span>
            </div>
            <div>
              <span className="block text-brand-500">Próxima actualización</span>
              <span className="text-brand-900">
                {datos.frecuenciaMeses > 0 ? aTextoAR(leerFechaISO(prev.proxActualizacion)!) : "Sin actualización"}
              </span>
              {prev.necesitaRenovacion && <span className="block text-xs text-red-600">Cae después del fin: RENOVAR.</span>}
            </div>
            <Campo label="Alquiler vigente hoy ($)" ayuda={`Calculado: ${formatMoneda(prev.alquilerVigenteCalculado)}. Podés corregirlo.`}>
              <Numero valor={alquilerVigente} step={1000} onChange={setAlquilerVigente} />
            </Campo>
          </div>

          {prev.avisos.map((a) => (
            <p key={a} className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              ⚠️ {a}
            </p>
          ))}

          {meses.length > 0 ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-brand-800">
                  El contrato ya empezó: se registran {meses.length} {meses.length === 1 ? "mes anterior" : "meses anteriores"}. El mes
                  actual se cobra después desde Pagos.
                </p>
                <div className="flex gap-2 text-xs">
                  <button onClick={() => marcarTodos("Pagado")} className="rounded border border-brand-200 px-2 py-1 hover:bg-white">
                    Todos Pagado
                  </button>
                  <button onClick={() => marcarTodos("Adeudado")} className="rounded border border-brand-200 px-2 py-1 hover:bg-white">
                    Todos Adeudado
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b border-brand-100 text-left text-brand-600">
                      <th className="px-2 py-1.5">Mes</th>
                      <th className="px-2 py-1.5">Vence</th>
                      <th className="px-2 py-1.5 text-right">Alquiler</th>
                      <th className="px-2 py-1.5 text-right">Servicios y cochera</th>
                      <th className="px-2 py-1.5 text-right">Cuotas</th>
                      <th className="px-2 py-1.5">Estado</th>
                      <th className="px-2 py-1.5">Ajuste ±</th>
                      <th className="px-2 py-1.5 text-right">Total</th>
                      <th className="px-2 py-1.5 text-center">Comisión</th>
                      <th className="px-2 py-1.5">Paga ahora</th>
                    </tr>
                  </thead>
                  <tbody>
                    {meses.map((m) => {
                      const otros = m.cochera + m.expensas + m.edesal + m.gas + m.municipalidad + m.ooss + m.impInmobiliario + m.cargoGeneral;
                      return (
                        <tr key={m.nro} className="border-b border-brand-50 align-top">
                          <td className="px-2 py-1.5">
                            <span className="block text-brand-900">{m.periodo}</span>
                            <span className="text-brand-400">{m.mesCalendario}</span>
                          </td>
                          <td className="px-2 py-1.5">{aTextoAR(leerFechaISO(m.vencimiento)!)}</td>
                          <td className="px-2 py-1.5 text-right">
                            {!m.indiceOk && <span title="No se pudo consultar el índice">⚠️ </span>}
                            {formatMoneda(m.alquiler)}
                          </td>
                          <td className="px-2 py-1.5 text-right">{formatMoneda(otros)}</td>
                          <td className="px-2 py-1.5 text-right">{formatMoneda(m.honorarios + m.garantia)}</td>
                          <td className="px-2 py-1.5">
                            <select
                              value={m.estado}
                              onChange={(e) => setMes(m.nro, { estado: e.target.value as MesConfirmado["estado"] })}
                              className="rounded border border-brand-100 px-1 py-1"
                            >
                              <option value="Pagado">Pagado</option>
                              <option value="Adeudado">Adeudado</option>
                            </select>
                          </td>
                          <td className="px-2 py-1.5">
                            <input
                              type="number"
                              step="any"
                              value={m.ajuste}
                              onChange={(e) => setMes(m.nro, { ajuste: e.target.value === "" ? 0 : Number(e.target.value) })}
                              className="w-24 rounded border border-brand-100 px-1 py-1"
                            />
                          </td>
                          <td className="px-2 py-1.5 text-right font-medium text-brand-900">{formatMoneda(totalDelMes(m))}</td>
                          <td className="px-2 py-1.5 text-center">
                            <input type="checkbox" checked={m.comision} onChange={(e) => setMes(m.nro, { comision: e.target.checked })} />
                          </td>
                          <td className="px-2 py-1.5">
                            {m.estado === "Adeudado" ? (
                              <div className="space-y-1">
                                <label className="flex items-center gap-1">
                                  <input type="checkbox" checked={m.pagaAhora} onChange={(e) => setMes(m.nro, { pagaAhora: e.target.checked })} />
                                  <span>Paga ahora</span>
                                </label>
                                {m.pagaAhora && (
                                  <div className="space-y-1">
                                    <input
                                      type="number"
                                      step="any"
                                      min={0}
                                      value={m.montoPagado}
                                      onChange={(e) => setMes(m.nro, { montoPagado: e.target.value === "" ? 0 : Number(e.target.value) })}
                                      className="w-28 rounded border border-brand-100 px-1 py-1"
                                      aria-label="Monto que paga"
                                    />
                                    <input
                                      type="date"
                                      value={m.fechaPago}
                                      max={claveHoy()}
                                      onChange={(e) => setMes(m.nro, { fechaPago: e.target.value })}
                                      className="w-32 rounded border border-brand-100 px-1 py-1"
                                      aria-label="Fecha del pago"
                                    />
                                    <select
                                      value={m.metodoPago}
                                      onChange={(e) => setMes(m.nro, { metodoPago: e.target.value })}
                                      className="w-32 rounded border border-brand-100 px-1 py-1"
                                      aria-label="Método de pago"
                                    >
                                      {METODOS_PAGO.map((mp) => (
                                        <option key={mp} value={mp}>
                                          {mp}
                                        </option>
                                      ))}
                                    </select>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="text-brand-300">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                <span>
                  Total de los meses: <strong>{formatMoneda(meses.reduce((a, m) => a + totalDelMes(m), 0))}</strong>
                </span>
                <span>
                  Abonado: <strong>{formatMoneda(meses.reduce((a, m) => a + abonadoDelMes(m), 0))}</strong>
                </span>
                <span className={saldo > 0 ? "text-red-700" : saldo < 0 ? "text-green-700" : ""}>
                  Saldo que queda en la cuenta corriente: <strong>{formatMoneda(saldo)}</strong>
                  {saldo < 0 && " (a favor del inquilino)"}
                </span>
              </div>
              <p className="text-xs text-brand-400">
                Pagado: se registra con fecha de vencimiento de ese mes y método &quot;Carga inicial&quot;. Adeudado: queda en la cuenta
                corriente; si paga ahora, el cobro cuenta en la caja de la fecha de pago. Por ahora no se envía comprobante ni WhatsApp de
                estos meses.
              </p>
            </div>
          ) : (
            <p className="text-sm text-brand-700">El contrato arranca este mes o más adelante: no hay meses anteriores para registrar.</p>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={guardar}
              disabled={trabajando || !(alquilerVigente > 0)}
              className="rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {trabajando ? "Guardando…" : "💾 Guardar contrato"}
            </button>
            <button
              onClick={volver}
              disabled={trabajando}
              className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-white"
            >
              ← Volver a editar
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
