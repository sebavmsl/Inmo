"use client";

import { useState } from "react";
import { FormularioGasto } from "@/components/gastos/FormularioGasto";
import { TablaGastos } from "@/components/gastos/TablaGastos";
import { PanelMetricas } from "@/components/gastos/PanelMetricas";
import type { FilaGasto } from "@/lib/gastos/queries";
import type { FilaIngresoMetrica, FilaGastoMetrica } from "@/lib/gastos/metricas";

type Tab = "nuevo" | "historial" | "metricas";

interface Props {
  mostrarAlta: boolean;
  propiedades: { id: number; aliasPropiedad: string; grupo: string | null }[];
  historial: FilaGasto[];
  metricas: {
    ingresos: FilaIngresoMetrica[];
    gastos: FilaGastoMetrica[];
    propiedades: { alias: string; propietario: string; grupo: string | null }[];
  };
  ocultarFiltroPropietario: boolean;
}

/** Puerto de las 3 subpestañas de Gastos en app.py — ➕ Registrar / 📋 Historial / 📊 Métricas. */
export function TabsGastos({ mostrarAlta, propiedades, historial, metricas, ocultarFiltroPropietario }: Props) {
  const [tab, setTab] = useState<Tab>(mostrarAlta ? "nuevo" : "historial");

  const tabs: { id: Tab; label: string }[] = [
    ...(mostrarAlta ? [{ id: "nuevo" as const, label: "➕ Registrar Gasto" }] : []),
    { id: "historial", label: "📋 Historial de Gastos" },
    { id: "metricas", label: "📊 Métricas por Propiedad" },
  ];

  return (
    <div>
      <div className="mb-4 flex gap-1 border-b border-brand-100">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t.id ? "border-b-2 border-brand-600 text-brand-800" : "text-brand-400 hover:text-brand-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "nuevo" && mostrarAlta && <FormularioGasto propiedades={propiedades} />}
      {tab === "historial" && <TablaGastos filas={historial} />}
      {tab === "metricas" && (
        <PanelMetricas
          ingresos={metricas.ingresos}
          gastos={metricas.gastos}
          propiedades={metricas.propiedades}
          ocultarFiltroPropietario={ocultarFiltroPropietario}
        />
      )}
    </div>
  );
}
