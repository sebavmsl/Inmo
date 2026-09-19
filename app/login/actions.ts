"use server";

import { z } from "zod";
import { redirect } from "next/navigation";
import { createClient, createAdminClient } from "@/lib/supabase/server";

const LoginSchema = z.object({
  usuario: z.string().trim().min(1, "Ingresá tu usuario."),
  password: z.string().min(1, "Ingresá tu contraseña."),
});

export interface LoginState {
  error: string | null;
}

/**
 * Equivalente a `verificar_usuario()` de app.py, pero delegando la
 * verificación de contraseña en Supabase Auth en vez de bcrypt manual.
 *
 * v1 loguea por `username`; Supabase Auth loguea por `email`. Para no
 * romper el flujo que ya conocen los usuarios, el formulario sigue
 * pidiendo "Usuario" y acá lo resolvemos a un email internamente:
 *   1. Buscamos el email asociado a ese username en `usuarios_central`
 *      (con el cliente admin, porque RLS no deja leer emails ajenos).
 *   2. Hacemos signInWithPassword con ese email + la contraseña ingresada.
 *
 * El rol de "superadmin" (antes hardcodeado en secrets.toml) pasa a ser
 * simplemente otra fila de `usuarios_central` con rol = 'superadmin'.
 */
export async function login(
  _prevState: LoginState,
  formData: FormData
): Promise<LoginState> {
  const parsed = LoginSchema.safeParse({
    usuario: formData.get("usuario"),
    password: formData.get("password"),
  });

  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "Datos inválidos." };
  }

  const { usuario, password } = parsed.data;

  const admin = createAdminClient();
  const { data: perfil, error: perfilError } = await admin
    .from("usuarios_central")
    .select("email")
    .eq("username", usuario)
    .single();

  if (perfilError || !perfil?.email) {
    return { error: "Usuario o contraseña incorrectos" };
  }

  const supabase = await createClient();
  const { error: authError } = await supabase.auth.signInWithPassword({
    email: perfil.email,
    password,
  });

  if (authError) {
    return { error: "Usuario o contraseña incorrectos" };
  }

  redirect("/dashboard");
}

export async function logout() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
