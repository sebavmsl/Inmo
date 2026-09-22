-- =====================================================================
-- 0013_panel_gestion_usuarios.sql
--
-- Módulo 1 (Panel de Gestión) — habilita al rol "admin" a gestionar los
-- usuarios de SU PROPIA empresa (alta, edición de datos y permisos),
-- algo que hoy Panel de Gestión no permite (bloqueado a superadmin,
-- ver app/(protected)/panel-gestion/page.tsx antes de esta entrega).
--
-- superadmin sigue gestionando cualquier empresa a través del cliente
-- service_role (createAdminAuthClient(), ver actions.ts) — las policies
-- de acá son para que ADEMÁS admin pueda hacerlo con el cliente normal
-- (con sesión), sin necesitar service_role.
-- =====================================================================

-- ── 1. Teléfono del usuario de staff ──────────────────────────────────
-- Falta hoy en usuarios_central (a diferencia de inquilinos, que ya lo
-- tiene) — se usa para poder contactar al usuario, y a futuro para
-- notificaciones (ver docs/DESIGN_LOG.md).
alter table usuarios_central
  add column if not exists telefono text;

-- ── 2. usuarios_central: admin lee y edita usuarios de su empresa ────
-- Políticas ADITIVAS a "propio_perfil"/"propio_perfil_update" (0001) —
-- Postgres combina policies permisivas del mismo comando con OR, así
-- que no hace falta tocar las existentes.

drop policy if exists "admin_ve_usuarios_empresa" on usuarios_central;
create policy "admin_ve_usuarios_empresa" on usuarios_central for select
  using (auth_rol() = 'admin' and empresa_id = auth_empresa_id());

-- admin no puede editar (ni de rebote, vía update de otra fila) una
-- fila de rol superadmin, ni la propia (ya cubierta por propio_perfil_update).
drop policy if exists "admin_edita_usuarios_empresa" on usuarios_central;
create policy "admin_edita_usuarios_empresa" on usuarios_central for update
  using (auth_rol() = 'admin' and empresa_id = auth_empresa_id() and rol <> 'superadmin')
  with check (auth_rol() = 'admin' and empresa_id = auth_empresa_id() and rol <> 'superadmin');

-- Alta de usuarios de staff por admin (superadmin sigue usando
-- service_role para alta de empresa+admin, ver crearEmpresaConAdmin).
-- admin no puede crear filas de rol superadmin ni admin — solo "user" y
-- "propietario" (ver puedeAsignarRol() en actions.ts, misma regla
-- validada acá por las dudas de que se llame la tabla directo).
drop policy if exists "admin_crea_usuarios_empresa" on usuarios_central;
create policy "admin_crea_usuarios_empresa" on usuarios_central for insert
  with check (
    auth_rol() = 'admin'
    and empresa_id = auth_empresa_id()
    and rol in ('user', 'propietario')
  );

-- ── 2.b superadmin: mismo editor, pero sin restricción de empresa ────
-- "propio_perfil" (0001) ya cubre el select de superadmin sobre
-- cualquier fila; acá se agrega lo que faltaba (update/insert) para que
-- el nuevo editor de Panel de Gestión funcione con el cliente normal
-- también para superadmin, sin necesitar service_role (que en este
-- proyecto se reserva solo para la Admin API de Auth, ver
-- lib/supabase/admin.ts).
drop policy if exists "superadmin_edita_cualquier_usuario" on usuarios_central;
create policy "superadmin_edita_cualquier_usuario" on usuarios_central for update
  using (auth_rol() = 'superadmin')
  with check (auth_rol() = 'superadmin');

drop policy if exists "superadmin_crea_cualquier_usuario" on usuarios_central;
create policy "superadmin_crea_cualquier_usuario" on usuarios_central for insert
  with check (auth_rol() = 'superadmin');

-- ── 3. permisos_usuario: admin lee y gestiona permisos de su empresa ─
-- Regla de negocio confirmada: "el admin solo puede otorgar los
-- permisos que él mismo tiene" — la UI ya deshabilita esos checkboxes,
-- pero acá queda blindado también a nivel de base: el `pestana` que se
-- intenta insertar/actualizar tiene que estar entre los permisos del
-- propio admin (o ser superadmin).

drop policy if exists "admin_ve_permisos_empresa" on permisos_usuario;
create policy "admin_ve_permisos_empresa" on permisos_usuario for select
  using (
    auth_rol() = 'admin'
    and username in (select username from usuarios_central where empresa_id = auth_empresa_id())
  );

drop policy if exists "admin_gestiona_permisos_empresa" on permisos_usuario;
create policy "admin_gestiona_permisos_empresa" on permisos_usuario for all
  using (
    auth_rol() = 'admin'
    and username in (
      select username from usuarios_central
      where empresa_id = auth_empresa_id() and rol <> 'superadmin'
    )
  )
  with check (
    auth_rol() = 'admin'
    and username in (
      select username from usuarios_central
      where empresa_id = auth_empresa_id() and rol <> 'superadmin'
    )
    and pestana in (
      select pp.pestana
      from permisos_usuario pp
      join usuarios_central u on u.username = pp.username
      where u.auth_user_id = auth.uid()
    )
  );

-- Nota: la policy "for all" de arriba ya cubre insert/update/delete;
-- "propios_permisos" (0001) sigue cubriendo el select de superadmin y
-- del propio usuario sobre sus propios permisos.

drop policy if exists "superadmin_gestiona_cualquier_permiso" on permisos_usuario;
create policy "superadmin_gestiona_cualquier_permiso" on permisos_usuario for all
  using (auth_rol() = 'superadmin')
  with check (auth_rol() = 'superadmin');
