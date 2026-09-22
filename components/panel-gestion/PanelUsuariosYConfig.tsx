"use client";

import { useEffect, useState } from "react";
import { obtenerConfiguracionEmpresa } from "@/app/(protected)/panel-gestion/actions";
import { GestionUsuarios } from "@/components/panel-gestion/GestionUsuarios";
import { Configuraciones } from "@/components/panel-gestion/Configuraciones";
import type { Rol } from "@/lib/types/database.types";

interface Props {
  rolViewer: Rol;
  permisosViewer: string[];
  /** superadmin: lista completa para elegir; admin: solo la propia (sin selector). */
  empresas: { id: number; nombreComercial: string }[];
  empresaIdFija: number | null;
}

/**
 * Envoltorio que decide QUÉ empresa se está gestionando: fija (la del
 * propio admin) o elegible con un selector (superadmin, que puede
 * gestionar cualquier empresa). Una vez resuelto el empresaId, arma
 * Usuarios + Configuraciones para esa empresa.
 */
export function PanelUsuariosYConfig({ rolViewer, permisosViewer, empresas, empresaIdFija }: Props) {
  const [empresaId, setEmpresaId] = useState<number | null>(empresaIdFija ?? empresas[0]?.id ?? null);
  const [config, setConfig] = useState<{
    actualizarAlquilerAuto: boolean;
    whatsappHabilitado: boolean;
    timeoutInactividadMinutos: number;
  } | null>(null);
  const [cargandoConfig, setCargandoConfig] = useState(true);

  useEffect(() => {
    if (empresaId === null) return;
    setCargandoConfig(true);
    obtenerConfiguracionEmpresa(empresaId).then((c) => {
      setConfig(c);
      setCargandoConfig(false);
    });
  }, [empresaId]);

  if (empresaId === null) {
    return <p className="text-sm text-brand-400">No hay empresas para gestionar todavía.</p>;
  }

  return (
    <div className="space-y-6">
      {empresaIdFija === null && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-brand-500">Empresa:</label>
          <select
            value={empresaId}
            onChange={(e) => setEmpresaId(Number(e.target.value))}
            className="rounded border border-brand-100 px-2 py-1.5 text-sm"
          >
            {empresas.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nombreComercial}
              </option>
            ))}
          </select>
        </div>
      )}

      <GestionUsuarios empresaId={empresaId} rolViewer={rolViewer} permisosViewer={permisosViewer} />

      {cargandoConfig ? (
        <p className="text-sm text-brand-400">Cargando configuración…</p>
      ) : config ? (
        <Configuraciones
          key={empresaId}
          empresaId={empresaId}
          actualizarAlquilerAuto={config.actualizarAlquilerAuto}
          whatsappHabilitado={config.whatsappHabilitado}
          timeoutInactividadMinutos={config.timeoutInactividadMinutos}
        />
      ) : (
        <p className="text-sm text-red-600">No se pudo cargar la configuración de esta empresa.</p>
      )}
    </div>
  );
}
