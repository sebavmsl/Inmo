/**
 * Nombre de la cookie que guarda la "empresa activa" de superadmin — ver
 * lib/auth/session.ts (getSessionProfile) y app/(protected)/actions.ts
 * (seleccionarEmpresaActiva). Separado en su propio archivo porque un
 * archivo "use server" (Server Actions) solo puede exportar funciones,
 * no también esta constante.
 */
export const EMPRESA_ACTIVA_COOKIE = "sa_empresa_activa";
