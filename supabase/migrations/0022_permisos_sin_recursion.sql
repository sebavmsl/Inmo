-- =====================================================================
-- 0022_permisos_sin_recursion.sql  (V2.016)
--
-- Se corre A MANO en el SQL Editor de Supabase, completo, una sola vez.
--
-- Problema: la política "admin_gestiona_permisos_empresa" de
-- permisos_usuario consultaba permisos_usuario dentro de su propio
-- WITH CHECK (para validar que un admin solo otorgue permisos que él
-- mismo tiene). Postgres lo detecta como recursión infinita y falla
-- cualquier escritura en la tabla desde la v2 — incluso de superadmin —
-- con "infinite recursion detected in policy for relation permisos_usuario".
--
-- Solución estándar: una función SECURITY DEFINER que devuelve las
-- pestañas del usuario logueado sin pasar por RLS, usada en la política.
--
-- NO afecta a Python: Python se conecta como `postgres`, que no pasa por
-- políticas RLS.
-- =====================================================================

begin;

create or replace function public.auth_pestanas_propias()
returns setof text
language sql
security definer
stable
as $$
  select pp.pestana
  from permisos_usuario pp
  join usuarios_central u on u.username = pp.username
  where u.auth_user_id = auth.uid();
$$;

revoke execute on function public.auth_pestanas_propias() from public, anon;
grant execute on function public.auth_pestanas_propias() to authenticated;

drop policy if exists "admin_gestiona_permisos_empresa" on public.permisos_usuario;
create policy "admin_gestiona_permisos_empresa" on public.permisos_usuario for all to public
  using (
    auth_rol() = 'admin'
    and username in (
      select usuarios_central.username from usuarios_central
      where usuarios_central.empresa_id = auth_empresa_id() and usuarios_central.rol <> 'superadmin'
    )
  )
  with check (
    auth_rol() = 'admin'
    and username in (
      select usuarios_central.username from usuarios_central
      where usuarios_central.empresa_id = auth_empresa_id() and usuarios_central.rol <> 'superadmin'
    )
    and pestana in (select public.auth_pestanas_propias())
  );

commit;

-- ─────────────────────────────────────────────────────────────────────
-- Verificación (solo lectura). Esperado: la política ya no menciona
-- "permisos_usuario pp" y sí "auth_pestanas_propias".
-- ─────────────────────────────────────────────────────────────────────
-- select policyname,
--        (with_check like '%auth_pestanas_propias%') as usa_funcion,
--        (with_check like '%permisos_usuario pp%') as sigue_recursiva
-- from pg_policies where tablename = 'permisos_usuario' and policyname = 'admin_gestiona_permisos_empresa';
