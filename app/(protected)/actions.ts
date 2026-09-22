"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { requireSessionProfile } from "@/lib/auth/session";
import { EMPRESA_ACTIVA_COOKIE } from "@/lib/auth/empresaActivaCookie";

/**
 * Server Action del selector global de empresa (SelectorEmpresaActiva.tsx,
 * siempre visible arriba para superadmin — ver app/(protected)/layout.tsx).
 * Guarda la elección en una cookie que lib/auth/session.ts lee en cada
 * request y usa para sobreescribir `perfil.empresaId`/`nombreEmpresa` de
 * superadmin — así TODOS los módulos (que ya usan `perfil.empresaId` para
 * leer y escribir) quedan scopeados a la empresa elegida sin tener que
 * tocar cada uno por separado.
 *
 * `empresaId: null` = "sin empresa asignada" (el default, huérfanos).
 */
export async function seleccionarEmpresaActiva(empresaId: number | null): Promise<void> {
  const perfil = await requireSessionProfile();
  if (perfil.rol !== "superadmin") {
    throw new Error("Solo superadmin puede cambiar la empresa activa.");
  }

  const cookieStore = await cookies();
  if (empresaId === null) {
    cookieStore.delete(EMPRESA_ACTIVA_COOKIE);
  } else {
    cookieStore.set(EMPRESA_ACTIVA_COOKIE, String(empresaId), {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 días
    });
  }

  // Layout entero (todos los módulos protegidos leen perfil.empresaId a
  // través de requireSessionProfile en cada page.tsx/Server Action) —
  // sin esto, páginas ya renderizadas podrían quedar con datos viejos.
  revalidatePath("/", "layout");
}
