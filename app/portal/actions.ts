"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export interface LoginPortalState {
  error: string | null;
}

/**
 * Login del Portal del Inquilino — más simple que el del staff (Módulo
 * 1): acá se loguea directo por email, sin la resolución
 * username→email que necesita el staff (v1 loguea por username; los
 * inquilinos nunca tuvieron ese concepto, entran directo con su email).
 */
export async function loginPortal(_prevState: LoginPortalState, formData: FormData): Promise<LoginPortalState> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  if (!email || !password) return { error: "Completá email y contraseña." };

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) return { error: "Email o contraseña incorrectos." };

  redirect("/portal/mi-cuenta");
}

export async function logoutPortal() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/portal/login");
}
