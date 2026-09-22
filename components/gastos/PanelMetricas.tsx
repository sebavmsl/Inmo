"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FilaIngresoMetrica, FilaGastoMetrica } from "@/lib/gastos/metricas";
import { formatMoneda } from "@/lib/format";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
] as const;

/** Validado con el validador de paletas del skill dataviz (2 series, categórico, luz/oscuro). */
const COLOR_INGRESOS = "#1a9c6b";
const COLOR_GASTOS = "#c2410c";

function fmtMesAnio(yyyymm: string): string {
  const [anio, mes] = yyyymm.split("-");
  return `${MESES[Number(mes) - 1] ?? mes} ${anio}`;
}

/** ARS/USD por fila, según cotización individual de ESA fila (misma convención que Módulo 4). */
function aUsd(valorArs: number, cotizacion: number | null): number {
  return cotizacion && cotizacion > 0 ? valorArs / cotizacion : 0;
}

interface Props {
  ingresos: FilaIngresoMetrica[];
  gastos: FilaGastoMetrica[];
  propiedades: { alias: string; propietario: string; grupo: string | null }[];
  /** true = rol "propietario", ya viene todo pre-filtrado y no se muestra el selector de propietario. */
  ocultarFiltroPropietario: boolean;
}

/**
 * Módulo 2 (Tier B) — "Ingresos vs. Gastos por Propiedad". Puerto
 * simplificado de la subpestaña "📊 Métricas por Propiedad" de app.py
 * (ver nota de diseño en lib/gastos/metricas.ts sobre el mes calendario).
 * No replica el filtro "período de contrato" de v1 (Mes N de M) — acá
 * se filtra directo por mes/año calendario, que cubre el mismo caso de
 * uso de forma más simple.
 */
export function PanelMetricas({ ingresos, gastos, propiedades, ocultarFiltroPropietario }: Props) {
  const [propietarioSel, setPropietarioSel] = useState("Todos");
  const [propiedadSel, setPropiedadSel] = useState("Todas"); // "Todas" | `prop:<alias>` | `grupo:<grupo>`
  const [anioSel, setAnioSel] = useState("Todos");
  const [mesSel, setMesSel] = useState("Todos");
  const [moneda, setMoneda] = useState<"ARS" | "USD">("ARS");

  const propietarios = useMemo(
    () => Array.from(new Set(propiedades.map((p) => p.propietario).filter(Boolean))).sort(),
    [propiedades]
  );
  const grupos = useMemo(
    () => Array.from(new Set(propiedades.map((p) => p.grupo).filter((g): g is string => !!g))).sort(),
    [propiedades]
  );
  const anios = useMemo(() => {
    const todos = [...ingresos.map((i) => i.mes), ...gastos.map((g) => g.mes)].map((m) => m.slice(0, 4));
    return Array.from(new Set(todos)).sort().reverse();
  }, [ingresos, gastos]);

  function pasaFiltroComun(propiedad: string, propietario: string, grupo: string | null, mes: string): boolean {
    if (propietarioSel !== "Todos" && propietario !== propietarioSel) return false;
    if (propiedadSel.startsWith("prop:") && propiedad !== propiedadSel.slice(5)) return false;
    if (propiedadSel.startsWith("grupo:") && grupo !== propiedadSel.slice(6)) return false;
    if (anioSel !== "Todos" && mes.slice(0, 4) !== anioSel) return false;
    if (mesSel !== "Todos" && mes.slice(5, 7) !== mesSel) return false;
    return true;
  }

  const ingresosFiltrados = useMemo(
    () => ingresos.filter((i) => pasaFiltroComun(i.propiedad, i.propietario, i.grupo, i.mes)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ingresos, propietarioSel, propiedadSel, anioSel, mesSel]
  );
  const gastosFiltrados = useMemo(
    () => gastos.filter((g) => pasaFiltroComun(g.propiedad, g.propietario, g.grupo, g.mes)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [gastos, propietarioSel, propiedadSel, anioSel, mesSel]
  );

  const enUsd = moneda === "USD";
  const valorIngreso = (i: FilaIngresoMetrica) => (enUsd ? aUsd(i.totalIngreso, i.cotizacionUsd) : i.totalIngreso);
  const valorAdmin = (i: FilaIngresoMetrica) => (enUsd ? aUsd(i.gastoAdmin, i.cotizacionUsd) : i.gastoAdmin);
  const valorImpInmo = (i: FilaIngresoMetrica) => (enUsd ? aUsd(i.impInmobiliario, i.cotizacionUsd) : i.impInmobiliario);
  const valorGasto = (g: FilaGastoMetrica) => (enUsd ? aUsd(g.totalGasto, g.cotizacionUsd) : g.totalGasto);

  const totalIngreso = ingresosFiltrados.reduce((acc, i) => acc + valorIngreso(i), 0);
  const totalAlquiler = ingresosFiltrados.reduce((acc, i) => acc + (enUsd ? aUsd(i.alquiler, i.cotizacionUsd) : i.alquiler), 0);
  const totalCochera = ingresosFiltrados.reduce((acc, i) => acc + (enUsd ? aUsd(i.cochera, i.cotizacionUsd) : i.cochera), 0);
  const totalExpensas = ingresosFiltrados.reduce((acc, i) => acc + (enUsd ? aUsd(i.expensas, i.cotizacionUsd) : i.expensas), 0);
  const totalAdmin = ingresosFiltrados.reduce((acc, i) => acc + valorAdmin(i), 0);
  const totalImpInmo = ingresosFiltrados.reduce((acc, i) => acc + valorImpInmo(i), 0);
  const totalGastoProp = gastosFiltrados.reduce((acc, g) => acc + valorGasto(g), 0);
  const totalPasivos = totalGastoProp + totalAdmin + totalImpInmo;
  const balance = totalIngreso - totalPasivos;

  const datosGrafico = useMemo(() => {
    const porMes = new Map<string, { mes: string; Ingresos: number; Gastos: number }>();
    for (const i of ingresosFiltrados) {
      const fila = porMes.get(i.mes) ?? { mes: i.mes, Ingresos: 0, Gastos: 0 };
      fila.Ingresos += valorIngreso(i);
      porMes.set(i.mes, fila);
    }
    for (const g of gastosFiltrados) {
      const fila = porMes.get(g.mes) ?? { mes: g.mes, Ingresos: 0, Gastos: 0 };
      fila.Gastos += valorGasto(g);
      porMes.set(g.mes, fila);
    }
    return Array.from(porMes.values())
      .sort((a, b) => a.mes.localeCompare(b.mes))
      .map((f) => ({ ...f, mesLabel: fmtMesAnio(f.mes) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ingresosFiltrados, gastosFiltrados, moneda]);

  const simbolo = enUsd ? "U$S" : "$";
  const fmt = (v: number) => `${simbolo} ${v.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (propiedades.length === 0) {
    return <p className="text-sm text-brand-500">No hay propiedades para mostrar métricas todavía.</p>;
  }

  return (
    <div className="space-y-5">
      <p className="text-xs text-brand-400">
        Los valores en USD corresponden a la cotización registrada al momento de cada cobro/gasto.
      </p>

      <div>
        <p className="mb-2 text-xs font-medium text-brand-500">🔎 Filtros</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {!ocultarFiltroPropietario && (
            <label className="block text-sm">
              <span className="mb-1 block text-brand-700">Propietario</span>
              <select value={propietarioSel} onChange={(e) => setPropietarioSel(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
                <option>Todos</option>
                {propietarios.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Propiedad</span>
            <select value={propiedadSel} onChange={(e) => setPropiedadSel(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
              <option value="Todas">Todas</option>
              {grupos.map((g) => (
                <option key={g} value={`grupo:${g}`}>
                  🏢 {g} (grupo/edificio)
                </option>
              ))}
              {propiedades.map((p) => (
                <option key={p.alias} value={`prop:${p.alias}`}>
                  🏠 {p.alias}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Año</span>
            <select value={anioSel} onChange={(e) => setAnioSel(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
              <option>Todos</option>
              {anios.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-brand-700">Mes</span>
            <select value={mesSel} onChange={(e) => setMesSel(e.target.value)} className="w-full rounded border border-brand-100 px-2 py-1.5">
              <option value="Todos">Todos</option>
              {MESES.map((m, i) => (
                <option key={m} value={String(i + 1).padStart(2, "0")}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-3 flex items-center gap-3 text-sm">
          <span className="text-brand-700">Ver métricas en:</span>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={!enUsd} onChange={() => setMoneda("ARS")} /> $ Pesos
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={enUsd} onChange={() => setMoneda("USD")} /> U$S Dólares
          </label>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-brand-500">📥 Ingresos</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Total Ingresos" valor={fmt(totalIngreso)} />
          <Tile label="Alquiler" valor={fmt(totalAlquiler)} />
          <Tile label="Cochera" valor={fmt(totalCochera)} />
          <Tile label="Expensas cobradas" valor={fmt(totalExpensas)} />
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-brand-500">📤 Pasivos</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tile label="Gastos Propiedad" valor={fmt(totalGastoProp)} />
          <Tile label="Gasto Adm." valor={fmt(totalAdmin)} />
          <Tile label="Imp. Inmobiliario" valor={fmt(totalImpInmo)} />
          <Tile label="Balance Neto" valor={fmt(balance)} resaltado={balance >= 0 ? "positivo" : "negativo"} />
        </div>
      </div>

      {datosGrafico.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-brand-500">📊 Ingresos vs. Gastos</p>
          <div className="h-80 rounded-lg border border-brand-100 bg-white p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={datosGrafico} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" vertical={false} />
                <XAxis dataKey="mesLabel" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" width={70} tickFormatter={(v) => `${simbolo} ${Number(v).toLocaleString("es-AR")}`} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Legend />
                <Bar dataKey="Ingresos" fill={COLOR_INGRESOS} radius={[3, 3, 0, 0]} />
                <Bar dataKey="Gastos" fill={COLOR_GASTOS} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function Tile({ label, valor, resaltado }: { label: string; valor: string; resaltado?: "positivo" | "negativo" }) {
  const color = resaltado === "positivo" ? "text-green-700" : resaltado === "negativo" ? "text-red-700" : "text-brand-900";
  return (
    <div className="rounded-lg bg-brand-50 p-3 text-sm">
      <p className="text-xs text-brand-500">{label}</p>
      <p className={`font-semibold ${color}`}>{valor}</p>
    </div>
  );
}
