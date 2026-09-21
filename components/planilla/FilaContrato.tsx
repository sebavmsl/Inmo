"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import clsx from "clsx";
import type { FilaPlanilla } from "@/lib/planilla/types";
import { toggleVerificado, actualizarExpensasAdhoc, archivarContrato } from "@/app/(protected)/planilla/actions";
import { formatMoneda } from "@/lib/format";

const COLOR_URGENCIA: Record<FilaPlanilla["urgencia"], string> = {
  actualizar_este_mes: "bg-amber-50",
  actualizar_mes_proximo: "bg-blue-50",
  renovar: "bg-red-50",
  normal: "",
};

export function FilaContrato({ fila, soloLectura }: { fila: FilaPlanilla; soloLectura: boolean }) {
  const [verificado, setVerificado] = useState(fila.verificado);
  const [expensas, setExpensas] = useState(fila.expensasAdhoc?.toString() ?? "");
  const [pendiente, startTransition] = useTransition();

  return (
    <tr
      className={clsx(
        "border-b border-brand-50 text-sm",
        fila.estadoVencido ? "bg-brand-50 text-brand-400" : COLOR_URGENCIA[fila.urgencia]
      )}
    >
      <td className="px-3 py-2">{fila.pagado ? "✅" : "⏳"}</td>
      <td className="px-3 py-2">
        {fila.aliasPropiedad}
        {fila.estadoVencido && (
          <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700">
            VENCIDO
          </span>
        )}
      </td>
      <td className="px-3 py-2">{fila.inquilino}</td>
      <td className="px-3 py-2">{formatMoneda(fila.alquilerMostrar)}</td>
      <td className="px-3 py-2">{fila.saldoActual > 0 ? formatMoneda(fila.saldoActual) : "—"}</td>
      <td className="px-3 py-2">
        <input
          type="number"
          value={expensas}
          disabled={soloLectura}
          placeholder="0"
          className="w-24 rounded border border-brand-100 px-2 py-1 text-sm"
          onChange={(e) => setExpensas(e.target.value)}
          onBlur={() =>
            startTransition(() => actualizarExpensasAdhoc(fila.codigo, expensas ? Number(expensas) : null))
          }
        />
      </td>
      <td className="px-3 py-2 text-center">
        {!soloLectura && !fila.estadoVencido && (
          <input
            type="checkbox"
            checked={verificado}
            disabled={pendiente}
            onChange={(e) => {
              setVerificado(e.target.checked);
              startTransition(() => toggleVerificado(fila.codigo, e.target.checked));
            }}
          />
        )}
      </td>
      <td className="px-3 py-2 text-right">
        {fila.estadoVencido ? (
          !soloLectura && (
            <button
              onClick={() => startTransition(() => archivarContrato(fila.codigo))}
              disabled={pendiente}
              className="text-xs text-brand-500 hover:underline"
            >
              🗄️ Archivar
            </button>
          )
        ) : (
          <Link href={`/pagos?contrato=${fila.codigo}`} className="text-xs text-brand-600 hover:underline">
            Ir a Pagos →
          </Link>
        )}
      </td>
    </tr>
  );
}
