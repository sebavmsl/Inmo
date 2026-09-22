"use client";

import { useEffect, useState } from "react";
import {
  listarUsuariosEditables,
  crearUsuarioEnEmpresa,
  actualizarUsuario,
  type UsuarioEditable,
} from "@/app/(protected)/panel-gestion/actions";
import { PESTANAS_MAESTRAS, PERMISOS_TRANSVERSALES } from "@/lib/auth/permissions";
import { usePresencia } from "@/lib/concurrencia/usePresencia";
import type { Rol } from "@/lib/types/database.types";

/**
 * Qué roles puede asignar quien está mirando esta pantalla — mismo
 * criterio que puedeAsignarRol() en actions.ts, repetido acá solo para
 * armar el <select>; la validación real vive del lado del servidor.
 */
const ROLES_ASIGNABLES: Record<Rol, Rol[]> = {
  superadmin: ["admin", "user", "propietario"],
  admin: ["user", "propietario"],
  user: [],
  propietario: [],
};

interface Props {
  empresaId: number;
  rolViewer: Rol;
  permisosViewer: string[];
}

/**
 * Alta y edición de usuarios de una empresa, con su rol y sus permisos
 * (pestañas + permisos transversales como WhatsApp o cotización
 * manual). Reemplaza el bloqueo anterior de Panel de Gestión a
 * "solo superadmin" — admin ahora gestiona el staff de su propia
 * empresa acá (ver docs/DESIGN_LOG.md, Módulo 1).
 *
 * Usa el módulo transversal "Ediciones simultáneas"
 * (lib/concurrencia/usePresencia.ts) al editar un usuario existente:
 * avisa si alguien más tiene el mismo usuario abierto, y bloquea el
 * guardado si alguien más guardó cambios primero (optimistic locking).
 */
export function GestionUsuarios({ empresaId, rolViewer, permisosViewer }: Props) {
  const [usuarios, setUsuarios] = useState<UsuarioEditable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState<UsuarioEditable | "nuevo" | null>(null);

  async function recargar() {
    setCargando(true);
    setUsuarios(await listarUsuariosEditables(empresaId));
    setCargando(false);
  }

  useEffect(() => {
    setEditando(null);
    recargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empresaId]);

  const rolesAsignables = ROLES_ASIGNABLES[rolViewer];

  return (
    <div className="space-y-3 rounded-lg border border-brand-100 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-brand-800">👥 Usuarios de la empresa</h2>
        {rolesAsignables.length > 0 && (
          <button
            onClick={() => setEditando("nuevo")}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700"
          >
            + Nuevo usuario
          </button>
        )}
      </div>

      {cargando ? (
        <p className="text-sm text-brand-400">Cargando…</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-brand-100 text-xs text-brand-400">
              <th className="py-1.5">Usuario</th>
              <th>Email</th>
              <th>Rol</th>
              <th>Acceso</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id} className="border-b border-brand-50">
                <td className="py-1.5">{u.username}</td>
                <td className="text-brand-500">{u.email ?? "-"}</td>
                <td className="capitalize text-brand-500">{u.rol}</td>
                <td>{u.tieneAcceso ? "✓" : "—"}</td>
                <td className="text-right">
                  {(u.rol === "superadmin" ? rolViewer === "superadmin" : true) && u.rol !== "superadmin" ? (
                    <button onClick={() => setEditando(u)} className="text-xs text-brand-600 hover:underline">
                      Editar
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {usuarios.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-center text-brand-400">
                  Sin usuarios todavía.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {editando && (
        <FormularioUsuario
          empresaId={empresaId}
          rolViewer={rolViewer}
          permisosViewer={permisosViewer}
          rolesAsignables={rolesAsignables}
          usuario={editando === "nuevo" ? null : editando}
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

function FormularioUsuario({
  empresaId,
  rolViewer,
  permisosViewer,
  rolesAsignables,
  usuario,
  onCancelar,
  onGuardado,
}: {
  empresaId: number;
  rolViewer: Rol;
  permisosViewer: string[];
  rolesAsignables: Rol[];
  usuario: UsuarioEditable | null;
  onCancelar: () => void;
  onGuardado: () => void;
}) {
  const [username, setUsername] = useState(usuario?.username ?? "");
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [telefono, setTelefono] = useState(usuario?.telefono ?? "");
  const [rol, setRol] = useState<Rol>(usuario?.rol ?? rolesAsignables[0] ?? "user");
  const [propietarioFiltro, setPropietarioFiltro] = useState(usuario?.propietarioFiltro ?? "");
  const [permisos, setPermisos] = useState<string[]>(usuario?.permisos ?? []);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);

  // Presencia en vivo — solo tiene sentido en edición (un alta todavía
  // no tiene id de fila). La lista ya viene filtrada sin el propio
  // usuario y sin superadmin (ver lib/concurrencia/queries.ts).
  const otrosEditando = usePresencia("usuarios_central", usuario ? String(usuario.id) : null);

  // superadmin puede otorgar cualquier permiso; admin/user solo los que
  // él mismo tiene (regla confirmada, ver DESIGN_LOG.md).
  const puedeOtorgar = (clave: string) => rolViewer === "superadmin" || permisosViewer.includes(clave);

  function togglePermiso(clave: string) {
    if (!puedeOtorgar(clave)) return;
    setPermisos((prev) => (prev.includes(clave) ? prev.filter((p) => p !== clave) : [...prev, clave]));
  }

  async function handleSubmit() {
    setGuardando(true);
    setError(null);
    setConflicto(false);
    const res = usuario
      ? await actualizarUsuario({
          id: usuario.id,
          username,
          telefono,
          rol,
          propietarioFiltro: propietarioFiltro || null,
          permisos,
          updatedAtEsperado: usuario.updatedAt,
        })
      : await crearUsuarioEnEmpresa({
          empresaId,
          username,
          email,
          telefono,
          rol,
          propietarioFiltro: propietarioFiltro || null,
          permisos,
        });
    setGuardando(false);
    if (!res.ok) {
      setError(res.error ?? "Error al guardar.");
      setConflicto(!!res.conflicto);
      return;
    }
    onGuardado();
  }

  return (
    <div className="space-y-3 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      <h3 className="text-sm font-semibold text-brand-800">
        {usuario ? `Editar ${usuario.username}` : "Nuevo usuario"}
      </h3>

      {otrosEditando.length > 0 && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          También hay alguien más editando esto ahora mismo:{" "}
          {otrosEditando.map((e) => e.username).join(", ")}. Si guardan al mismo tiempo, se avisa el conflicto y
          se pide refrescar.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={!!usuario}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm disabled:bg-brand-100/50"
        />
        {!usuario && (
          <input
            placeholder="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded border border-brand-100 px-2 py-1.5 text-sm"
          />
        )}
        <input
          placeholder="Teléfono"
          value={telefono}
          onChange={(e) => setTelefono(e.target.value)}
          className="rounded border border-brand-100 px-2 py-1.5 text-sm"
        />
        <select value={rol} onChange={(e) => setRol(e.target.value as Rol)} className="rounded border border-brand-100 px-2 py-1.5 text-sm">
          {rolesAsignables.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        {rol === "propietario" && (
          <input
            placeholder="Filtro de propietario (nombre exacto en Propiedades)"
            value={propietarioFiltro}
            onChange={(e) => setPropietarioFiltro(e.target.value)}
            className="rounded border border-brand-100 px-2 py-1.5 text-sm sm:col-span-2"
          />
        )}
      </div>

      {rol !== "propietario" && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-brand-500">Pestañas habilitadas</p>
          <div className="flex flex-wrap gap-2">
            {PESTANAS_MAESTRAS.map((p) => (
              <label
                key={p.clave}
                className={`flex items-center gap-1.5 rounded border px-2 py-1 text-xs ${
                  puedeOtorgar(p.clave) ? "border-brand-100" : "cursor-not-allowed border-brand-50 text-brand-300"
                }`}
                title={puedeOtorgar(p.clave) ? undefined : "No podés otorgar un permiso que vos mismo no tenés"}
              >
                <input
                  type="checkbox"
                  checked={permisos.includes(p.clave)}
                  disabled={!puedeOtorgar(p.clave)}
                  onChange={() => togglePermiso(p.clave)}
                />
                {p.icono} {p.label}
              </label>
            ))}
          </div>

          <p className="mb-1.5 mt-3 text-xs font-medium text-brand-500">Permisos adicionales</p>
          <div className="flex flex-wrap gap-2">
            {PERMISOS_TRANSVERSALES.map((p) => (
              <label
                key={p.clave}
                className={`flex items-center gap-1.5 rounded border px-2 py-1 text-xs ${
                  puedeOtorgar(p.clave) ? "border-brand-100" : "cursor-not-allowed border-brand-50 text-brand-300"
                }`}
                title={puedeOtorgar(p.clave) ? undefined : "No podés otorgar un permiso que vos mismo no tenés"}
              >
                <input
                  type="checkbox"
                  checked={permisos.includes(p.clave)}
                  disabled={!puedeOtorgar(p.clave)}
                  onChange={() => togglePermiso(p.clave)}
                />
                {p.label}
              </label>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{error}</p>
          {conflicto && (
            <button
              onClick={onGuardado}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              Refrescar lista (volvé a abrir "Editar" para reintentar)
            </button>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={guardando || conflicto || !username || (!usuario && !email)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        <button onClick={onCancelar} className="rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-600 hover:bg-brand-50">
          Cancelar
        </button>
      </div>
    </div>
  );
}
