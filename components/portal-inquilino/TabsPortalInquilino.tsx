"use client";

import { useState } from "react";
import type { FilaComprobante, FilaReclamo } from "@/lib/portal-inquilino/queries";
import { BandejaComprobantes } from "@/components/portal-inquilino/BandejaComprobantes";
import { BandejaReclamos } from "@/components/portal-inquilino/BandejaReclamos";

type Tab = "comprobantes" | "reclamos";

export function TabsPortalInquilino({
  comprobantesIniciales,
  reclamosIniciales,
}: {
  comprobantesIniciales: FilaComprobante[];
  reclamosIniciales: FilaReclamo[];
}) {
  const [tab, setTab] = useState<Tab>("comprobantes");
  const [comprobantes, setComprobantes] = useState(comprobantesIniciales);
  const [reclamos, setReclamos] = useState(reclamosIniciales);

  function actualizarComprobante(id: number, cambios: Partial<FilaComprobante>) {
    setComprobantes((prev) => prev.map((c) => (c.id === id ? { ...c, ...cambios } : c)));
  }

  function actualizarReclamo(id: number, cambios: Partial<FilaReclamo>) {
    setReclamos((prev) => prev.map((r) => (r.id === id ? { ...r, ...cambios } : r)));
  }

  const pendientesComprobantes = comprobantes.filter((c) => c.estado === "pendiente").length;
  const pendientesReclamos = reclamos.filter((r) => r.estado !== "resuelto").length;

  const tabs: { id: Tab; label: string; badge: number }[] = [
    { id: "comprobantes", label: "📎 Comprobantes", badge: pendientesComprobantes },
    { id: "reclamos", label: "🛠️ Reclamos", badge: pendientesReclamos },
  ];

  return (
    <div>
      <div className="mb-4 flex gap-1 border-b border-brand-100">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium ${
              tab === t.id ? "border-b-2 border-brand-600 text-brand-800" : "text-brand-400 hover:text-brand-600"
            }`}
          >
            {t.label}
            {t.badge > 0 && (
              <span className="rounded-full bg-brand-100 px-1.5 py-0.5 text-xs font-semibold text-brand-700">{t.badge}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "comprobantes" && <BandejaComprobantes filas={comprobantes} onActualizar={actualizarComprobante} />}
      {tab === "reclamos" && <BandejaReclamos filas={reclamos} onActualizar={actualizarReclamo} />}
    </div>
  );
}
