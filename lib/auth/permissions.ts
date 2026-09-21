import type { Rol } from "@/lib/types/database.types";

/**
 * Puerto directo de `pestanas_maestras` + el bloque
 * "CONFIGURACIÓN DINÁMICA DE PESTAÑAS SEGÚN PERMISOS Y ROL" de app.py
 * (v1.149, líneas ~2091-2150). Cada pestaña de v1 es ahora una ruta de v2.
 */
export interface Pestana {
  clave: string;
  icono: string;
  label: string;
  href: string;
}

export const PESTANAS_MAESTRAS: Pestana[] = [
  { clave: "dashboard", icono: "📈", label: "Tablero de Control", href: "/dashboard" },
  { clave: "planilla", icono: "📊", label: "Planilla de Contratos", href: "/planilla" },
  { clave: "pagos", icono: "💰", label: "Registrar / Emitir Recibo", href: "/pagos" },
  { clave: "historial_pagos", icono: "🗄️", label: "Historial de Caja", href: "/historial-pagos" },
  { clave: "carga", icono: "📝", label: "Carga de Contratos", href: "/carga" },
  { clave: "auxiliares", icono: "⚙️", label: "Cargar Inquilinos / Propiedades", href: "/auxiliares" },
  { clave: "gastos", icono: "🔧", label: "Gastos de Propiedades", href: "/gastos" },
  { clave: "rendicion", icono: "📑", label: "Rendición a Propietarios", href: "/rendicion" },
];

/**
 * "whatsapp" no es una pestaña navegable (no tiene pantalla propia): es un
 * permiso más dentro de `permisos_usuario`, igual que las de arriba, que
 * habilita el botón "Enviar por WhatsApp" dentro de Pagos/Planilla/etc.
 * Ver 0002_whatsapp_notes.sql. Se chequea con tieneWhatsapp(), no con
 * pestanasVisibles().
 */
const CLAVE_PERMISO_WHATSAPP = "whatsapp";

const PANEL_GESTION: Pestana = {
  clave: "panel_gestion",
  icono: "⚙️",
  label: "Panel de Gestión",
  href: "/panel-gestion",
};

const TERMINOS: Pestana = {
  clave: "terminos",
  icono: "📄",
  label: "Términos y Condiciones",
  href: "/terminos",
};

/** Pestañas de solo lectura para el rol "propietario" (líneas ~2130-2136 de app.py). */
const CLAVES_PROPIETARIO = ["dashboard", "planilla", "historial_pagos", "gastos", "rendicion"];

/**
 * Devuelve las pestañas visibles para un usuario según su rol y sus
 * permisos individuales (tabla `permisos_usuario`, solo aplica al rol
 * "user" y "admin" — mismo comportamiento que app.py).
 */
export function pestanasVisibles(rol: Rol, permisosUsuario: string[]): Pestana[] {
  switch (rol) {
    case "superadmin":
      return [...PESTANAS_MAESTRAS, PANEL_GESTION, TERMINOS];

    case "admin":
      return [
        ...PESTANAS_MAESTRAS.filter((p) => permisosUsuario.includes(p.clave)),
        PANEL_GESTION,
        TERMINOS,
      ];

    case "propietario":
      return [
        ...PESTANAS_MAESTRAS.filter((p) => CLAVES_PROPIETARIO.includes(p.clave)),
        TERMINOS,
      ];

    case "user":
    default:
      return [
        ...PESTANAS_MAESTRAS.filter((p) => permisosUsuario.includes(p.clave)),
        TERMINOS,
      ];
  }
}

/** El rol "propietario" es de solo lectura en todas sus pestañas visibles. */
export function esSoloLectura(rol: Rol): boolean {
  return rol === "propietario";
}

/**
 * ¿Puede este usuario ver los botones de envío por WhatsApp?
 * Requiere DOS condiciones, igual que v1:
 *   1. La empresa tiene WhatsApp habilitado (configuraciones_empresa.whatsapp_habilitado)
 *   2. El usuario tiene el permiso "whatsapp" en permisos_usuario (superadmin: siempre)
 */
export function tieneWhatsapp(
  rol: Rol,
  permisosUsuario: string[],
  empresaWhatsappHabilitado: boolean
): boolean {
  if (!empresaWhatsappHabilitado) return false;
  if (rol === "superadmin") return true;
  return permisosUsuario.includes(CLAVE_PERMISO_WHATSAPP);
}
