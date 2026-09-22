"use client";

import { useState } from "react";

/**
 * Selector de propietario + período de Rendición. Soporta "Todos" en
 * ambos (puerto de los selectbox de app.py líneas 8327-8334) — antes
 * v2 exigía elegir un propietario puntual para ver cualquier cosa.
 * El rol `propietario` no ve la opción "Todos los propietarios": queda
 * fijo a lo suyo, igual que v1 (línea 8328-8330).
 */
export function SelectorRendicion({
  propietarios,
  propietarioInicial,
  periodoInicial, // "todos" | "YYYY-MM"
  soloPropioPropietario,
}: {
  propietarios: string[];
  propietarioInicial: string;
  periodoInicial: string;
  soloPropioPropietario: boolean;
}) {
  const [propietario, setPropietario] = useState(propietarioInicial);
  const [periodoModo, setPeriodoModo] = useState<"todos" | "especifico">(periodoInicial === "todos" ? "todos" : "especifico");
  const [periodoEspecifico, setPeriodoEspecifico] = useState(
    periodoInicial === "todos" ? new Date().toISOString().slice(0, 7) : periodoInicial
  );

  function navegar(prop: string, modo: "todos" | "especifico", esp: string) {
    const params = new URLSearchParams();
    if (prop) params.set("propietario", prop);
    params.set("periodo", modo === "todos" ? "todos" : esp);
    window.location.href = `/rendicion?${params.toString()}`;
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {!soloPropioPropietario ? (
        <select
          value={propietario}
          onChange={(e) => {
            setPropietario(e.target.value);
            navegar(e.target.value, periodoModo, periodoEspecifico);
          }}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        >
          <option value="">Todos los propietarios</option>
          {propietarios.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      ) : (
        <span className="text-sm text-brand-700">
          <strong>Propietario:</strong> {propietario}
        </span>
      )}

      <select
        value={periodoModo}
        onChange={(e) => {
          const modo = e.target.value as "todos" | "especifico";
          setPeriodoModo(modo);
          navegar(propietario, modo, periodoEspecifico);
        }}
        className="rounded border border-brand-100 px-2 py-1.5 text-sm"
      >
        <option value="todos">Todos los períodos</option>
        <option value="especifico">Un período específico</option>
      </select>

      {periodoModo === "especifico" && (
        <input
          type="month"
          value={periodoEspecifico}
          onChange={(e) => {
            setPeriodoEspecifico(e.target.value);
            navegar(propietario, "especifico", e.target.value);
          }}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        />
      )}
    </div>
  );
}
